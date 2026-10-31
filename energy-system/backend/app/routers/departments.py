"""CRUD for Departments – /api/departments"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Audit, Department
from ..schemas import DepartmentCreate, DepartmentOut, DepartmentUpdate

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("", response_model=List[DepartmentOut])
def list_departments(
    block_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _u: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Department)
    if block_id is not None:
        q = q.filter(Department.block_id == block_id)
    if search:
        q = q.filter(Department.name.ilike(f"%{search}%"))
    return q.offset((page - 1) * page_size).limit(page_size).all()


@router.post("", response_model=DepartmentOut, status_code=201)
def create_department(body: DepartmentCreate, u: dict = Depends(require_admin),
                      db: Session = Depends(get_db)):
    if db.query(Department).filter_by(name=body.name).first():
        raise HTTPException(409, f"Department '{body.name}' already exists")
    dept = Department(**body.model_dump())
    db.add(dept)
    db.add(Audit(who=u["sub"], what=f"created department {body.name}"))
    db.commit()
    db.refresh(dept)
    return dept


@router.get("/{did}", response_model=DepartmentOut)
def get_department(did: int, _u: dict = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    dept = db.get(Department, did)
    if not dept:
        raise HTTPException(404, "Department not found")
    return dept


@router.patch("/{did}", response_model=DepartmentOut)
def update_department(did: int, body: DepartmentUpdate, u: dict = Depends(require_admin),
                      db: Session = Depends(get_db)):
    dept = db.get(Department, did)
    if not dept:
        raise HTTPException(404, "Department not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(dept, k, v)
    db.add(Audit(who=u["sub"], what=f"updated department {did}"))
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{did}", status_code=204)
def delete_department(did: int, u: dict = Depends(require_admin),
                      db: Session = Depends(get_db)):
    dept = db.get(Department, did)
    if not dept:
        raise HTTPException(404, "Department not found")
    db.delete(dept)
    db.add(Audit(who=u["sub"], what=f"deleted department {did}"))
    db.commit()

