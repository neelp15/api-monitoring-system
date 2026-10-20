from fastapi import FastAPI

from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers.checks import router as checks_router
from app.routers.monitors import router as monitors_router
from app.routers.incidents import router as incidents_router

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API availability monitoring and incident alert system.",
)

BASE_DIR = Path(__file__).resolve().parent

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse(BASE_DIR / "templates" / "dashboard.html")


@app.get("/health/live", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "application": settings.app_name,
        "environment": settings.app_env,
    }


app.include_router(monitors_router)
app.include_router(checks_router)
app.include_router(incidents_router)
