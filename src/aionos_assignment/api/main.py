"""
FastAPI application entry point for the Airline Disruption Resolution Agent.

Run with:
    uvicorn aionos_assignment.api.main:app --reload
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aionos_assignment.api.routes import admin, chat, sessions
from aionos_assignment.config import settings
from aionos_assignment.db.database import init_db
from aionos_assignment.db.seed import seed


# ─── Lifespan (startup / shutdown) ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Code before 'yield' runs on startup; code after runs on shutdown.
    """
    # Startup
    init_db()
    seed()
    yield


# ─── App Init ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    description="AI-powered customer support agent for airline disruption scenarios.",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Templates (for HTML UI) ─────────────────────────────────────────────────
# Resolve templates dir relative to project root
_base_dir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
_templates_dir = os.path.join(_base_dir, "templates")
templates = Jinja2Templates(directory=_templates_dir)

# ─── Routes ──────────────────────────────────────────────────────────────────
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(admin.router)


# ─── Template Route (HTML UI) ────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request):
    """Serve the HTML chat interface."""
    return templates.TemplateResponse(request=request, name="index.html", context={})


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "app": settings.app_name}

