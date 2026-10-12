from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    DepartmentFacultyStats
)
from app.utils.auth import hash_password, require_admin, get_current_user_optional

router = APIRouter(prefix="/faculty", tags=["Faculty Management (Admin)"])

@router.get("", response_model=List[UserResponse])
def list_faculty(
    department: Optional[str] = Query(None, description="Filter by department"),
    designation: Optional[str] = Query(None, description="Filter by designation"),
    search: Optional[str] = Query(None, description="Search by name, email, or ID"),
    is_active: Optional[bool] = Query(None, description="Filter active status"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    List faculty members organized department-wise and designation-wise.
    Admin access required.
    """
    query = db.query(User).filter(User.role == "faculty")

    if department and department.strip():
        query = query.filter(User.department.ilike(f"%{department.strip()}%"))

    if designation and designation.strip():
        query = query.filter(User.designation.ilike(f"%{designation.strip()}%"))

    if search and search.strip():
        search_term = f"%{search.strip()}%"
        query = query.filter(
            (User.full_name.ilike(search_term)) |
            (User.email.ilike(search_term)) |
            (User.employee_id.ilike(search_term))
        )

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    return query.order_by(User.department.asc(), User.designation.asc(), User.full_name.asc()).all()

@router.get("/stats", response_model=DepartmentFacultyStats)
def get_faculty_department_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Retrieve statistical distribution of faculty members across departments and designations."""
    faculty_list = db.query(User).filter(User.role == "faculty").all()

    dept_counts = {}
    desig_counts = {}

    for f in faculty_list:
        d = f.department or "Unassigned"
        dept_counts[d] = dept_counts.get(d, 0) + 1

        des = f.designation or "Lecturer"
        desig_counts[des] = desig_counts.get(des, 0) + 1

    return DepartmentFacultyStats(
        total_faculty=len(faculty_list),
        departments_count=len(dept_counts),
        department_breakdown=dept_counts,
        designation_breakdown=desig_counts
    )

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_faculty(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Add a new faculty member with specific department and designation."""
    # Check if email exists
    existing = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A faculty or user with email '{payload.email}' already exists."
        )

    new_faculty = User(
        email=payload.email.lower().strip(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role="faculty",
        department=payload.department.strip(),
        designation=payload.designation.strip(),
        employee_id=payload.employee_id.strip() if payload.employee_id else None,
        phone=payload.phone.strip() if payload.phone else None,
        is_active=payload.is_active
    )
    db.add(new_faculty)
    db.commit()
    db.refresh(new_faculty)
    return new_faculty

@router.get("/{faculty_id}", response_model=UserResponse)
def get_faculty_detail(
    faculty_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get single faculty profile by ID."""
    faculty = db.query(User).filter(User.id == faculty_id, User.role == "faculty").first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty record not found.")
    return faculty

@router.put("/{faculty_id}", response_model=UserResponse)
def update_faculty(
    faculty_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update faculty member details (department, designation, name, contact, password)."""
    faculty = db.query(User).filter(User.id == faculty_id, User.role == "faculty").first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty record not found.")

    if payload.email and payload.email.lower().strip() != faculty.email:
        existing = db.query(User).filter(User.email == payload.email.lower().strip()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Another user with this email already exists.")
        faculty.email = payload.email.lower().strip()

    if payload.full_name is not None:
        faculty.full_name = payload.full_name.strip()
    if payload.department is not None:
        faculty.department = payload.department.strip()
    if payload.designation is not None:
        faculty.designation = payload.designation.strip()
    if payload.employee_id is not None:
        faculty.employee_id = payload.employee_id.strip()
    if payload.phone is not None:
        faculty.phone = payload.phone.strip()
    if payload.is_active is not None:
        faculty.is_active = payload.is_active
    if payload.password and payload.password.strip():
        faculty.password_hash = hash_password(payload.password.strip())

    db.commit()
    db.refresh(faculty)
    return faculty

@router.delete("/{faculty_id}", status_code=status.HTTP_200_OK)
def delete_faculty(
    faculty_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete a faculty member."""
    faculty = db.query(User).filter(User.id == faculty_id, User.role == "faculty").first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty record not found.")

    db.delete(faculty)
    db.commit()
    return {"message": f"Faculty member '{faculty.full_name}' deleted successfully."}

@router.get("/settings")
def get_faculty_settings(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get faculty setting: Automatically download and index verified open-access books."""
    auto_dl = False
    if current_user:
        auto_dl = bool(getattr(current_user, "auto_download_verified_oa", False))
    else:
        f = db.query(User).filter(User.role == "faculty").first()
        if f:
            auto_dl = bool(getattr(f, "auto_download_verified_oa", False))
    return {"auto_download_verified_oa": auto_dl}

@router.post("/settings")
@router.put("/settings")
def update_faculty_settings(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Update faculty setting: Automatically download and index verified open-access books."""
    enabled = bool(payload.get("auto_download_verified_oa", False))
    if current_user:
        current_user.auto_download_verified_oa = enabled
        db.commit()
    else:
        faculties = db.query(User).filter(User.role == "faculty").all()
        for f in faculties:
            f.auto_download_verified_oa = enabled
        db.commit()
    return {"auto_download_verified_oa": enabled, "message": "Faculty settings updated successfully."}

