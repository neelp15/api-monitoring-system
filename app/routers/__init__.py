
from fastapi import FastAPI

from app.core.config import settings
from app.routers.monitors import router as monitors_router

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API availability monitoring and incident alert system.",
)


@app.get("/health/live", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Return whether the API process is running."""
    return {
        "status": "ok",
        "application": settings.app_name,
        "environment": settings.app_env,
    }


app.include_router(monitors_router)
