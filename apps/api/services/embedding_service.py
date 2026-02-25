"""Embedding service using sentence-transformers/all-MiniLM-L6-v2.

Model is loaded once at startup and reused. Embeddings are
384-dimensional float32 vectors. Used for:

Job description similarity (matching + dedup)
Resume semantic search
Copilot context retrieval
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from core.config import settings

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Load model once, reuse across all requests."""

    global _model
    if _model is None:
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


async def embed_text(text: str) -> list[float]:
    """Generate a normalized embedding for a single text."""

    model = get_embedding_model()
    loop = asyncio.get_running_loop()
    embedding: list[float] = await loop.run_in_executor(
        None,
        lambda: model.encode(text[:4096], normalize_embeddings=True).tolist(),
    )
    return embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate normalized embeddings for multiple text inputs."""

    model = get_embedding_model()
    loop = asyncio.get_running_loop()
    embeddings: list[list[float]] = await loop.run_in_executor(
        None,
        lambda: model.encode(texts, normalize_embeddings=True, batch_size=32).tolist(),
    )
    return embeddings


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""

    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


async def store_job_embedding(job_id: str, description: str, chroma_client: Any) -> str:
    """Generate and store a job description embedding in ChromaDB."""

    embedding = await embed_text(description)
    collection = chroma_client.get_or_create_collection("job_descriptions")
    collection.upsert(ids=[job_id], embeddings=[embedding], metadatas=[{"job_id": job_id}])
    return job_id


async def store_resume_embedding(
    resume_id: str,
    resume_text: str,
    chroma_client: Any,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Generate and store a resume embedding in ChromaDB."""

    embedding = await embed_text(resume_text)
    collection = chroma_client.get_or_create_collection("resumes")
    meta = {"resume_id": resume_id, **(metadata or {})}
    collection.upsert(ids=[resume_id], embeddings=[embedding], metadatas=[meta])
    return resume_id


async def find_matching_jobs(
    resume_id: str,
    chroma_client: Any,
    n_results: int = 50,
    min_score: float = 0.6,
) -> list[dict[str, float | str]]:
    """Find semantically matching jobs for a stored resume embedding."""

    resume_collection = chroma_client.get_or_create_collection("resumes")
    result = resume_collection.get(ids=[resume_id], include=["embeddings"])
    if not result.get("embeddings"):
        return []

    resume_embedding = result["embeddings"][0]
    job_collection = chroma_client.get_or_create_collection("job_descriptions")

    matches = job_collection.query(
        query_embeddings=[resume_embedding],
        n_results=n_results,
        include=["distances", "metadatas"],
    )

    output: list[dict[str, float | str]] = []
    ids = matches.get("ids", [[]])[0]
    distances = matches.get("distances", [[]])[0]
    metadatas = matches.get("metadatas", [[]])[0]

    for job_id, distance, _metadata in zip(ids, distances, metadatas, strict=False):
        score = 1.0 - float(distance)
        if score >= min_score:
            output.append({"job_id": str(job_id), "similarity_score": round(score, 4)})

    return sorted(output, key=lambda item: float(item["similarity_score"]), reverse=True)
