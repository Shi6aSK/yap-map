from typing import Optional, List, Dict
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from datetime import datetime
import uuid


class GraphNode(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(index=True)
    type: str
    label: str
    normalized_label: str = Field(index=True)
    summary: Optional[str] = None
    importance: float = Field(default=1.0)
    segment_ids: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    metadata_: Dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GraphEdge(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(index=True)
    source: str
    target: str
    type: str
    weight: float = Field(default=1.0)
    segment_ids: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    metadata_: Dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
