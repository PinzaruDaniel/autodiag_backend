from fastapi import FastAPI

from app.routes.audio import router as audio_router
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router

app = FastAPI(title="AutoDiag Backend")
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(audio_router)
