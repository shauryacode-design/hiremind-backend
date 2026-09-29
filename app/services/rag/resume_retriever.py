from sqlalchemy.orm import Session

from app.models.resume_chunk import ResumeChunk
from app.services.ai.embeddings import generate_embedding


def retrieve_relevant_chunks(
    db: Session,
    resume_id: int,
    query: str,
    limit: int = 3,
) -> list[str]:

    query_embedding = generate_embedding(query)

    chunks = (
        db.query(ResumeChunk)
        .filter(ResumeChunk.resume_id == resume_id)
        .order_by(
            ResumeChunk.embedding.cosine_distance(query_embedding)
        )
        .limit(limit)
        .all()
    )

    return [chunk.content for chunk in chunks]