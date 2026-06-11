from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SessionCreate(BaseModel):
    title: Optional[str] = None
    mode: Optional[str] = "live_mic"


class SessionRead(BaseModel):
    id: str
    title: Optional[str] = None
    mode: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
