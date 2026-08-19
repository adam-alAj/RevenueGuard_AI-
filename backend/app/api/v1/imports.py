"""Import API endpoints.

- POST /imports — upload a CSV/Excel file for import
- GET /imports/{id} — get import job status and summary
- GET /imports/{id}/errors — get paginated rejected rows with reasons
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.core.rbac import require_permission
from app.db.session import get_db
from app.models.integration import ImportJob
from app.models.organization import User
from app.services.ingestion.importer import run_import

router = APIRouter(prefix="/imports", tags=["imports"])

VALID_ENTITIES = {
    "customer",
    "contract",
    "contract_line",
    "project",
    "invoice",
    "invoice_line",
    "payment",
}


# --- Response Models ---


class ImportJobResponse(BaseModel):
    id: uuid.UUID
    target_entity: str
    status: str
    source: str
    file_name: str | None
    records_received: int
    records_accepted: int
    records_rejected: int
    errors: dict | None

    model_config = {"from_attributes": True}


class ImportErrorRow(BaseModel):
    row: int
    errors: list[str]
    original: dict | None = None


class ImportErrorsResponse(BaseModel):
    job_id: uuid.UUID
    total_errors: int
    offset: int
    limit: int
    errors: list[ImportErrorRow]


# --- Endpoints ---


@router.post(
    "",
    response_model=ImportJobResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("imports", "write"))],
)
async def create_import(
    file: UploadFile,
    target_entity: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    column_mapping: str | None = None,
) -> ImportJobResponse:
    """Upload a CSV/Excel file for import.

    - file: The CSV or Excel file to import
    - target_entity: The entity type to import (customer, contract, etc.)
    - column_mapping: Optional JSON string mapping source columns to target columns
    """
    if target_entity not in VALID_ENTITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target_entity: {target_entity}. Must be one of: {', '.join(sorted(VALID_ENTITIES))}",
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a filename",
        )

    # Read file content
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    # Parse column mapping if provided
    mapping = None
    if column_mapping:
        import json

        try:
            mapping = json.loads(column_mapping)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="column_mapping must be valid JSON",
            ) from None

    # Run the import
    job = await run_import(
        db=db,
        org_id=current_user.organization_id,
        target_entity=target_entity,
        file_content=content,
        file_name=file.filename,
        column_mapping=mapping,
    )

    return ImportJobResponse.model_validate(job)


@router.get(
    "/{job_id}",
    response_model=ImportJobResponse,
    dependencies=[Depends(require_permission("imports", "read"))],
)
async def get_import_job(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportJobResponse:
    """Get import job status and summary."""
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == job_id,
            ImportJob.organization_id == current_user.organization_id,
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found",
        )
    return ImportJobResponse.model_validate(job)


@router.get(
    "/{job_id}/errors",
    response_model=ImportErrorsResponse,
    dependencies=[Depends(require_permission("imports", "read"))],
)
async def get_import_errors(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ImportErrorsResponse:
    """Get paginated rejected rows with reasons."""
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == job_id,
            ImportJob.organization_id == current_user.organization_id,
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found",
        )

    errors_data = (job.errors or {}).get("rows", [])
    total = len(errors_data)
    paginated = errors_data[offset : offset + limit]

    return ImportErrorsResponse(
        job_id=job.id,
        total_errors=total,
        offset=offset,
        limit=limit,
        errors=[ImportErrorRow(**e) for e in paginated],
    )
