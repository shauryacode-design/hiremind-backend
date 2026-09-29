from sqlalchemy.orm import Session

from app.models.resume import Resume
from app.models.resume_chunk import ResumeChunk
from app.services.ai.embeddings import generate_embedding
from app.services.rag.resume_chunker import chunk_resume_text


def ingest_resume_chunks(
    db: Session,
    resume: Resume,
) -> int:

    if not resume.extracted_text:
        return 0

    # Remove old chunks if this resume is being re-processed.
    db.query(ResumeChunk).filter(
        ResumeChunk.resume_id == resume.id
    ).delete()

    chunks = chunk_resume_text(resume.extracted_text)

    for index, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk)

        db.add(
            ResumeChunk(
                resume_id=resume.id,
                chunk_index=index,
                content=chunk,
                embedding=embedding,
            )
        )

    db.commit()

    return len(chunks)