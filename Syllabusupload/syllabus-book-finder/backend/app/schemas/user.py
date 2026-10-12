from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict
import datetime

class UserBase(BaseModel):
    email: str
    full_name: str
    role: str = "faculty" # "admin" | "faculty"
    department: str
    designation: str
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class DepartmentFacultyStats(BaseModel):
    total_faculty: int
    departments_count: int
    department_breakdown: Dict[str, int]
    designation_breakdown: Dict[str, int]
