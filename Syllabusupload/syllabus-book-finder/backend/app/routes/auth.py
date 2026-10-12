from typing import Optional
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import LoginRequest, LoginResponse, UserResponse
from app.utils.auth import (
    verify_password,
    hash_password,
    create_access_token,
    get_current_user,
    security_scheme,
    SECRET_KEY,
    ALGORITHM
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

def seed_default_users_if_needed(db: Session):
    """Seed initial administrator and faculty accounts if user table is empty."""
    admin_exists = db.query(User).filter(User.role == "admin").first()
    if not admin_exists:
        admin_user = User(
            email="admin@college.edu",
            password_hash=hash_password("Admin@123"),
            full_name="Academic Administrator",
            role="admin",
            department="Academic Affairs & Examination Cell",
            designation="Dean of Academics",
            employee_id="ADM-001",
            phone="+91 98765 00001",
            is_active=True
        )
        db.add(admin_user)

    faculty_count = db.query(User).filter(User.role == "faculty").count()
    if faculty_count == 0:
        sample_faculty_1 = User(
            email="faculty@college.edu",
            password_hash=hash_password("Faculty@123"),
            full_name="Dr. Rajesh Raman",
            role="faculty",
            department="Computer Science & Engineering",
            designation="Associate Professor",
            employee_id="CSE-104",
            phone="+91 98765 43210",
            is_active=True
        )
        sample_faculty_2 = User(
            email="sharma@college.edu",
            password_hash=hash_password("Faculty@123"),
            full_name="Prof. Sunita Sharma",
            role="faculty",
            department="Electronics & Communication",
            designation="Professor & HOD",
            employee_id="ECE-042",
            phone="+91 98765 43211",
            is_active=True
        )
        sample_faculty_3 = User(
            email="anita@college.edu",
            password_hash=hash_password("Faculty@123"),
            full_name="Dr. Anita Kulkarni",
            role="faculty",
            department="Information Science & Engineering",
            designation="Assistant Professor",
            employee_id="ISE-208",
            phone="+91 98765 43212",
            is_active=True
        )
        db.add_all([sample_faculty_1, sample_faculty_2, sample_faculty_3])
        db.commit()

    # Seed 5 default students if not present
    student_count = db.query(User).filter(User.role == "student").count()
    if student_count < 5:
        from app.models.student import (
            StudentProfile,
            Course,
            StudentEnrollment,
            Notification,
            MasteryRecord
        )
        from app.models.syllabus import Syllabus

        students_data = [
            ("student1@college.edu", "Aarav Sharma", "21CS001", "A"),
            ("student2@college.edu", "Diya Patel", "21CS015", "A"),
            ("student3@college.edu", "Kavya Nair", "21CS028", "B"),
            ("student4@college.edu", "Rohan Iyer", "21CS042", "A"),
            ("student5@college.edu", "Siddharth Verma", "21CS056", "B"),
        ]

        created_students = []
        for email, full_name, reg_no, sec in students_data:
            existing = db.query(User).filter(User.email == email).first()
            if not existing:
                st_user = User(
                    email=email,
                    password_hash=hash_password("Student@123"),
                    full_name=full_name,
                    role="student",
                    department="Computer Science & Engineering",
                    designation="Student",
                    employee_id=reg_no,
                    phone="+91 98765 1111" + reg_no[-1],
                    is_active=True
                )
                db.add(st_user)
                db.flush()

                st_profile = StudentProfile(
                    user_id=st_user.id,
                    register_number=reg_no,
                    programme="B.E. Computer Science & Engineering",
                    semester="IV Semester",
                    section=sec,
                    batch_year="2023-2027",
                    academic_standing="Good"
                )
                db.add(st_profile)
                created_students.append(st_user)
            else:
                created_students.append(existing)

        db.commit()

        # Find a faculty member and syllabus for courses
        faculty_user = db.query(User).filter(User.role == "faculty").first()
        faculty_id = faculty_user.id if faculty_user else None

        # Look for syllabuses
        syl_cs = db.query(Syllabus).filter(Syllabus.original_filename.like("%Data%")).first()
        if not syl_cs:
            syl_cs = db.query(Syllabus).first()

        syl_r = db.query(Syllabus).filter(Syllabus.original_filename.like("%R_%")).first()
        if not syl_r:
            syl_r = syl_cs

        # Seed 2 Courses if not already present
        c1 = db.query(Course).filter(Course.course_code == "21CS42").first()
        if not c1:
            c1 = Course(
                course_code="21CS42",
                course_name="Advanced Data Structures & Algorithms",
                department="Computer Science & Engineering",
                semester="IV Semester",
                academic_year="2025-2026",
                faculty_id=faculty_id,
                syllabus_id=syl_cs.id if syl_cs else None,
                description="Comprehensive study of advanced linear and non-linear data structures, amortized analysis, flow networks, and NP-completeness.",
                is_active=True
            )
            db.add(c1)
            db.flush()

        c2 = db.query(Course).filter(Course.course_code == "CS204").first()
        if not c2:
            c2 = Course(
                course_code="CS204",
                course_name="R Programming & Data Analysis",
                department="Computer Science & Engineering",
                semester="IV Semester",
                academic_year="2025-2026",
                faculty_id=faculty_id,
                syllabus_id=syl_r.id if syl_r else None,
                description="Exploration of R programming language fundamentals, data frames, statistical tests, and ggplot2 visual analytics.",
                is_active=True
            )
            db.add(c2)
            db.flush()

        db.commit()

        # Enroll all students in both courses
        for st in created_students:
            for crs in [c1, c2]:
                enrollment_exists = db.query(StudentEnrollment).filter(
                    StudentEnrollment.student_id == st.id,
                    StudentEnrollment.course_id == crs.id
                ).first()
                if not enrollment_exists:
                    prof = db.query(StudentProfile).filter(StudentProfile.user_id == st.id).first()
                    en = StudentEnrollment(
                        student_id=st.id,
                        course_id=crs.id,
                        semester="IV Semester",
                        section=prof.section if prof else "A",
                        academic_year="2025-2026",
                        status="enrolled"
                    )
                    db.add(en)

        # Seed initial notifications for student1
        first_student = created_students[0]
        notif_exists = db.query(Notification).filter(Notification.user_id == first_student.id).count()
        if notif_exists == 0:
            db.add_all([
                Notification(
                    user_id=first_student.id,
                    title="Diagnostic Assessment Assigned",
                    message="Dr. Rajesh Raman has assigned Diagnostic Test 1 for 21CS42. Please complete it by Friday.",
                    notification_type="assessment_assigned",
                    link_tab="student-dashboard",
                    is_read=False
                ),
                Notification(
                    user_id=first_student.id,
                    title="Course Material Uploaded",
                    message="Lecture slides for Unit 2: Advanced Graph Algorithms & Flow Networks are now available.",
                    notification_type="system",
                    link_tab="student-courses",
                    is_read=False
                ),
                Notification(
                    user_id=first_student.id,
                    title="Remedial Activity Recommended",
                    message="Based on your topic mastery in Dynamic Programming, review Cormen Ch. 15 reading notes.",
                    notification_type="remedial_plan",
                    link_tab="student-dashboard",
                    is_read=True
                )
            ])

        # Seed initial mastery records for student1
        m_exists = db.query(MasteryRecord).filter(
            MasteryRecord.student_id == first_student.id,
            MasteryRecord.course_id == c1.id
        ).count()
        if m_exists == 0:
            db.add_all([
                MasteryRecord(
                    student_id=first_student.id,
                    course_id=c1.id,
                    mastery_level_type="course",
                    target_identifier="21CS42",
                    numerical_score=68.5,
                    mastery_category="Proficient"
                ),
                MasteryRecord(
                    student_id=first_student.id,
                    course_id=c1.id,
                    mastery_level_type="unit",
                    target_identifier="Unit 1",
                    numerical_score=85.0,
                    mastery_category="Advanced"
                ),
                MasteryRecord(
                    student_id=first_student.id,
                    course_id=c1.id,
                    mastery_level_type="unit",
                    target_identifier="Unit 2",
                    numerical_score=72.0,
                    mastery_category="Proficient"
                ),
                MasteryRecord(
                    student_id=first_student.id,
                    course_id=c1.id,
                    mastery_level_type="unit",
                    target_identifier="Unit 3",
                    numerical_score=52.0,
                    mastery_category="Developing"
                ),
                MasteryRecord(
                    student_id=first_student.id,
                    course_id=c1.id,
                    mastery_level_type="unit",
                    target_identifier="Unit 4",
                    numerical_score=64.0,
                    mastery_category="Proficient"
                ),
                MasteryRecord(
                    student_id=first_student.id,
                    course_id=c1.id,
                    mastery_level_type="unit",
                    target_identifier="Unit 5",
                    numerical_score=45.0,
                    mastery_category="Developing"
                )
            ])

        db.commit()

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email and password, returning JWT access token."""
    # Ensure default accounts are present
    seed_default_users_if_needed(db)

    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact the administrator."
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role, "email": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Retrieve the currently authenticated user's profile."""
    return current_user

@router.post("/seed")
def manual_seed(db: Session = Depends(get_db)):
    """Explicitly trigger default user seed."""
    seed_default_users_if_needed(db)
    return {"message": "Users verified and seeded successfully."}

@router.post("/refresh")
@router.post("/refresh/", include_in_schema=False)
def refresh_token(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
):
    """
    Generate a fresh JWT access token. Accepts valid or recently-expired Bearer token.
    """
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token decode error or corrupted token.")

    user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated."
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role, "email": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

