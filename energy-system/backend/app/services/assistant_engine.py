"""Campus Energy Assistant Engine.

Handles natural language interpretation, entity resolution, fixed function calling,
and formatting with fallback/LLM options.
"""

import os
import re
import datetime as dt
from typing import Any, Dict, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from .assistant_resolver import resolve_entities
from .assistant_tools import (
    TARIFF,
    compare_scopes,
    explain_alert,
    get_alerts,
    get_device_status,
    get_now_ref,
    get_room_status,
    get_room_usage,
    get_timetable,
    get_top_consumers,
)

# Optional LLM integration via environment variable
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")


def answer_assistant_query(
    query: str,
    user: dict,
    db: Session,
    last_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Main assistant query handler.

    Returns:
        {
            "a": str,                 # Natural text response
            "scope": Optional[str],    # Contextual scope description
            "context": Dict[str, Any] # State for follow-up conversation
        }
    """
    q_clean = query.strip()
    q_lower = q_clean.lower()

    # 1. Resolve Target Entity
    entity, error_msg = resolve_entities(q_clean, db, user)
    if error_msg:
        # Access denied or ambiguous entity
        return {"a": error_msg, "scope": None, "context": last_context or {}}

    # Handle follow-up queries using prior context
    if not entity and last_context and last_context.get("entity"):
        # Check if query is a follow-up
        if any(w in q_lower for w in ("why", "yesterday", "today", "status", "usage", "cost", "free", "hours")):
            entity = last_context["entity"]

    # 2. Extract Period
    period = "today"
    if "yesterday" in q_lower:
        period = "yesterday"
    elif "last 7 days" in q_lower or "week" in q_lower:
        period = "7days"
    elif "this month" in q_lower or "month" in q_lower:
        period = "month"

    # -------------------------------------------------------------------------
    # Intent 0: Greetings, Help & Capabilities
    # -------------------------------------------------------------------------
    if any(q_lower == g or q_lower.startswith(g + " ") for g in ("hi", "hello", "hey", "help", "who are you", "what can you do")):
        ans = (
            "Hello! I am your AI Campus Energy Assistant. You can ask me questions about any room, block, department, or alert:\n"
            "• **Specific rooms**: *\"Status of A204\"*, *\"Is B101 free now?\"*, *\"Tell me about the seminar hall\"*\n"
            "• **Rankings & consumers**: *\"Which room consumes more power in A block?\"*, *\"Which block uses the most power today?\"*\n"
            "• **Department & block usage**: *\"How much power did Civil use today?\"*, *\"Compare CSE vs ECE\"*\n"
            "• **Alerts & anomalies**: *\"Why was an alert raised for A204?\"*, *\"Any open alerts today?\"*\n"
            "• **Bills & meters**: *\"What will the bill be this month?\"*, *\"Are any meters offline?\"*"
        )
        return {
            "a": ans,
            "scope": "Help & Capabilities",
            "context": last_context or {},
        }

    # -------------------------------------------------------------------------
    # Intent 1: Comparison between two entities
    # -------------------------------------------------------------------------
    if any(k in q_lower for k in ("compare", "versus", "vs", "difference", "than")):
        # Look for two entities mentioned in query
        parts = re.split(r"\b(?:and|vs|versus|with|to|than|or)\b", q_clean, flags=re.IGNORECASE)
        if len(parts) >= 2:
            e1, err1 = resolve_entities(parts[0], db, user)
            e2, err2 = resolve_entities(parts[1], db, user)
            if err1:
                return {"a": err1, "scope": None, "context": {}}
            if err2:
                return {"a": err2, "scope": None, "context": {}}

            if e1 and e2:
                cmp_res = compare_scopes(e1, e2, period, user, db)
                ans = (
                    f"Comparison for {cmp_res['period']}:\n"
                    f"• {cmp_res['entity_a']['label']}: {cmp_res['entity_a']['kwh']} kWh (est. cost Rs {cmp_res['entity_a']['est_cost']:,})\n"
                    f"• {cmp_res['entity_b']['label']}: {cmp_res['entity_b']['kwh']} kWh (est. cost Rs {cmp_res['entity_b']['est_cost']:,})\n"
                    f"Difference: {cmp_res['difference_kwh']} kWh ({cmp_res['higher']} is higher). Data source: simulated."
                )
                return {
                    "a": ans,
                    "scope": f"{e1.get('label')} vs {e2.get('label')}, {period}",
                    "context": {"entity": e1},
                }

    # -------------------------------------------------------------------------
    # Intent 1.5: Bill Estimate / Monthly Cost / Budget
    # -------------------------------------------------------------------------
    if any(k in q_lower for k in ("bill", "budget", "monthly cost", "tariff", "rate")) and not (entity and entity.get("type") == "room"):
        from ..routers.overview import overview, BUDGET_KWH
        o = overview(user, db)
        ans = (
            f"Estimated energy bill for this month is **Rs {o['est_bill']:,}** (estimate at Rs {o['tariff']}/kWh).\n"
            f"• Month-to-date energy: {o['month_kwh']:,} kWh ({o['budget_pct']}% of {BUDGET_KWH:,.0f} kWh monthly budget)\n"
            f"• Today's energy spend: Rs {round(o['today_kwh'] * o['tariff']):,} estimate ({o['today_kwh']} kWh)\n"
            f"• Current demand: {o['current_kw']} kW across {o['meters']} reporting meters."
        )
        return {
            "a": ans,
            "scope": f"Bill estimate, {period}",
            "context": last_context or {},
        }

    # -------------------------------------------------------------------------
    # Intent 1.6: Forecast / Projections
    # -------------------------------------------------------------------------
    if any(k in q_lower for k in ("forecast", "projection", "predict", "future consumption")):
        from ..routers.overview import forecast
        fc = forecast(user, db)
        daily = fc.get("daily", [])
        if daily:
            ans = (
                f"Campus Energy Forecast ({fc.get('method', 'statistical estimate')}):\n"
                f"• Average historical daily draw: {fc['avg_daily_kwh']} kWh/day across {len(daily)} tracked days\n"
                f"• Projected 30-day consumption: {fc['month_kwh']:,} kWh (est. cost Rs {fc['month_cost']:,})\n"
                f"• Projected budget usage: {fc['budget_pct']}% of monthly budget."
            )
        else:
            ans = "Insufficient telemetry history to compute forecast projection."
        return {
            "a": ans,
            "scope": "Campus energy forecast",
            "context": last_context or {},
        }

    # -------------------------------------------------------------------------
    # Intent 2: Offline / Device status
    # -------------------------------------------------------------------------
    if any(k in q_lower for k in ("offline", "disconnected", "heartbeat", "device", "reporting")):
        res = get_device_status(entity, user, db)
        if res["offline_count"] == 0:
            ans = f"All meters in scope ({res['scope']}) are currently online and communicating normally."
        else:
            room_list = ", ".join([f"{r['room']} ({r['meter']})" for r in res["offline_rooms"][:5]])
            ans = (
                f"{res['offline_count']} room meters are currently offline in {res['scope']}: {room_list}. "
                f"Note: Offline meters reflect missing telemetry, not zero consumption."
            )
        return {
            "a": ans,
            "scope": res["scope"],
            "context": {"entity": entity} if entity else {},
        }

    # -------------------------------------------------------------------------
    # Intent 3: Alert Explanation / Open Alerts
    # -------------------------------------------------------------------------
    if any(k in q_lower for k in ("alert", "why", "anomaly", "investigate", "spike")):
        if entity and entity.get("type") == "room":
            res = explain_alert(entity, user, db)
            if res["found"]:
                dur_str = f" for {res.get('duration_min')} min" if res.get('duration_min') else ""
                ans = (
                    f"Alert explanation for Room {res['room']} ({res['kind']}, {res['severity']} severity at {res['time']}):\n"
                    f"• Measured draw: {res['measured_kw']} kW against normal baseline of {res['baseline_kw']} kW{dur_str}.\n"
                    f"• Timetable status at event: {res.get('status_at_event', 'Checked')}\n"
                    f"• Details: {res['explanation']}\n"
                    f"• Suggested action: {res['recommended_action']}"
                )
            else:
                # Part 1(b): No alerts have been raised -> give latest reading, timetable status now, and normal baseline
                st_res = get_room_status(entity, db)
                from ..simulator import baseline
                base_val, _ = baseline(db, entity["id"], st_res["current_status"], dt.datetime.now())
                ans = (
                    f"No alerts have been raised for {entity['label']}.\n"
                    f"• Current power draw: {st_res['power_kw'] or '—'} kW (telemetry: {st_res['source']})\n"
                    f"• Timetable status now: {st_res['current_status']}\n"
                    f"• Normal baseline draw: {round(base_val, 2)} kW (typical expectation)."
                )
            return {
                "a": ans,
                "scope": f"{entity['label']} alerts",
                "context": {"entity": entity},
            }
        else:
            res = get_alerts(entity, "open", user, db)
            if not res["alerts"]:
                ans = f"There are currently no open alerts for {res['scope']}."
            else:
                alert_lines = [
                    f"• {a['room']}: {a['kind']} ({a['power_kw']} kW vs {a['baseline_kw']} kW baseline) at {a['time']}. Please investigate."
                    for a in res["alerts"]
                ]
                ans = f"Found {res['total_matching']} open alert(s) in {res['scope']}:\n" + "\n".join(alert_lines)
            return {
                "a": ans,
                "scope": res["scope"],
                "context": {"entity": entity} if entity else {},
            }

    # -------------------------------------------------------------------------
    # Intent 4: Timetable / Is Room Free?
    # -------------------------------------------------------------------------
    if entity and entity.get("type") == "room" and any(k in q_lower for k in ("free", "occupied", "class", "schedule", "timetable", "activity")):
        tt_res = get_timetable(entity, None, db)
        free_txt = "free" if tt_res["is_free_now"] else "occupied"
        ans = (
            f"{tt_res['room']} is currently scheduled as **{tt_res['current_status']}** ({free_txt}) on {tt_res['day']}. "
            f"Scheduled slots today include: " + ", ".join([f"{s['hour']} ({s['activity']})" for s in tt_res['slots'][:4]]) + "..."
        )
        return {
            "a": ans,
            "scope": f"Timetable: {entity['label']}",
            "context": {"entity": entity},
        }

    # -------------------------------------------------------------------------
    # Intent 5: Top Consumers / Highest Usage Ranking
    # -------------------------------------------------------------------------
    if any(k in q_lower for k in ("highest", "most", "top", "max", "consume", "consumes", "usage")):
        # If the query is specifically asking about a single room's usage and not ranking/comparing, let Intent 6 handle it
        if entity and entity.get("type") == "room" and not any(k in q_lower for k in ("highest", "most", "top", "max", "rank", "compare")):
            pass
        else:
            # Determine target to rank (rooms, departments, floors, blocks)
            # Separate the TARGET from the SCOPE FILTER
            if re.search(r"\b(rooms?)\b", q_lower):
                target = "rooms"
            elif re.search(r"\b(departments?|depts?)\b", q_lower):
                target = "departments"
            elif re.search(r"\b(floors?)\b", q_lower):
                target = "floors"
            elif re.search(r"\b(blocks?)\b", q_lower) and not (
                entity and entity.get("type") == "block" and not re.search(r"\b(which|what|top|highest|most)\s+block", q_lower)
            ):
                target = "blocks"
            else:
                # Default: if scoped to a container (block, floor, dept), rank rooms in that container; otherwise blocks
                target = "rooms" if entity else "blocks"

            # Execute top consumers query with the scope filter
            res = get_top_consumers(target, period, user, db, scope_filter=entity, limit=3)
            period_phrase = "today" if period == "today" else ("yesterday" if period == "yesterday" else ("over the last 7 days" if period == "7days" else "this month"))

            # Build accurate scope label (e.g., "Block A rooms, today")
            if target == "rooms":
                if entity:
                    scope_label = f"{entity['label']} rooms, {period}"
                else:
                    scope_label = f"Campus rooms, {period}"
            elif target == "blocks":
                scope_label = f"Campus blocks, {period}"
            elif target == "departments":
                scope_label = f"Campus departments, {period}"
            elif target == "floors":
                scope_label = f"{entity['label'] if entity else 'Campus'} floors, {period}"
            else:
                scope_label = f"{res['category']}, {period}"

            if not res["ranking"]:
                ans = f"No energy consumption recorded for {scope_label}."
            else:
                top = res["ranking"][0]
                kw_mention = f" and highest current demand is {top['current_kw']} kW" if top.get("current_kw") is not None else ""

                if target == "rooms":
                    container_label = entity['label'] if entity else "the campus"
                    ans = (
                        f"{top.get('room_name', top['label'])} used the most in {container_label} {period_phrase}: "
                        f"{top['kwh']} kWh (metric: total energy used {period_phrase}, est. cost Rs {top['est_cost']:,}){kw_mention}."
                    )
                    if len(res["ranking"]) > 1:
                        rank_items = [
                            f"• {item.get('room_name', item['label'])}: {item['kwh']} kWh" + (f" (current: {item['current_kw']} kW)" if item.get('current_kw') is not None else "")
                            for item in res["ranking"]
                        ]
                        ans += f"\nTop consumers in {container_label} for {period}:\n" + "\n".join(rank_items)
                elif target == "blocks":
                    ans = (
                        f"{top['label']} used the most {period_phrase}: {top['kwh']} kWh "
                        f"(metric: total energy used {period_phrase}, est. cost Rs {top['est_cost']:,})."
                    )
                    if len(res["ranking"]) > 1:
                        rank_items = [f"• {item['label']}: {item['kwh']} kWh (est. cost Rs {item['est_cost']:,})" for item in res["ranking"]]
                        ans += f"\nCampus blocks ranked by energy usage ({period}):\n" + "\n".join(rank_items)
                else:
                    ans = (
                        f"{top['label']} used the most {period_phrase}: {top['kwh']} kWh "
                        f"(metric: total energy used {period_phrase}, est. cost Rs {top['est_cost']:,})."
                    )
                    if len(res["ranking"]) > 1:
                        rank_items = [f"• {item['label']}: {item['kwh']} kWh (est. cost Rs {item['est_cost']:,})" for item in res["ranking"]]
                        ans += f"\nTop {target} for {period}:\n" + "\n".join(rank_items)

            return {
                "a": ans,
                "scope": scope_label,
                "context": {"entity": entity} if entity else {},
            }

    # -------------------------------------------------------------------------
    # Intent 6: Room Usage / Cost for Room Entity
    # -------------------------------------------------------------------------
    if entity and entity.get("type") == "room":
        usage_res = get_room_usage(entity, period, db)
        status_res = get_room_status(entity, db)

        ans = (
            f"{entity['label']} ({entity.get('rtype', 'Room')}, Dept: {entity.get('department')}) status:\n"
            f"• Current power draw: {status_res['power_kw'] or '—'} kW (status: {status_res['current_status']}, telemetry: {status_res['source']})\n"
            f"• Energy used {usage_res['period']}: {usage_res['energy_kwh']} kWh\n"
            f"• Estimated cost {usage_res['period']}: Rs {usage_res['est_cost_rs']:,} (at Rs {usage_res['tariff_per_kwh']}/kWh estimate)."
        )
        return {
            "a": ans,
            "scope": f"{entity['label']}, {period}",
            "context": {"entity": entity},
        }

    # -------------------------------------------------------------------------
    # Intent 7: Block / Floor / Department Usage
    # -------------------------------------------------------------------------
    if entity:
        from ..models import Reading
        from .assistant_tools import _get_permitted_room_ids, get_now_ref

        rids = _get_permitted_room_ids(db, user, entity)
        now_ref = get_now_ref(db)
        today_0 = now_ref.replace(hour=0, minute=0, second=0, microsecond=0)

        if period == "yesterday":
            start_ts = today_0 - dt.timedelta(days=1)
            end_ts = today_0
        elif period in ("7days", "last 7 days", "week"):
            start_ts = now_ref - dt.timedelta(days=7)
            end_ts = now_ref
        elif period in ("month", "this month"):
            start_ts = today_0.replace(day=1)
            end_ts = now_ref
        else:
            start_ts = today_0
            end_ts = now_ref

        total_kwh = (
            db.query(func.coalesce(func.sum(Reading.energy_kwh), 0.0))
            .filter(Reading.room_id.in_(rids), Reading.ts >= start_ts, Reading.ts <= end_ts)
            .scalar()
        )
        latest_ts = db.query(func.max(Reading.ts)).filter(Reading.room_id.in_(rids)).scalar()
        cur_kw = (
            db.query(func.coalesce(func.sum(Reading.power_kw), 0.0))
            .filter(Reading.room_id.in_(rids), Reading.ts == latest_ts)
            .scalar()
        ) if latest_ts else 0.0
        est_cost = round(total_kwh * TARIFF, 2)

        ans = (
            f"{entity.get('label')} energy summary ({period}):\n"
            f"• Rooms monitored: {len(rids)}\n"
            f"• Active power demand: {round(cur_kw, 2)} kW (simulated)\n"
            f"• Energy consumption {period}: {round(total_kwh, 1)} kWh\n"
            f"• Estimated cost {period}: Rs {round(est_cost):,} (rate Rs {TARIFF}/kWh estimate)."
        )
        return {
            "a": ans,
            "scope": f"{entity.get('label')}, {period}",
            "context": {"entity": entity},
        }

    # -------------------------------------------------------------------------
    # Default: General Campus Overview
    # -------------------------------------------------------------------------
    from ..routers.overview import overview
    o = overview(user, db)
    ans = (
        f"Campus Energy Status as of {str(o['as_of']).replace('T', ' ')}:\n"
        f"• Active power demand: {o['current_kw']} kW across {o['meters']} reporting meters\n"
        f"• Energy used today: {o['today_kwh']} kWh (est. cost Rs {round(o['today_kwh'] * o['tariff']):,})\n"
        f"• Month consumption so far: {o['month_kwh']:,} kWh (estimated bill: Rs {o['est_bill']:,})\n"
        f"• Budget utilization: {o['budget_pct']}% of monthly budget\n"
        f"• Open alerts: {o['open_alerts']}\n"
        f"Ask me about any room (e.g. A204, B101, C102), block, floor, department, or alert."
    )
    return {
        "a": ans,
        "scope": "Campus overview, today",
        "context": last_context or {},
    }
