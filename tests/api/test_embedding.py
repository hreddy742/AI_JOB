from __future__ import annotations

import numpy as np
import pytest

from services import embedding_service


class FakeModel:
    def encode(self, texts, normalize_embeddings=True, batch_size=32):
        def one(_: str):
            v = np.ones(384, dtype=np.float32)
            if normalize_embeddings:
                v = v / np.linalg.norm(v)
            return v

        if isinstance(texts, list):
            return np.array([one(t) for t in texts])
        return one(texts)


@pytest.mark.asyncio
async def test_embed_text_returns_correct_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embedding_service, "get_embedding_model", lambda: FakeModel())
    embedding = await embedding_service.embed_text("Python engineer")
    assert len(embedding) == 384


@pytest.mark.asyncio
async def test_cosine_similarity_identical_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embedding_service, "get_embedding_model", lambda: FakeModel())
    a = await embedding_service.embed_text("x")
    b = await embedding_service.embed_text("x")
    sim = embedding_service.cosine_similarity(a, b)
    assert sim > 0.99


@pytest.mark.asyncio
async def test_find_matching_jobs_returns_sorted() -> None:
    class C:
        def __init__(self):
            self.data = {
                "resumes": {"r1": [1.0] * 384},
                "job_descriptions": {
                    "j1": [1.0] * 384,
                    "j2": [0.5] * 384,
                    "j3": [0.2] * 384,
                },
            }

        def get_or_create_collection(self, name):
            outer = self

            class Col:
                def get(self, ids, include):
                    emb = outer.data[name].get(ids[0])
                    return {"embeddings": [emb] if emb else []}

                def query(self, query_embeddings, n_results, include):
                    return {
                        "ids": [["j1", "j2", "j3"]],
                        "distances": [[0.01, 0.3, 0.7]],
                        "metadatas": [[{"job_id": "j1"}, {"job_id": "j2"}, {"job_id": "j3"}]],
                    }

            return Col()

    matches = await embedding_service.find_matching_jobs("r1", C(), n_results=3, min_score=0.2)
    assert matches[0]["job_id"] == "j1"
