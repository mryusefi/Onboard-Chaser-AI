import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, onboarding, candidates


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only create tables if not in test mode
    if os.environ.get("TESTING") != "1":
        Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(onboarding.router, prefix=settings.API_V1_PREFIX)
app.include_router(candidates.router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}
