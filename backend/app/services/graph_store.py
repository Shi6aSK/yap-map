from typing import Dict, Any, List, Tuple
from sqlmodel import Session, select
from app.database import engine
from app.models.graph import GraphNode, GraphEdge
from datetime import datetime
import difflib
import json
from uuid import uuid4


# threshold for fuzzy merging of labels (0..1)
MERGE_THRESHOLD = 0.86


def _normalize_label(label: str) -> str:
    return (label or '').strip().lower()


def _ensure_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    try:
        return list(v)
    except Exception:
        return [v]


def apply_graph_patch(session_id: str, patch: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Persist a graph.patch into the DB, merging nodes/edges when labels are similar.

    Returns the canonicalized patch (nodes/edges with DB IDs and merged segment lists).
    """
    nodes_added = patch.get('nodesAdded', []) or []
    edges_added = patch.get('edgesAdded', []) or []

    id_map: Dict[str, str] = {}  # original_id -> persisted_id

    with Session(engine) as db:
        # handle node additions (merge or create)
        for n in nodes_added:
            orig_id = n.get('id')
            label = n.get('label') or ''
            norm = n.get('normalizedLabel') or _normalize_label(label)
            ntype = n.get('type') or 'claim'

            # first try exact normalized_label match
            stmt = select(GraphNode).where(GraphNode.session_id == session_id, GraphNode.normalized_label == norm, GraphNode.type == ntype)
            existing = db.exec(stmt).first()

            # if no exact match, try fuzzy match among same-type nodes for this session
            if existing is None:
                stmt2 = select(GraphNode).where(GraphNode.session_id == session_id, GraphNode.type == ntype)
                candidates = db.exec(stmt2).all()
                best = None
                best_score = 0.0
                for c in candidates:
                    score = difflib.SequenceMatcher(None, (c.normalized_label or ''), norm).ratio()
                    if score > best_score:
                        best_score = score
                        best = c
                if best_score >= MERGE_THRESHOLD:
                    existing = best

            if existing:
                # merge: union segment ids, update importance and timestamps
                old_segs = existing.segment_ids or []
                new_segs = _ensure_list(n.get('segmentIds'))
                merged_segs = list(dict.fromkeys(old_segs + new_segs))
                existing.segment_ids = merged_segs
                try:
                    existing.importance = float(max(existing.importance or 0.0, float(n.get('importance', 1.0))))
                except Exception:
                    existing.importance = float(n.get('importance', 1.0))
                    existing.updated_at = datetime.utcnow()
                db.add(existing)
                db.commit()
                db.refresh(existing)
                id_map[orig_id] = existing.id
            else:
                node_id = orig_id or str(uuid4())
                node = GraphNode(
                    id=node_id,
                    session_id=session_id,
                    type=ntype,
                    label=label,
                    normalized_label=norm,
                    summary=n.get('summary'),
                    importance=float(n.get('importance', 1.0)),
                    segment_ids=_ensure_list(n.get('segmentIds')),
                        metadata_=n.get('metadata') or {},
                )
                db.add(node)
                db.commit()
                db.refresh(node)
                id_map[orig_id] = node.id

        # handle edges (translate node ids via id_map)
        for e in edges_added:
            orig_eid = e.get('id')
            src = id_map.get(e.get('source'), e.get('source'))
            tgt = id_map.get(e.get('target'), e.get('target'))
            etype = e.get('type', 'related_to')
            segs = _ensure_list(e.get('segmentIds'))

            stmt = select(GraphEdge).where(
                GraphEdge.session_id == session_id,
                GraphEdge.source == src,
                GraphEdge.target == tgt,
                GraphEdge.type == etype,
            )
            existing_e = db.exec(stmt).first()
            if existing_e:
                old_segs = existing_e.segment_ids or []
                merged_segs = list(dict.fromkeys(old_segs + segs))
                existing_e.segment_ids = merged_segs
                try:
                    existing_e.weight = float(existing_e.weight or 0.0) + float(e.get('weight', 1.0))
                except Exception:
                    existing_e.weight = float(e.get('weight', 1.0))
                existing_e.updated_at = datetime.utcnow()
                db.add(existing_e)
                db.commit()
                db.refresh(existing_e)
                e['id'] = existing_e.id
                e['source'] = src
                e['target'] = tgt
            else:
                edge = GraphEdge(
                    id=orig_eid or str(uuid4()),
                    session_id=session_id,
                    source=src,
                    target=tgt,
                    type=etype,
                    weight=float(e.get('weight', 1.0)),
                    segment_ids=segs,
                        metadata_=e.get('metadata') or {},
                )
                db.add(edge)
                db.commit()
                db.refresh(edge)
                e['id'] = edge.id
                e['source'] = src
                e['target'] = tgt

    # Build canonicalized patch to return (query final state for those ids)
    canonical_nodes: List[Dict[str, Any]] = []
    canonical_edges: List[Dict[str, Any]] = []

    with Session(engine) as db:
        # collect unique persisted node ids from id_map values
        persisted_node_ids = list(dict.fromkeys(id_map.values()))
        for nid in persisted_node_ids:
            node = db.get(GraphNode, nid)
            if node:
                canonical_nodes.append({
                    'id': node.id,
                    'sessionId': node.session_id,
                    'type': node.type,
                    'label': node.label,
                    'normalizedLabel': node.normalized_label,
                    'summary': node.summary,
                    'importance': float(node.importance),
                    'segmentIds': node.segment_ids or [],
                        'metadata': node.metadata_ or {},
                })

        # edges: take edges that were added/updated in this patch by id (deduplicated)
        edge_by_id: Dict[str, Dict[str, Any]] = {}
        for e in edges_added:
            eid = e.get('id')
            if not eid:
                continue
            edge = db.get(GraphEdge, eid)
            if edge and edge.id not in edge_by_id:
                edge_by_id[edge.id] = {
                    'id': edge.id,
                    'sessionId': edge.session_id,
                    'source': edge.source,
                    'target': edge.target,
                    'type': edge.type,
                    'weight': float(edge.weight),
                    'segmentIds': edge.segment_ids or [],
                    'metadata': edge.metadata_ or {},
                }
        canonical_edges = list(edge_by_id.values())

    return {
        'nodesAdded': canonical_nodes,
        'nodesUpdated': [],
        'edgesAdded': canonical_edges,
        'edgesUpdated': [],
    }
