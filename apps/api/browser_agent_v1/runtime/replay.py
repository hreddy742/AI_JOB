"""Replay bundle helpers for Browser Agent V1."""

from __future__ import annotations

from typing import Any


def build_replay_bundle(
    *,
    run: Any,
    steps: list[Any],
    events: list[Any],
    artifacts: list[Any],
    pause_requests: list[Any],
) -> dict[str, Any]:
    """Build a developer-facing replay bundle from persisted run data."""

    return {
        "run": {
            "id": str(run.id),
            "status": str(run.status),
            "current_state": str(run.current_state),
            "provider": str(run.ats_type or run.provider or "generic"),
            "entry_url": str(run.entry_url),
            "current_url": str(run.current_url or run.entry_url),
            "feature_flag_snapshot": dict(run.feature_flag_snapshot or {}),
        },
        "steps": [
            {
                "sequence": int(step.sequence),
                "page_state": str(step.page_state),
                "action_kind": str(step.action_kind),
                "status": str(step.status),
                "selector": str(step.selector or ""),
                "detail": str(step.detail or ""),
                "payload": dict(step.payload or {}),
                "result": dict(step.result or {}),
            }
            for step in steps
        ],
        "events": [
            {
                "event_type": str(event.event_type),
                "from_state": str(event.from_state or ""),
                "to_state": str(event.to_state or ""),
                "level": str(event.level),
                "message": str(event.message),
                "payload": dict(event.payload or {}),
            }
            for event in events
        ],
        "pause_requests": [
            {
                "reason_code": str(row.reason_code),
                "prompt": str(row.prompt),
                "requested_data": dict(row.requested_data or {}),
                "response_data": dict(row.response_data or {}),
                "status": str(row.status),
            }
            for row in pause_requests
        ],
        "artifacts": [
            {
                "artifact_type": str(artifact.artifact_type),
                "storage_path": str(artifact.storage_path or ""),
                "content_type": str(artifact.content_type),
                "metadata_json": dict(artifact.metadata_json or {}),
            }
            for artifact in artifacts
        ],
    }
