from app.routes.admin import router as admin_router
from app.routes.admin_users import router as admin_users_router
from app.routes.auth import router as auth_router
from app.routes.behavior_metrics import router as behavior_metrics_router
from app.routes.behaviors import router as behaviors_router
from app.routes.leads import router as leads_router

__all__ = [
    "leads_router",
    "behaviors_router",
    "behavior_metrics_router",
    "admin_router",
    "auth_router",
    "admin_users_router",
]
