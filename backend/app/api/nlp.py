from fastapi import APIRouter, BackgroundTasks, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import Optional
import io
import logging

from app.services.model_init import get_model_manager

router = APIRouter()
logger = logging.getLogger(__name__)


class ExtractRequest(BaseModel):
    text: str
    top_n: Optional[int] = 30


@router.get("/status")
async def get_model_status():
    """
    Check the status of model initialization.
    Returns: {
        "status": "loading" | "ready" | "failed" | "not_started",
        "error": null or error message if failed
    }
    """
    manager = get_model_manager()
    return {
        "status": manager.status.value,
        "error": manager.error_message,
        "is_ready": manager.is_ready()
    }


@router.post("/extract")
async def extract_topics(body: ExtractRequest, background_tasks: BackgroundTasks):
    """
    Extract keyphrases and semantic similarity edges from transcript text.
    Uses KeyBERT + sentence-transformers/all-mpnet-base-v2.
    Model is downloaded automatically on first use (~420 MB, one-time).
    """
    from app.services.nlp_service import extract_graph_topics
    result = extract_graph_topics(body.text, top_n=body.top_n or 30)
    return result


# NOTE: File upload endpoint disabled temporarily - python-multipart loading issues
# Focus on real-time WebSocket microphone path first
# TODO: Re-enable once python-multipart integration is stable
# @router.post("/transcribe-audio")
# async def transcribe_audio(file: UploadFile = File(...)):
#     """
#     Transcribe an audio file and optionally process through the graph pipeline.
#     Supports: WAV, MP3, WEBM, OGG, FLAC, M4A, etc.
#     Returns: transcript text and optional graph patch
#     """
#     ...
