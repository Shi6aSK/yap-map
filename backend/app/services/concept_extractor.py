from typing import List, Dict, Any, Tuple
import re
from uuid import uuid4


def _find_persons(text: str) -> List[str]:
    # naive capitalized name detection (first + last name)
    pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
    return pattern.findall(text)


def _find_topics(text: str) -> List[str]:
    # match phrases after keywords
    pattern = re.compile(r"(?:about|using|with|for)\s+([A-Za-z0-9 _-]{3,60})", re.IGNORECASE)
    return [m.strip() for m in pattern.findall(text)]


def extract_concepts(text: str, segment_id: str | None = None, speaker: str | None = None) -> Dict[str, Any]:
    """Very small rule-based extractor that returns nodes and edges from a text segment.

    Returns:
      { 'nodes': [ {id, type, label, normalizedLabel, importance, segmentIds, metadata}], 'edges': [] }
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    for sent in sentences:
        s = sent.strip()
        if not s:
            continue

        # Questions
        if s.endswith('?'):
            nodes.append({
                'id': str(uuid4()),
                'type': 'question',
                'label': s,
                'normalizedLabel': s.lower(),
                'importance': 1.0,
                'segmentIds': [segment_id] if segment_id else [],
                'metadata': {},
            })
            continue

        # Action items
        if re.search(r"\b(we should|i will|we need to|todo|next step|let's|let us)\b", s, re.IGNORECASE):
            nodes.append({
                'id': str(uuid4()),
                'type': 'action_item',
                'label': s,
                'normalizedLabel': re.sub(r"\s+"," ", s).strip().lower(),
                'importance': 1.0,
                'segmentIds': [segment_id] if segment_id else [],
                'metadata': {},
            })
            continue

        # Decisions
        if re.search(r"\b(we decided|we will use|let's go with|we are going with|we'll use)\b", s, re.IGNORECASE):
            nodes.append({
                'id': str(uuid4()),
                'type': 'decision',
                'label': s,
                'normalizedLabel': s.lower(),
                'importance': 1.0,
                'segmentIds': [segment_id] if segment_id else [],
                'metadata': {},
            })
            continue

        # Persons
        persons = _find_persons(s)
        for p in persons:
            nodes.append({
                'id': str(uuid4()),
                'type': 'person',
                'label': p,
                'normalizedLabel': p.lower(),
                'importance': 1.0,
                'segmentIds': [segment_id] if segment_id else [],
                'metadata': {},
            })

        # Topics
        topics = _find_topics(s)
        for t in topics:
            nodes.append({
                'id': str(uuid4()),
                'type': 'topic',
                'label': t,
                'normalizedLabel': t.lower(),
                'importance': 1.0,
                'segmentIds': [segment_id] if segment_id else [],
                'metadata': {},
            })

        # Claims (fallthrough)
        nodes.append({
            'id': str(uuid4()),
            'type': 'claim',
            'label': s,
            'normalizedLabel': s.lower(),
            'importance': 0.5,
            'segmentIds': [segment_id] if segment_id else [],
            'metadata': {},
        })

    return {'nodes': nodes, 'edges': edges}
