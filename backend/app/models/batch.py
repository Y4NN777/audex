from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditBatch(SQLModel, table=True):
    __tablename__ = "audit_batches"

    id: str = Field(primary_key=True, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
    status: str
    report_hash: Optional[str] = Field(default=None)
    report_path: Optional[str] = Field(default=None)
    last_error: Optional[str] = Field(default=None)

    files: List["BatchFile"] = Relationship(
        back_populates="batch",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    events: List["ProcessingEvent"] = Relationship(
        back_populates="batch",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "ProcessingEvent.timestamp"},
    )
    ocr_texts: List["OCRText"] = Relationship(
        back_populates="batch",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "OCRText.created_at"},
    )


class BatchFile(SQLModel, table=True):
    __tablename__ = "batch_files"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(foreign_key="audit_batches.id", index=True)
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    stored_path: str
    metadata_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column("metadata", JSON, nullable=True),
    )

    batch: "AuditBatch" = Relationship(back_populates="files")


class ProcessingEvent(SQLModel, table=True):
    __tablename__ = "processing_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(foreign_key="audit_batches.id", index=True)
    code: str
    label: str
    kind: str = Field(default="info")
    progress: Optional[int] = Field(default=None)
    timestamp: datetime = Field(default_factory=utcnow)
    details: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

    batch: "AuditBatch" = Relationship(back_populates="events")


class OCRText(SQLModel, table=True):
    __tablename__ = "ocr_texts"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(foreign_key="audit_batches.id", index=True)
    filename: str
    engine: str = Field(default="unknown")
    content: str = Field(default="")
    confidence: Optional[float] = Field(default=None)
    warnings: Optional[list[str]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    error: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    batch: "AuditBatch" = Relationship(back_populates="ocr_texts")
