from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlmodel import select
from sqlmodel import Session as DBSession

from app.database import get_session
from app.models.session import Session as SessionModel
from app.schemas.session import SessionCreate, SessionRead

router = APIRouter()


@router.post("/", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(session_in: SessionCreate, db: DBSession = Depends(get_session)):
    sess = SessionModel(title=session_in.title, mode=session_in.mode, status=("live" if session_in.mode == "live_mic" else "created"))
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


@router.get("/", response_model=List[SessionRead])
def list_sessions(db: DBSession = Depends(get_session)):
    sessions = db.exec(select(SessionModel)).all()
    return sessions


@router.get("/{session_id}", response_model=SessionRead)
def get_session_by_id(session_id: str, db: DBSession = Depends(get_session)):
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, db: DBSession = Depends(get_session)):
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(sess)
    db.commit()
    return
