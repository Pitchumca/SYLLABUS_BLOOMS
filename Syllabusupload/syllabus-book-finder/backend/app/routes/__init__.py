from app.routes.upload import router as upload_router
from app.routes.books import router as books_router
from app.routes.search import router as search_router
from app.routes.analytics import router as analytics_router
from app.routes.export import router as export_router

__all__ = ["upload_router", "books_router", "search_router", "analytics_router", "export_router"]
