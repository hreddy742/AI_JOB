"""Resume API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_current_token, get_db
from core.security import TokenPayload
from schemas.resume import (
    CoverLetterRequest,
    CoverLetterResponse,
    ImproveBulletRequest,
    ResumeBuildRequest,
    ResumeEditRequest,
    ResumeResponse,
    ResumeUpdateRequest,
    ResumeVersionResponse,
    ReviewResponse,
    TailorRequest,
    TailorTaskResponse,
    TailoredResumeResponse,
)
from services.cover_letter_service import get_cover_letter
from services.resume_service import (
    build_resume,
    create_tailoring_task,
    delete_resume,
    edit_resume_content,
    export_tailored_resume_pdf,
    generate_cover_letter_for_resume,
    get_or_generate_review,
    get_resume,
    get_resume_autofill_profile,
    get_resume_download_url,
    get_tailored_resume,
    get_tailoring_task_status,
    improve_bullet_text,
    list_resume_versions,
    list_resumes,
    list_tailored_resumes,
    permanent_delete_resume,
    restore_resume_version_number,
    update_resume_metadata,
    upload_resume,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume_endpoint(
    file: UploadFile = File(...),
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    return await upload_resume(db, token, file)


@router.get("", response_model=list[ResumeResponse])
async def list_resumes_endpoint(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeResponse]:
    return await list_resumes(db, token)


@router.get("/{id}", response_model=ResumeResponse)
async def get_resume_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    return await get_resume(db, token, id)


@router.get("/{id}/download")
async def get_resume_download_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    return {"url": await get_resume_download_url(db, token, id)}


@router.put("/{id}", response_model=ResumeResponse)
async def update_resume_endpoint(
    id: UUID,
    payload: ResumeUpdateRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    return await update_resume_metadata(db, token, id, payload.label, payload.is_primary)


@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_resume_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await delete_resume(db, token, id)
    return {"status": "deleted"}


@router.delete("/{id}/permanent", status_code=status.HTTP_200_OK)
async def delete_resume_permanent_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await permanent_delete_resume(db, token, id)
    return {"status": "deleted"}


@router.post("/{id}/tailor", response_model=TailorTaskResponse)
async def tailor_resume_endpoint(
    id: UUID,
    payload: TailorRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> TailorTaskResponse:
    task_id = await create_tailoring_task(db, token, id, payload.job_id)
    return TailorTaskResponse(task_id=task_id)


@router.post("/tailor", response_model=TailorTaskResponse)
async def tailor_resume_legacy_endpoint(
    payload: TailorRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> TailorTaskResponse:
    if payload.resume_id is None:
        raise HTTPException(status_code=400, detail="resume_id is required")
    task_id = await create_tailoring_task(db, token, payload.resume_id, payload.job_id)
    return TailorTaskResponse(task_id=task_id)


@router.get("/tailor/{task_id}/status")
async def tailor_status_endpoint(task_id: str) -> dict:
    return await get_tailoring_task_status(task_id)


@router.get("/{id}/tailored", response_model=list[TailoredResumeResponse])
async def list_tailored_for_resume_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[TailoredResumeResponse]:
    return await list_tailored_resumes(db, token, id)


@router.get("/tailored/{id}", response_model=TailoredResumeResponse)
async def get_tailored_resume_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> TailoredResumeResponse:
    return await get_tailored_resume(db, token, id)


@router.post("/tailored/{id}/export")
async def export_tailored_resume_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    stream = await export_tailored_resume_pdf(db, token, id)
    return StreamingResponse(stream, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=tailored-{id}.pdf"})


@router.post("/{id}/cover-letter", response_model=CoverLetterResponse)
async def generate_cover_letter_endpoint(
    id: UUID,
    payload: CoverLetterRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> CoverLetterResponse:
    created = await generate_cover_letter_for_resume(db, token, id, payload)
    return CoverLetterResponse.model_validate(created)


@router.get("/cover-letters/{id}", response_model=CoverLetterResponse)
async def get_cover_letter_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> CoverLetterResponse:
    item = await get_cover_letter(db, UUID(token.sub), UUID(token.tenant_id), id)
    return CoverLetterResponse.model_validate(item)


@router.get("/{id}/review", response_model=ReviewResponse)
async def get_resume_review_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    item = await get_or_generate_review(db, token, id, force_new=False)
    return ReviewResponse.model_validate(item)


@router.post("/{id}/review", response_model=ReviewResponse)
async def regenerate_resume_review_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    item = await get_or_generate_review(db, token, id, force_new=True)
    return ReviewResponse.model_validate(item)


@router.post("/{id}/edit", response_model=ResumeResponse)
async def edit_resume_endpoint(
    id: UUID,
    payload: ResumeEditRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    summary = payload.change_summary or f"Edited {payload.section}:{payload.field_path}"
    return await edit_resume_content(db, token, id, payload.original_value, payload.new_value, summary)


@router.get("/{id}/versions", response_model=list[ResumeVersionResponse])
async def list_versions_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeVersionResponse]:
    rows = await list_resume_versions(db, token, id)
    return [ResumeVersionResponse.model_validate(row) for row in rows]


@router.post("/{id}/versions/{n}/restore", response_model=ResumeResponse)
async def restore_version_endpoint(
    id: UUID,
    n: int,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    return await restore_resume_version_number(db, token, id, n)


@router.post("/{id}/improve-bullet")
async def improve_bullet_endpoint(
    id: UUID,
    payload: ImproveBulletRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    return await improve_bullet_text(db, token, id, payload.original, payload.target_role)


@router.post("/build", response_model=ResumeResponse)
async def build_resume_endpoint(
    payload: ResumeBuildRequest,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    return await build_resume(db, token, payload.payload)


@router.get("/{id}/autofill-profile")
async def get_autofill_profile_endpoint(
    id: UUID,
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_resume_autofill_profile(db, token, id)
