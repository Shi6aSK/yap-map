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
from app.services.topic_manager import TopicManager
from app.services.question_generator import QuestionGenerator

router = APIRouter()

logger = logging.getLogger(__name__)

# Per-session topic managers. IMPORTANT: topic clustering state must NOT be
# shared across sessions/conversations — each session gets its own set of
# clusters (though they all reuse the single pre-loaded embedding model to
# avoid re-loading it). Without this, unrelated conversations from different
# sessions (or repeated test runs) all pile into one giant shared cluster
# state, which is a major source of graph fragmentation/clutter.
_session_topic_managers: dict = {}

# How many finalized segments between batch reanalysis passes. Real-time
# transcription must stay fast, so reanalysis (merging near-duplicate topics,
# pruning noise) runs on a slower cadence rather than per-segment.
REANALYSIS_SEGMENT_INTERVAL = 4


@router.websocket("/ws/live/{session_id}")
async def live_audio_ws(websocket: WebSocket, session_id: str):
    logger.info('WebSocket connected for session %s', session_id)
    await websocket.accept()

    # Get pre-loaded transcriber and models from global manager
    from app.services.model_init import get_model_manager
    mm = get_model_manager()
    
    # Use the pre-loaded transcriber (no model loading, already done at startup)
    transcriber = mm.vosk_transcriber
    provider = (settings.TRANSCRIPTION_PROVIDER or 'vosk').lower()

    if transcriber is None or provider == 'mock':
        logger.warning('Using MockTranscriber — real transcription not available')
        transcriber = MockTranscriber()
    else:
        logger.info('Using pre-loaded VoskTranscriber')

    # Use pre-loaded models from global manager
    model_manager = mm.local_model_manager
    question_gen = mm.question_generator

    # Fresh, session-scoped topic manager (reuses the shared embedding model)
    if session_id not in _session_topic_managers:
        _session_topic_managers[session_id] = TopicManager(model_manager=model_manager)
    topic_manager = _session_topic_managers[session_id]
    finalized_segment_count = 0

    async def produce_transcripts():
        try:
            async for event in transcriber.events():
                try:
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

                            # Periodic batch reanalysis: real-time transcription/graph updates stay
                            # fast (greedy per-segment assignment above), but every few segments we
                            # run a heavier pass that merges near-duplicate topic clusters and prunes
                            # weak, isolated single-mention fragments — correcting the fragmentation
                            # that greedy assignment alone tends to accumulate over a long session.
                            nonlocal finalized_segment_count
                            finalized_segment_count += 1
                            if finalized_segment_count % REANALYSIS_SEGMENT_INTERVAL == 0:
                                try:
                                    changes = topic_manager.reanalyze()
                                    removed_ids = [absorbed for absorbed, _survivor in changes.get('merged', [])] + changes.get('removed', [])
                                    if removed_ids:
                                        removal_patch = {
                                            'nodesAdded': [],
                                            'edgesAdded': [],
                                            'nodesRemoved': removed_ids,
                                            'edgesRemoved': [],
                                        }
                                        canonical_removal = apply_graph_patch(session_id, removal_patch)
                                        logger.info('Reanalysis merged/pruned %d cluster(s) for session %s', len(removed_ids), session_id)
                                        await websocket.send_json({"type": "graph.patch", "payload": canonical_removal})
                                except Exception as exc:
                                    logger.error('Reanalysis pass failed: %s', exc, exc_info=True)
                        except Exception as exc:
                            logger.error('Error processing transcript: %s', exc, exc_info=True)
                            await websocket.send_json({"type": "processing.status", "payload": {"status": "error", "message": str(exc)}})
                    elif getattr(event, 'type', None) == 'error':
                        # forward errors from underlying transcriber (decoding/recognizer)
                        msg = getattr(event, 'text', None) or getattr(event, 'message', None) or 'transcriber error'
                        logger.warning('Transcriber error: %s', msg)
                        try:
                            await websocket.send_json({"type": "processing.status", "payload": {"status": "error", "message": msg}})
                        except Exception:
                            logger.exception('Failed to send transcriber error to client')
                except Exception as exc:
                    logger.error('Error sending transcript event: %s', exc, exc_info=True)
                    # If we can't send to client, break the producer loop
                    if isinstance(exc, (ConnectionError, RuntimeError)):
                        break
        except asyncio.CancelledError:
            logger.debug('produce_transcripts cancelled')
        except Exception as exc:
            logger.error('Error in produce_transcripts: %s', exc, exc_info=True)

    producer_task = asyncio.create_task(produce_transcripts())

    try:
        while True:
            try:
                msg = await websocket.receive_json()
                msg_type = msg.get("type")
                logger.info('WS recv msg type=%s', msg_type)

                if msg_type == "session.start":
                    logger.info('Session started for %s', session_id)
                    await websocket.send_json({"type": "processing.status", "payload": {"status": "listening"}})

                elif msg_type == "audio.chunk":
                    payload = msg.get("payload", {})
                    data_b64 = payload.get("dataBase64")
                    if data_b64:
                        logger.info('Received audio.chunk with %d bytes of base64 data', len(data_b64))
                        try:
                            audio_bytes = base64.b64decode(data_b64)
                            logger.info('Decoded audio.chunk to %d bytes', len(audio_bytes))
                        except Exception as e:
                            logger.error('Failed to decode base64: %s', e)
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
                        logger.info('Sending audio to transcriber: seq=%s size=%d mime=%s', seq, len(audio_bytes), mime_type)
                        await transcriber.send_audio(audio_bytes, mime_type)
                    else:
                        logger.warning('audio.chunk received but no dataBase64 in payload')

                elif msg_type == "session.stop":
                    await websocket.send_json({"type": "processing.status", "payload": {"status": "stopped"}})
                    await transcriber.close()
                    break
            except asyncio.CancelledError:
                logger.warning('Receive cancelled on session %s', session_id)
                raise
            except RuntimeError as e:
                # RuntimeError: "Cannot call 'receive' once a disconnect message has been received"
                # This indicates the socket is disconnected; break the loop instead of retrying
                if "disconnect" in str(e).lower() or "cannot call" in str(e).lower():
                    logger.info('Socket disconnected (RuntimeError: %s); exiting receive loop', str(e))
                    break
                else:
                    logger.error('RuntimeError receiving message on session %s: %s', session_id, e, exc_info=True)
            except Exception as e:
                logger.error('Error receiving message on session %s: %s', session_id, e, exc_info=True)
                # For other exceptions, don't break—continue trying to receive

    except WebSocketDisconnect:
        logger.info('WebSocket disconnected for session %s', session_id)
    except asyncio.CancelledError:
        logger.info('WebSocket handler cancelled for session %s', session_id)
    except Exception as exc:
        logger.error('WebSocket error on session %s: %s', session_id, exc, exc_info=True)
    finally:
        # Check if producer task has failed with an exception
        if producer_task and not producer_task.done():
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass
        elif producer_task:
            try:
                # Get any exception that occurred in the producer task
                producer_task.result()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error('Producer task failed: %s', e, exc_info=True)
        try:
            await transcriber.close()
        except Exception:
            pass
        # Free the session-scoped topic clustering state now that the session
        # has ended, so long-running server processes don't accumulate
        # clusters from every past session in memory.
        _session_topic_managers.pop(session_id, None)
