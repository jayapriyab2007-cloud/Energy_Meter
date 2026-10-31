"""CRUD for Blocks – /api/blocks"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Audit, Block
from ..schemas import BlockCreate, BlockOut, BlockUpdate

router = APIRouter(prefix="/api/blocks", tags=["blocks"])


@router.get("", response_model=List[BlockOut])
def list_blocks(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _u: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Block)
    if search:
        q = q.filter(Block.name.ilike(f"%{search}%"))
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return items


@router.post("", response_model=BlockOut, status_code=201)
def create_block(body: BlockCreate, u: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    if db.query(Block).filter_by(name=body.name).first():
        raise HTTPException(409, f"Block '{body.name}' already exists")
    blk = Block(**body.model_dump())
    db.add(blk)
    db.add(Audit(who=u["sub"], what=f"created block {body.name}"))
    db.commit()
    db.refresh(blk)
    return blk


@router.get("/{bid}", response_model=BlockOut)
def get_block(bid: int, _u: dict = Depends(get_current_user),
              db: Session = Depends(get_db)):
    blk = db.get(Block, bid)
    if not blk:
        raise HTTPException(404, "Block not found")
    return blk


@router.patch("/{bid}", response_model=BlockOut)
def update_block(bid: int, body: BlockUpdate, u: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    blk = db.get(Block, bid)
    if not blk:
        raise HTTPException(404, "Block not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(blk, k, v)
    db.add(Audit(who=u["sub"], what=f"updated block {bid}"))
    db.commit()
    db.refresh(blk)
    return blk


@router.delete("/{bid}", status_code=204)
def delete_block(bid: int, u: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    blk = db.get(Block, bid)
    if not blk:
        raise HTTPException(404, "Block not found")
    db.delete(blk)
    db.add(Audit(who=u["sub"], what=f"deleted block {bid}"))
    db.commit()

