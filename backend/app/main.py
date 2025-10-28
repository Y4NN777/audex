from fastapi import FastAPI

from app.api.v1.routes import api_router
from app.core.config import settings


def create_application() -> FastAPI:
    """FastAPI application factory."""
    application = FastAPI(
        title="AUDEX API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)
    return application


app = create_application()


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
