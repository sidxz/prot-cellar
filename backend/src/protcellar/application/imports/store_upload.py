"""StoreUpload / GetUpload use cases — persist and retrieve ImportUpload aggregates."""

from __future__ import annotations

import uuid

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin, require_authenticated
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.imports.repository import ImportUploadRepository
from protcellar.domain.imports.upload import ImportUpload
from protcellar.domain.shared.errors import DomainError, NotFoundError


class StoreUpload:
    """Persist a raw file upload as an ImportUpload aggregate.

    Caller responsibilities:
    - Provide ``auth`` with at least the ``admin`` role.
    - The XLSX→TSV conversion (if needed) is an *infrastructure* concern
      performed by the HTTP route before calling this use case; this use case
      stores whatever bytes are passed in.
    """

    def __init__(self, uow: UnitOfWork, upload_repo: ImportUploadRepository) -> None:
        self._uow = uow
        self._repo = upload_repo

    async def __call__(
        self,
        *,
        filename: str,
        content_type: str | None,
        data: bytes,
        auth: AuthContext | None = None,
    ) -> Result[ImportUpload, DomainError]:
        require_admin(auth)

        upload = ImportUpload.create(
            workspace_id=auth.workspace_id,  # type: ignore[union-attr]
            filename=filename,
            content_type=content_type,
            data=data,
        )

        async with self._uow:
            await self._repo.save(upload)
            await self._uow.commit()

        return Success(upload)


class GetUpload:
    """Retrieve a stored ImportUpload by ID.

    Any authenticated caller may fetch an upload (the route layer may impose
    further authz if needed).
    """

    def __init__(self, uow: UnitOfWork, upload_repo: ImportUploadRepository) -> None:
        self._uow = uow
        self._repo = upload_repo

    async def __call__(
        self,
        upload_id: uuid.UUID,
        auth: AuthContext | None = None,
    ) -> Result[ImportUpload, DomainError]:
        require_authenticated(auth)

        async with self._uow:
            upload = await self._repo.get(
                auth.workspace_id,  # type: ignore[union-attr]
                upload_id,
            )

        if upload is None:
            return Failure(NotFoundError("ImportUpload", str(upload_id)))

        return Success(upload)
