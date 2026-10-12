from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
import datetime

class StudentProfileBase(BaseModel):
    register_number: str
    programme: str
    semester: str
    section: str
    batch_year: str
    academic_standing: str = "Good"

class StudentProfileResponse(StudentProfileBase):
    id: int
    user_id: int
    full_name: str
    email: str
    department: str
    created_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    notification_type: str
    link_tab: Optional[str] = "student-dashboard"
    is_read: bool
    created_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CourseSummaryResponse(BaseModel):
    id: int
    course_code: str
    course_name: str
    department: str
    semester: str
    academic_year: str
    faculty_name: str
    faculty_email: str
    unit_count: int = 5
    progress_percentage: float = 0.0
    mastery_percentage: float = 0.0
    mastery_category: str = "Developing"
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class UnitLearningItem(BaseModel):
    number: str
    title: str
    topics: str
    completion_percentage: float = 0.0
    mastery_score: float = 0.0
    mastery_category: str = "Needs Support"

class LearningMaterialItem(BaseModel):
    id: int
    title: str
    material_type: str # "lecture_slide", "lecture_note", "prescribed_textbook", "reference_book"
    format: str # "pptx", "pdf", "book"
    meta_info: Optional[str] = None
    url: Optional[str] = None

class CourseLearningDetailResponse(BaseModel):
    id: int
    course_code: str
    course_name: str
    department: str
    semester: str
    academic_year: str
    faculty_name: str
    faculty_email: str
    description: Optional[str] = None
    
    # Curriculum breakdown
    units: List[UnitLearningItem] = []
    overall_unit_completion: float = 0.0
    overall_course_mastery: float = 0.0
    mastery_category: str = "Developing"
    
    # Materials and outcomes
    materials: List[LearningMaterialItem] = []
    course_outcomes: List[Dict[str, Any]] = []
    bloom_distribution: Dict[str, int] = {}
    
    # Assessment summary
    pending_assessments_count: int = 0
    completed_assessments_count: int = 0
    
    # Recommendation
    recommended_next_topic: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

class StudentDashboardResponse(BaseModel):
    student_profile: StudentProfileResponse
    enrolled_courses: List[CourseSummaryResponse]
    pending_assessments: List[Dict[str, Any]] = []
    recently_completed_assessments: List[Dict[str, Any]] = []
    current_mastery_percentage: float = 0.0
    current_mastery_category: str = "Developing"
    weak_topics: List[Dict[str, Any]] = []
    recommended_learning_activities: List[Dict[str, Any]] = []
    upcoming_deadlines: List[Dict[str, Any]] = []
    progress_trend: List[Dict[str, Any]] = []
    co_attainment_summary: List[Dict[str, Any]] = []
    notifications: List[NotificationResponse] = []

    model_config = ConfigDict(from_attributes=True)
