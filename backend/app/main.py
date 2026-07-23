from fastapi import FastAPI

from app.api.reports import router as reports_router
from app.core.config import get_settings

app = FastAPI(title="Rapports PDF — démo", version="0.1.0")
app.include_router(reports_router)


@app.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "environment": settings.environment}
