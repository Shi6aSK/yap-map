from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid


class Session(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: Optional[str] = Field(default=None)
    mode: str = Field(default="live_mic")
    status: str = Field(default="created")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
