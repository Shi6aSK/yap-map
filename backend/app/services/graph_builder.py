from typing import Dict, Any, List
from uuid import uuid4


def build_graph_patch_from_concepts(session_id: str, concepts: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    nodes_out: List[Dict[str, Any]] = []
    edges_out: List[Dict[str, Any]] = []

    # Create node objects
    for n in concepts.get('nodes', []):
        node = {
            'id': n.get('id') or str(uuid4()),
            'sessionId': session_id,
            'type': n.get('type'),
            'label': n.get('label'),
            'normalizedLabel': n.get('normalizedLabel') or (n.get('label') or '').lower(),
            'summary': n.get('summary'),
            'importance': n.get('importance', 1.0),
            'segmentIds': n.get('segmentIds', []),
            'metadata': n.get('metadata', {}),
        }
        nodes_out.append(node)

    # Naive edge creation: link topics to claims in same segment
    topics = [n for n in nodes_out if n['type'] == 'topic']
    claims = [n for n in nodes_out if n['type'] == 'claim']

    for t in topics:
        for c in claims:
            # if they share any segment id, connect them
            if set(t.get('segmentIds', [])) & set(c.get('segmentIds', [])):
                edge = {
                    'id': str(uuid4()),
                    'sessionId': session_id,
                    'source': t['id'],
                    'target': c['id'],
                    'type': 'related_to',
                    'weight': 1.0,
                    'segmentIds': list(set(t.get('segmentIds', []) + c.get('segmentIds', []))),
                    'metadata': {},
                }
                edges_out.append(edge)

    return {
        'nodesAdded': nodes_out,
        'nodesUpdated': [],
        'edgesAdded': edges_out,
        'edgesUpdated': [],
    }
