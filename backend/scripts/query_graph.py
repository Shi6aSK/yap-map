import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from sqlmodel import Session, select
from app.database import engine
from app.models.graph import GraphNode, GraphEdge

session_id = 'testsession'
with Session(engine) as s:
    nodes = s.exec(select(GraphNode).where(GraphNode.session_id == session_id)).all()
    edges = s.exec(select(GraphEdge).where(GraphEdge.session_id == session_id)).all()

print('NODES:')
for n in nodes:
    print(f"{n.id} | {n.type} | {n.label} | {n.segment_ids} | {n.importance}")

print('\nEDGES:')
for e in edges:
    print(f"{e.id} | {e.source} -> {e.target} | {e.segment_ids} | {e.weight}")
