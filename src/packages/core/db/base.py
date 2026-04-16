from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    type_annotation_map = {
        dict: JSONB,
        list[float]: Vector(1536),
    }


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
