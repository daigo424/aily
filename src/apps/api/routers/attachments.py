from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from packages.core.db.repositories import Repository
from packages.core.db.session import get_db
from packages.core.infrastructure.storage import backend as storage

router = APIRouter()


@router.get("/attachments/{attachment_id}")
def get_attachment(attachment_id: int, db: Session = Depends(get_db)) -> Response:
    repo = Repository(db)
    att = repo.get_attachment(attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    try:
        data = storage.load(att.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Attachment file not found")
    return Response(content=data, media_type=att.mime_type)
