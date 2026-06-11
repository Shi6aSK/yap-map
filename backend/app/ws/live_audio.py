from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import base64
import logging
from uuid import uuid4
from datetime import datetime

from app.services.transcription.mock_transcriber import MockTranscriber
from app.config import settings
from app.services.concept_extractor import extract_concepts
from app.services.graph_builder import build_graph_patch_from_concepts
from app.services.graph_store import apply_graph_patch
from app.services.local_models import LocalModelManager
from app.services.topic_manager import TopicManager
from app.services.question_generator import QuestionGenerator

router = APIRouter()

logger = logging.getLogger(__name__)


@router.websocket("/ws/live/{session_id}")
async def live_audio_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()

    # Select transcriber: prefer Vosk when model exists, regardless of env setting
    mm_for_vosk = LocalModelManager()
    vosk_path = mm_for_vosk.manifest.get('vosk_model')
    provider = (settings.TRANSCRIPTION_PROVIDER or 'vosk').lower()

    transcriber = None
    if vosk_path and provider != 'mock':
        try:
            from app.services.transcription.vosk_transcriber import VoskTranscriber
            transcriber = VoskTranscriber(model_path=vosk_path)
            logger.info('Using VoskTranscriber with model at %s', vosk_path)
        except Exception as exc:
            logger.error('Failed to load VoskTranscriber: %s — falling back to mock', exc)
            transcriber = None

    if transcriber is None:
        logger.warning('Using MockTranscriber — real transcription not available')
        transcriber = MockTranscriber()

    await transcriber.start()

    # initialize local model helpers (lazy-load models only when used)
    model_manager = LocalModelManager()
    topic_manager = TopicManager(model_manager=model_manager)
    question_gen = QuestionGenerator(model_manager=model_manager)

    async def produce_transcripts():
        async for event in transcriber.events():
            if event.type == "partial":
                await websocket.send_json({"type": "transcript.partial", "payload": event.model_dump()})

            elif event.type == "final":
                # build a minimal transcript segment
                segment = {
                    "id": str(uuid4()),
                    "sessionId": session_id,
                    "speaker": event.speaker,
                    "text": event.text,
                    "startTime": event.start_time,
                    "endTime": event.end_time,
                    "index": 0,
                    "isFinal": True,
                    "createdAt": datetime.utcnow().isoformat(),
                }

                await websocket.send_json({"type": "transcript.final", "payload": segment})

                # run concept extraction + graph builder for the finalized segment
                try:
                    concepts = extract_concepts(segment['text'], segment_id=segment['id'], speaker=segment.get('speaker'))
                    graph_patch = build_graph_patch_from_concepts(session_id, concepts)

                    # Assign segment to a topic cluster (embedding-based)
                    try:
                        cid, created = topic_manager.add_segment(segment['text'], segment['id'], timestamp=segment.get('createdAt'))
                        cluster = topic_manager.get_cluster(cid)
                        # add a cluster node into the graph patch
                        cluster_node = {
                            'id': cid,
                            'sessionId': session_id,
                            'type': 'topic',
                            'label': cluster.get('label')[:120],
                            'normalizedLabel': cluster.get('label', '').lower(),
                            'summary': None,
                            'importance': float(cluster.get('weight', 1.0)),
                            'segmentIds': cluster.get('segmentIds', []),
                            'metadata': {},
                        }
                        graph_patch['nodesAdded'].append(cluster_node)

                        # connect cluster node to claim nodes in this patch
                        for n in graph_patch.get('nodesAdded', []):
                            if n.get('type') == 'claim':
                                edge = {
                                    'id': f"{cid}-{n['id']}",
                                    'sessionId': session_id,
                                    'source': cid,
                                    'target': n['id'],
                                    'type': 'related_to',
                                    'weight': 1.0,
                                    'segmentIds': [segment['id']],
                                    'metadata': {},
                                }
                                graph_patch['edgesAdded'].append(edge)

                        # optionally generate question prompts when clusters are first created
                        if created:
                            try:
                                prompt_candidates = question_gen.generate(cluster.get('label', '')[:200], style='deep_psych', num=2)
                                await websocket.send_json({"type": "processing.status", "payload": {"status": "suggestions", "message": prompt_candidates}})
                            except Exception:
                                pass

                    except Exception:
                        # topic assignment failed silently
                        pass

                    # persist/merge the patch into the graph store and emit the canonical patch
                    try:
                        canonical_patch = apply_graph_patch(session_id, graph_patch)
                        await websocket.send_json({"type": "graph.patch", "payload": canonical_patch})
                    except Exception as exc:
                        await websocket.send_json({"type": "processing.status", "payload": {"status": "error", "message": f"graph_persist_error: {exc}"}})
                except Exception as exc:
                    await websocket.send_json({"type": "processing.status", "payload": {"status": "error", "message": str(exc)}})
            elif getattr(event, 'type', None) == 'error':
                # forward errors from underlying transcriber (decoding/recognizer)
                msg = getattr(event, 'text', None) or getattr(event, 'message', None) or 'transcriber error'
                logger.warning('Transcriber error: %s', msg)
                try:
                    await websocket.send_json({"type": "processing.status", "payload": {"status": "error", "message": msg}})
                except Exception:
                    logger.exception('Failed to send transcriber error to client')

    producer_task = asyncio.create_task(produce_transcripts())

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")
            logger.debug('WS recv msg type=%s', msg_type)

            if msg_type == "session.start":
                await websocket.send_json({"type": "processing.status", "payload": {"status": "listening"}})

            elif msg_type == "audio.chunk":
                payload = msg.get("payload", {})
                data_b64 = payload.get("dataBase64")
                if data_b64:
                    try:
                        audio_bytes = base64.b64decode(data_b64)
                    except Exception:
                        await websocket.send_json({"type": "processing.status", "payload": {"status": "error", "message": "invalid_base64_payload"}})
                        continue

                    # protect against excessively large single chunks (5MB)
                    max_chunk_bytes = 5 * 1024 * 1024
                    if len(audio_bytes) > max_chunk_bytes:
                        await websocket.send_json({"type": "processing.status", "payload": {"status": "error", "message": "chunk_too_large"}})
                        logger.warning('Rejected audio.chunk: size %d exceeds limit %d', len(audio_bytes), max_chunk_bytes)
                        continue

                    mime_type = payload.get("mimeType", "audio/webm")
                    seq = payload.get('sequence')
                    logger.debug('Received audio.chunk seq=%s size=%d mime=%s', seq, len(audio_bytes), mime_type)
                    await transcriber.send_audio(audio_bytes, mime_type)

            elif msg_type == "session.stop":
                await websocket.send_json({"type": "processing.status", "payload": {"status": "stopped"}})
                await transcriber.close()
                break

    except WebSocketDisconnect:
        # client disconnected
        pass
    finally:
        producer_task.cancel()
        try:
            await transcriber.close()
        except Exception:
            pass
