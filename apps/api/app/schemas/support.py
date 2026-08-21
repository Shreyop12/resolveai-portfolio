import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.ticket import NoteAuthor, TicketPriority, TicketStatus


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=80)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime


class TicketCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: str = Field(min_length=3, max_length=255)
    subject: str = Field(min_length=3, max_length=255)
    message: str = Field(min_length=3, max_length=20_000)
    priority: TicketPriority = TicketPriority.NORMAL


class TicketStatusUpdate(BaseModel):
    status: TicketStatus


class TicketNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    author: NoteAuthor = NoteAuthor.SUPPORT_AGENT


class TicketNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author: NoteAuthor
    body: str
    created_at: datetime


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: str
    customer_name: str
    customer_email: str
    subject: str
    message: str
    status: TicketStatus
    priority: TicketPriority
    created_at: datetime
    updated_at: datetime


class TicketDetailRead(TicketRead):
    notes: list[TicketNoteRead]


class TicketList(BaseModel):
    items: list[TicketRead]
    limit: int
    offset: int
