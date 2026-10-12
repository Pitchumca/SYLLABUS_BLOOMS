from app.models.syllabus import Syllabus
from app.models.book import Book
from app.models.search_result import SearchResult
from app.models.cache import SearchCache
from app.models.export_history import ExportHistory
from app.models.user import User
from app.models.content_file import ContentFile
from app.models.question_paper import QuestionPaper, Question
from app.models.student import (
    Course,
    StudentProfile,
    StudentEnrollment,
    Notification,
    Assessment,
    AssessmentAssignment,
    StudentAttempt,
    StudentResponse,
    AdaptiveQuestionLog,
    MasteryRecord,
    RemedialLearningPlan,
    LearningPlanResource,
    Reassessment
)

from app.models.template_and_resource import (
    QuestionPaperTemplate,
    TemplateVersion,
    ExtractedBlueprint,
    BlueprintSectionModel,
    BlueprintQuestionSlotModel,
    SlotQuestionTypeModel,
    ResourceRecord,
    StoredDocument,
    DocumentChunkModel,
    RightsVerificationLog,
    DownloadAuditLog
)

from app.models.discovery_rag import (
    CourseResource,
    BookMetadata,
    BookAuthor,
    BookSource,
    BookFile,
    DownloadJobModel,
    ExtractionJob,
    RAGDocument,
    RAGChunk,
    SyllabusBookMapping,
    ResourceVerificationLog
)

__all__ = [
    "Syllabus", 
    "Book", 
    "SearchResult", 
    "SearchCache", 
    "ExportHistory",
    "User",
    "ContentFile",
    "QuestionPaper",
    "Question",
    "Course",
    "StudentProfile",
    "StudentEnrollment",
    "Notification",
    "Assessment",
    "AssessmentAssignment",
    "StudentAttempt",
    "StudentResponse",
    "AdaptiveQuestionLog",
    "MasteryRecord",
    "RemedialLearningPlan",
    "LearningPlanResource",
    "Reassessment",
    "QuestionPaperTemplate",
    "TemplateVersion",
    "ExtractedBlueprint",
    "BlueprintSectionModel",
    "BlueprintQuestionSlotModel",
    "SlotQuestionTypeModel",
    "ResourceRecord",
    "StoredDocument",
    "DocumentChunkModel",
    "RightsVerificationLog",
    "DownloadAuditLog",
    "CourseResource",
    "BookMetadata",
    "BookAuthor",
    "BookSource",
    "BookFile",
    "DownloadJobModel",
    "ExtractionJob",
    "RAGDocument",
    "RAGChunk",
    "SyllabusBookMapping",
    "ResourceVerificationLog"
]
