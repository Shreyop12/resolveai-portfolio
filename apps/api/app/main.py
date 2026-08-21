from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.drafts import router as drafts_router
from app.api.routes.draft_evaluations import router as draft_evaluations_router
from app.api.routes.evaluations import router as evaluations_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.model_selection import router as model_selection_router
from app.api.routes.support import router as support_router
from app.api.routes.triage import router as triage_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="ResolveAI API",
    version="0.1.0",
    description="AI customer-support copilot platform.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix="/api/v1")
app.include_router(support_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(model_selection_router, prefix="/api/v1")
app.include_router(drafts_router, prefix="/api/v1")
app.include_router(draft_evaluations_router, prefix="/api/v1")
app.include_router(evaluations_router, prefix="/api/v1")
app.include_router(triage_router, prefix="/api/v1")
