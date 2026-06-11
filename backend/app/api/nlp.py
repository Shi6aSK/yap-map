from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ExtractRequest(BaseModel):
    text: str
    top_n: Optional[int] = 30


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
