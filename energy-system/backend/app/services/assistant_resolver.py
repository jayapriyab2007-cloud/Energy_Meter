"""Entity resolution and permission scoping for Campus Energy Assistant.

Resolves mentions of:
- Rooms by code (e.g., "A204", "a 204", "B101")
- Rooms by name/label (e.g., "seminar hall", "survey lab", "principal's office")
- Blocks (e.g., "Block A", "B Block", "block 3" -> invalid)
- Floors (e.g., "second floor of C block", "floor 2 of Block B")
- Departments (e.g., "CSE", "Civil", "Biotechnology", "ECE")
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from ..models import Block, Department, Floor, Room


def check_scope_permission(entity: Dict[str, Any], user: dict) -> bool:
    """Return True if user has access to entity based on user['block']."""
    if user.get("role") == "admin":
        return True
    user_block = user.get("block")
    if not user_block:
        return True

    # If entity has a block attribute, compare
    e_block = entity.get("block")
    if e_block:
        return e_block.upper() == user_block.upper()

    # If entity is a department, check if all its rooms or home_block match
    if entity.get("type") == "department":
        d_block = entity.get("home_block")
        if d_block:
            return d_block.upper() == user_block.upper()

    return False


def resolve_entities(
    query: str, db: Session, user: dict
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse query to identify the target entity.

    Returns:
        (entity_dict, error_or_clarification_message)
    """
    q = query.strip()
    q_lower = q.lower()

    # Pre-fetch campus data
    rooms = db.query(Room).all()
    blocks = db.query(Block).all()
    floors = db.query(Floor).all()
    departments = db.query(Department).all()

    # 1. Match Room Code: e.g. A204, A 204, B101, C 102
    room_code_match = re.search(r"\b([a-dA-D])\s*(\d{3})\b", q)
    if room_code_match:
        code = f"{room_code_match.group(1).upper()}{room_code_match.group(2)}"
        room = next((r for r in rooms if r.name.upper() == code), None)
        if room:
            entity = {
                "type": "room",
                "id": room.id,
                "name": room.name,
                "block": room.block,
                "floor": room.floor,
                "rtype": room.rtype,
                "department": room.department.name if room.department else "Unassigned",
                "label": f"Room {room.name}",
            }
            if not check_scope_permission(entity, user):
                return None, f"Access denied: You do not have permission to view data for Room {room.name} in Block {room.block}."
            return entity, None

    # 2. Match Room by descriptive name / label
    matched_rooms = []
    for r in rooms:
        r_name_clean = r.name.lower()
        # Check against common room types or names if any
        # Also check against department room name in seed if any
        candidates = [r_name_clean]
        if r.rtype:
            candidates.append(r.rtype.lower())

        # Check special known room descriptions
        if r.name == "B101":
            candidates.extend(["seminar hall", "seminar room b101", "auditorium"])
        elif r.name == "A101":
            candidates.extend(["principal's office", "principal office"])
        elif r.name == "A102":
            candidates.extend(["administration office", "admin office"])
        elif r.name == "A103":
            candidates.extend(["accounts office", "accounts"])
        elif r.name == "A104":
            candidates.extend(["conference room"])
        elif r.name == "C102":
            candidates.extend(["survey lab"])
        elif r.name == "C103":
            candidates.extend(["concrete lab"])
        elif r.name == "C203":
            candidates.extend(["machines lab"])

        for c in candidates:
            if re.search(r"\b" + re.escape(c) + r"\b", q_lower):
                matched_rooms.append(r)
                break

    if len(matched_rooms) == 1:
        rm = matched_rooms[0]
        entity = {
            "type": "room",
            "id": rm.id,
            "name": rm.name,
            "block": rm.block,
            "floor": rm.floor,
            "rtype": rm.rtype,
            "department": rm.department.name if rm.department else "Unassigned",
            "label": f"Room {rm.name} ({rm.rtype})",
        }
        if not check_scope_permission(entity, user):
            return None, f"Access denied: You do not have permission to view data for {entity['label']}."
        return entity, None
    elif len(matched_rooms) > 1:
        options = ", ".join([f"{r.name} ({r.rtype} in Block {r.block})" for r in matched_rooms[:4]])
        return None, f"Your query matched multiple rooms: {options}. Please specify the exact room code."

    # 3. Match Floor: e.g. "floor 2 of Block B", "second floor of C block", "Floor 1"
    floor_match = re.search(r"(?:floor\s*(\d)|(\w+)\s*floor)\s*(?:of|in)?\s*(?:block\s*([a-dA-D])|([a-dA-D])\s*block)?", q_lower)
    if floor_match:
        f_num_str = floor_match.group(1)
        word_num = floor_match.group(2)
        b_letter = floor_match.group(3) or floor_match.group(4)

        num_map = {"first": 1, "second": 2, "third": 3, "fourth": 4, "ground": 1}
        f_num = int(f_num_str) if f_num_str else num_map.get(word_num)

        if f_num and b_letter:
            blk_name = b_letter.upper()
            target_floor = next((f for f in floors if f.number == f_num and f.block and f.block.name == blk_name), None)
            if target_floor:
                entity = {
                    "type": "floor",
                    "id": target_floor.id,
                    "number": target_floor.number,
                    "block": blk_name,
                    "label": f"Floor {target_floor.number} of Block {blk_name}",
                }
                if not check_scope_permission(entity, user):
                    return None, f"Access denied: You do not have permission to view Floor {target_floor.number} in Block {blk_name}."
                return entity, None

    # 4. Match Department: e.g. "CSE", "Civil", "ECE", "Biotechnology", "MCT"
    for d in departments:
        # Check abbreviation in parentheses or full name
        abbr_match = re.search(r"\((.*?)\)", d.name)
        abbr = abbr_match.group(1).lower() if abbr_match else ""
        clean_name = re.sub(r"\(.*?\)", "", d.name).strip().lower()

        # Extract primary word (e.g. 'civil' from 'civil engineering')
        primary_word = clean_name.split()[0] if clean_name else ""

        matched = False
        if abbr and re.search(r"\b" + re.escape(abbr) + r"\b", q_lower):
            matched = True
        elif clean_name and re.search(r"\b" + re.escape(clean_name) + r"\b", q_lower):
            matched = True
        elif primary_word and len(primary_word) > 3 and re.search(r"\b" + re.escape(primary_word) + r"\b", q_lower):
            matched = True

        if matched:
            home_b = d.block.name if d.block else None
            entity = {
                "type": "department",
                "id": d.id,
                "name": d.name,
                "home_block": home_b,
                "label": f"Department of {d.name}",
            }
            if not check_scope_permission(entity, user):
                return None, f"Access denied: You do not have permission to view {d.name} data."
            return entity, None

    # 5. Match Block: e.g. "Block A", "A block", "Block B"
    block_match = re.search(r"\b(?:block\s*([a-dA-D])|([a-dA-D])\s*block)\b", q_lower)
    if block_match:
        b_name = (block_match.group(1) or block_match.group(2)).upper()
        blk = next((b for b in blocks if b.name == b_name), None)
        if blk:
            entity = {
                "type": "block",
                "id": blk.id,
                "name": blk.name,
                "block": blk.name,
                "label": f"Block {blk.name}",
            }
            if not check_scope_permission(entity, user):
                return None, f"Access denied: You do not have permission to view Block {blk.name}."
            return entity, None

    return None, None
