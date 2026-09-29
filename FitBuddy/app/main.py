"""FitBuddy - AI Fitness Plan Generator Main Application Entrypoint.

Configures FastAPI, mounts static assets, registers Jinja2 templates,
and includes application routers.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown tasks."""
    # Ensure database tables/schema metadata are created on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="FitBuddy – AI Fitness Plan Generator",
    description="Naan Mudhalvan Academic Project - AI Fitness & Nutrition Plan Generator using Google Gemini Models.",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include main router
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
