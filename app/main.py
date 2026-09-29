from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.models.user import User
from app.models.resume import Resume
from app.models.interview import Interview
from app.models.resume_chunk import ResumeChunk

from app.routers.user import router as user_router
from app.routers.resume import router as resume_router
from app.routers.interview import router as interview_router
from app.routers import dashboard as dashboard_router
from app.routers import profile


app = FastAPI(
    title="HireMind API",
    version="1.0.0"
)


# CORS - local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


Base.metadata.create_all(bind=engine)

app.include_router(user_router)
app.include_router(resume_router)
app.include_router(interview_router)
app.include_router(dashboard_router.router)
app.include_router(profile.router)


@app.get("/")
def home():
    return {
        "message": "HireMind Backend Running 🚀"
    }