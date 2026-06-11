from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.sessions import router as sessions_router
from app.api.nlp import router as nlp_router
from app.ws.live_audio import router as ws_router
from app.database import init_db


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(nlp_router, prefix="/api/nlp", tags=["nlp"])
    app.include_router(ws_router)

    @app.on_event("startup")
    async def on_startup():
        init_db()

    return app


app = create_app()
