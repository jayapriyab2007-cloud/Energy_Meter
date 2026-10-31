"""CRUD for Floors – /api/floors"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Audit, Block, Floor
from ..schemas import FloorCreate, FloorOut, FloorUpdate

router = APIRouter(prefix="/api/floors", tags=["floors"])


@router.get("", response_model=List[FloorOut])
def list_floors(
    block_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _u: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Floor)
    if block_id is not None:
        q = q.filter(Floor.block_id == block_id)
    return q.offset((page - 1) * page_size).limit(page_size).all()


@router.post("", response_model=FloorOut, status_code=201)
def create_floor(body: FloorCreate, u: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    if not db.get(Block, body.block_id):
        raise HTTPException(404, "Block not found")
    existing = db.query(Floor).filter_by(block_id=body.block_id, number=body.number).first()
    if existing:
        raise HTTPException(409, f"Floor {body.number} already exists in that block")
    fl = Floor(**body.model_dump())
    db.add(fl)
    db.add(Audit(who=u["sub"], what=f"created floor block={body.block_id} number={body.number}"))
    db.commit()
    db.refresh(fl)
    return fl


@router.get("/{fid}", response_model=FloorOut)
def get_floor(fid: int, _u: dict = Depends(get_current_user),
              db: Session = Depends(get_db)):
    fl = db.get(Floor, fid)
    if not fl:
        raise HTTPException(404, "Floor not found")
    return fl


@router.patch("/{fid}", response_model=FloorOut)
def update_floor(fid: int, body: FloorUpdate, u: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    fl = db.get(Floor, fid)
    if not fl:
        raise HTTPException(404, "Floor not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(fl, k, v)
    db.add(Audit(who=u["sub"], what=f"updated floor {fid}"))
    db.commit()
    db.refresh(fl)
    return fl


@router.delete("/{fid}", status_code=204)
def delete_floor(fid: int, u: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    fl = db.get(Floor, fid)
    if not fl:
        raise HTTPException(404, "Floor not found")
    db.delete(fl)
    db.add(Audit(who=u["sub"], what=f"deleted floor {fid}"))
    db.commit()

