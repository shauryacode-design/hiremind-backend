
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.interview import Interview

from app.database import get_db
from app.models.resume import Resume
from app.models.user import User
from app.utils.security import get_current_user
from app.services.resume_parser import extract_text_from_pdf
from app.services.ai.resume_analyzer import analyze_resume
from app.services.rag.resume_ingestion import ingest_resume_chunks
from app.services.rag.resume_retriever import retrieve_relevant_chunks

router = APIRouter(
    prefix="/resume",
    tags=["Resume"]
)


UPLOAD_DIR = Path("uploads/resumes")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check file extension
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    # Check MIME type
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a PDF."
        )

    # Generate a unique filename
    stored_filename = f"{uuid4()}.pdf"
    file_path = UPLOAD_DIR / stored_filename

    total_size = 0

    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Resume file must be smaller than 10 MB."
                    )

                buffer.write(chunk)

        extracted_text = extract_text_from_pdf(str(file_path))

        # Save resume information in PostgreSQL
        resume = Resume(
            user_id=current_user.id,
            filename=file.filename,
            file_path=str(file_path),
            extracted_text=extracted_text
        )

        db.add(resume)
        db.commit()
        db.refresh(resume)

        return {
            "message": "Resume uploaded successfully.",
            "resume_id": resume.id,
            "filename": resume.filename
        }

    except HTTPException:
        if file_path.exists():
            file_path.unlink()
        raise

    except Exception:
        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Failed to upload resume."
        )

    finally:
        await file.close()


@router.get("/")
def get_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resumes = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.id.desc())
        .all()
    )

    return {
        "message": "Resumes retrieved successfully.",
        "resumes": [
            {
                "id": resume.id,
                "filename": resume.filename,
                "analysis": resume.analysis,
            }
            for resume in resumes
        ]
    }

@router.delete("/{resume_id}")
def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        )
        .first()
    )

    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    # Prevent deletion if this resume has been used
    # by an interview.
    interview_exists = (
        db.query(Interview)
        .filter(Interview.resume_id == resume.id)
        .first()
    )

    if interview_exists:
        raise HTTPException(
            status_code=409,
            detail=(
                "This resume cannot be deleted because it has "
                "already been used in an interview."
            )
        )

    # Delete the physical PDF file
    file_path = Path(resume.file_path)

    if file_path.exists():
        file_path.unlink()

    # Delete the database record
    db.delete(resume)
    db.commit()

    return {
        "message": "Resume deleted successfully.",
        "resume_id": resume_id
    }

@router.post("/{resume_id}/analyze")
def analyze_uploaded_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        )
        .first()
    )

    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    if not resume.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="Resume text has not been extracted."
        )

    analysis = analyze_resume(resume.extracted_text)

    # Save AI analysis to PostgreSQL
    resume.analysis = analysis.model_dump()

    db.commit()
    db.refresh(resume)

    # Build RAG index for this resume
    chunk_count = ingest_resume_chunks(
        db=db,
        resume=resume
    )

    return {
        "resume_id": resume.id,
        "analysis": resume.analysis,
        "rag_chunks_created": chunk_count
    }

@router.get("/{resume_id}/rag-search")
def search_resume(
    resume_id: int,
    query: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == current_user.id
        )
        .first()
    )

    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    chunks = retrieve_relevant_chunks(
        db=db,
        resume_id=resume.id,
        query=query,
        limit=3
    )

    return {
        "resume_id": resume.id,
        "query": query,
        "relevant_chunks": chunks
    }