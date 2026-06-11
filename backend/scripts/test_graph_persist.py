import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.graph_store import apply_graph_patch
from app.database import engine, init_db
from sqlmodel import Session, select


def make_patch():
    # Two claim nodes with similar labels and a topic that shares segment
    return {
        'nodesAdded': [
            {'id': 'n1', 'type': 'claim', 'label': 'We should hire a designer', 'normalizedLabel': 'we should hire a designer', 'importance': 1.0, 'segmentIds': ['s1']},
            {'id': 'n2', 'type': 'claim', 'label': 'We should hire designer', 'normalizedLabel': 'we should hire designer', 'importance': 0.8, 'segmentIds': ['s2']},
            {'id': 't1', 'type': 'topic', 'label': 'Hiring', 'normalizedLabel': 'hiring', 'importance': 1.0, 'segmentIds': ['s1','s2']},
        ],
        'edgesAdded': [
            {'id': 'e1', 'source': 't1', 'target': 'n1', 'type': 'related_to', 'weight': 1.0, 'segmentIds': ['s1']},
            {'id': 'e2', 'source': 't1', 'target': 'n2', 'type': 'related_to', 'weight': 1.0, 'segmentIds': ['s2']},
        ],
    }


def main():
    session_id = 'test-session'
    # ensure DB tables exist
    init_db()

    patch = make_patch()
    canonical = apply_graph_patch(session_id, patch)
    print('Canonical patch:')
    print(canonical)

    # Inspect DB
    from app.models.graph import GraphNode, GraphEdge
    with Session(engine) as s:
        nodes = s.exec(select(GraphNode).where(GraphNode.session_id == session_id)).all()
        edges = s.exec(select(GraphEdge).where(GraphEdge.session_id == session_id)).all()
        print('\nDB nodes:')
        for n in nodes:
            print(n.id, n.type, n.label, n.segment_ids, n.importance)
        print('\nDB edges:')
        for e in edges:
            print(e.id, e.source, e.target, e.segment_ids, e.weight)


if __name__ == '__main__':
    main()
