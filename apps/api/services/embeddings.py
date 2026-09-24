"""Local embedding helpers for query/passage encoding."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog

from core.config import settings

logger = structlog.get_logger()


def _resolve_bge_model_name() -> str:
    """Return a BGEM3-compatible model name for FlagEmbedding."""

    configured = (settings.EMBEDDING_MODEL or "").strip()
    if configured and "bge-m3" in configured.lower():
        return configured
    if configured:
        logger.warning(
            "embedding_model_override_ignored",
            configured_model=configured,
            forced_model="BAAI/bge-m3",
            reason="BGEM3FlagModel requires a bge-m3 checkpoint",
        )
    return "BAAI/bge-m3"


def _materialize_model_on_cpu(model: Any) -> Any:
    """Force any lazy/meta BGE weights onto CPU before first encode."""

    inner = getattr(model, "model", None)
    if inner is None:
        return model

    try:
        import torch
    except Exception:
        if hasattr(inner, "to"):
            model.model = inner.to("cpu")
        return model

    has_meta_params = False
    if hasattr(inner, "parameters"):
        try:
            has_meta_params = any(getattr(param, "is_meta", False) for param in inner.parameters())
        except Exception:
            has_meta_params = False

    if has_meta_params and hasattr(inner, "to_empty"):
        inner = inner.to_empty(device="cpu")
    elif has_meta_params:
        for module in inner.modules():
            for name, param in list(getattr(module, "_parameters", {}).items()):
                if param is None or not getattr(param, "is_meta", False):
                    continue
                module._parameters[name] = torch.nn.Parameter(
                    torch.empty(param.shape, device="cpu", dtype=param.dtype),
                    requires_grad=param.requires_grad,
                )

    if hasattr(inner, "to"):
        inner = inner.to("cpu")
    model.model = inner
    return model


@lru_cache(maxsize=1)
def get_model() -> Any:
    """Return cached sentence-transformers model."""

    from FlagEmbedding import BGEM3FlagModel

    model_name = _resolve_bge_model_name()
    try:
        model = BGEM3FlagModel(model_name, use_fp16=False, device="cpu")
    except TypeError:
        model = BGEM3FlagModel(model_name, use_fp16=False)
    return _materialize_model_on_cpu(model)


def _dense_rows(vectors: Any) -> list[Any]:
    """Normalize BGE dense output to a row-oriented structure."""

    if vectors is None:
        return []
    shape = getattr(vectors, "shape", None)
    if shape is not None:
        if len(shape) == 0 or int(shape[0]) == 0:
            return []
        if hasattr(vectors, "tolist"):
            vectors = vectors.tolist()
            if len(shape) == 1:
                return [vectors]
            return vectors
        if len(shape) == 1:
            return [vectors]
        return [vectors[idx] for idx in range(int(shape[0]))]
    if hasattr(vectors, "tolist"):
        vectors = vectors.tolist()
    if not isinstance(vectors, list):
        return [[float(vectors)]]
    if not vectors:
        return []
    first = vectors[0]
    if isinstance(first, list):
        return vectors
    return [vectors]


def _vector_to_list(vector: Any) -> list[float]:
    """Convert one dense row to a Python float list."""

    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(value) for value in list(vector)]


def _prepare_text(text: str, *, label: str) -> str:
    """Normalize user text before encoding."""

    payload = (text or "").strip()
    if not payload:
        raise ValueError(f"{label} requires non-empty text")
    return payload[:2048]


def _encode_dense(texts: list[str], *, batch_size: int) -> list[list[float]]:
    """Encode text with defensive handling around BGE-M3 return shapes."""

    if not texts:
        return []

    try:
        result = get_model().encode(
            texts,
            batch_size=batch_size,
            max_length=512,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense = result.get("dense_vecs") if isinstance(result, dict) else result
        shape = getattr(dense, "shape", None)
        if dense is None:
            raise ValueError("BGE-M3 returned None for dense_vecs")
        if shape is not None and (len(shape) == 0 or int(shape[0]) == 0):
            sample = texts[0][:50] if texts else ""
            raise ValueError(f"BGE-M3 returned empty tensor with shape {shape} for input: {sample}")
        rows = _dense_rows(dense)
        if not rows:
            sample = texts[0][:50] if texts else ""
            raise ValueError(f"BGE-M3 returned empty dense_vecs for input: {sample}")
        if len(rows) != len(texts):
            raise ValueError(f"BGE-M3 returned {len(rows)} dense vectors for {len(texts)} inputs")
        return [_vector_to_list(row) for row in rows]
    except IndexError as exc:
        sample = texts[0][:80] if texts else ""
        raise ValueError(
            f"BGE-M3 IndexError for {len(texts)} text(s), first sample length {len(sample)}: {exc}"
        ) from exc
    except Exception as exc:
        logger.error(
            "embedding_encode_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            text_count=len(texts),
            sample=(texts[0][:80] if texts else ""),
        )
        raise


def embed_query(text: str) -> list[float]:
    """Embed query text synchronously for legacy call sites."""

    payload = _prepare_text(text, label="embed_query")
    try:
        model = get_model()
        model = _materialize_model_on_cpu(model)
        result = model.encode(
            [payload],
            batch_size=1,
            max_length=512,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense = result.get("dense_vecs") if isinstance(result, dict) else result
        shape = getattr(dense, "shape", None)
        if dense is None:
            raise ValueError("BGE-M3 returned None for dense_vecs")
        if shape is not None and (len(shape) == 0 or int(shape[0]) == 0):
            raise ValueError(f"BGE-M3 returned empty tensor with shape {shape}")
        rows = _dense_rows(dense)
        if len(rows) == 0:
            raise ValueError(f"BGE-M3 returned empty dense_vecs for input: {payload[:50]}")
        return _vector_to_list(rows[0])
    except IndexError as exc:
        raise ValueError(f"BGE-M3 IndexError on query text of length {len(payload)}: {exc}") from exc
    except Exception as exc:
        logger.error(
            "embedding_encode_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            text_count=1,
            sample=payload[:80],
        )
        raise


def embed_passage(text: str) -> list[float]:
    """Embed passage text synchronously for legacy call sites."""

    payload = _prepare_text(text, label="embed_passage")
    try:
        model = get_model()
        model = _materialize_model_on_cpu(model)
        result = model.encode(
            [payload],
            batch_size=1,
            max_length=512,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense = result.get("dense_vecs") if isinstance(result, dict) else result
        shape = getattr(dense, "shape", None)
        if dense is None:
            raise ValueError("BGE-M3 returned None for dense_vecs")
        if shape is not None and (len(shape) == 0 or int(shape[0]) == 0):
            raise ValueError(f"BGE-M3 returned empty tensor with shape {shape}")
        rows = _dense_rows(dense)
        if len(rows) == 0:
            raise ValueError(f"BGE-M3 returned empty dense_vecs for input: {payload[:50]}")
        return _vector_to_list(rows[0])
    except IndexError as exc:
        raise ValueError(f"BGE-M3 IndexError on text of length {len(payload)}: {exc}") from exc
    except Exception as exc:
        logger.error(
            "embedding_encode_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            text_count=1,
            sample=payload[:80],
        )
        raise


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed passage batch synchronously for legacy call sites."""

    if not texts:
        return []

    payload: list[str] = []
    valid_indices: list[int] = []
    for idx, text in enumerate(texts):
        normalized = str(text or "").strip()
        if not normalized:
            continue
        payload.append(normalized[:2048])
        valid_indices.append(idx)
    if not payload:
        raise ValueError("embed_batch received all empty texts")

    output: list[list[float] | None] = [None] * len(texts)
    offset = 0
    vectors: list[list[float]] = []
    for start in range(0, len(payload), 16):
        chunk = payload[start : start + 16]
        encoded = _encode_dense(chunk, batch_size=16)
        if len(encoded) != len(chunk):
            raise ValueError(f"BGE-M3 returned {len(encoded)} vectors for batch of {len(chunk)} inputs")
        for row_index, vector in enumerate(encoded):
            output[valid_indices[offset + row_index]] = vector
        offset += len(chunk)
        vectors.extend(encoded)
    return [vector for vector in output if vector is not None]
