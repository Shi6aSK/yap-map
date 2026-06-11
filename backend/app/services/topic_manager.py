from typing import Dict, Any, Optional, Tuple
from .local_models import LocalModelManager
import numpy as np
import uuid


class TopicManager:
    """Simple in-memory incremental topic clustering using embedding centroids.

    Not a production-grade clusterer, but sufficient for an MVP: keep per-cluster
    centroid vectors and assign new segments by cosine similarity threshold.
    """

    def __init__(self, model_manager: Optional[LocalModelManager] = None, sim_threshold: float = 0.72):
        self.model_manager = model_manager or LocalModelManager()
        self.sim_threshold = sim_threshold
        self.clusters: Dict[str, Dict[str, Any]] = {}

    def _cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-10
        return float(np.dot(a, b) / denom)

    def add_segment(self, text: str, segment_id: str, timestamp: Optional[str] = None) -> Tuple[str, bool]:
        """Embed `text`, assign to existing cluster or create a new one.

        Returns (cluster_id, created_new)
        """
        emb = self.model_manager.embed([text])[0]

        if not self.clusters:
            cid = str(uuid.uuid4())
            self.clusters[cid] = {
                'id': cid,
                'centroid': emb,
                'label': text[:120],
                'segmentIds': [segment_id],
                'count': 1,
                'weight': len(text.split()),
                'createdAt': timestamp,
                'lastSeen': timestamp,
            }
            return cid, True

        # compute similarities to centroids
        centroids = np.stack([c['centroid'] for c in self.clusters.values()])
        emb_norm = emb / (np.linalg.norm(emb) + 1e-10)
        cent_norm = centroids / (np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-10)
        sims = cent_norm.dot(emb_norm)
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])

        keys = list(self.clusters.keys())
        best_cid = keys[best_idx]

        if best_sim >= self.sim_threshold:
            cluster = self.clusters[best_cid]
            count = cluster.get('count', 1)
            # incremental centroid update
            new_centroid = (cluster['centroid'] * count + emb) / (count + 1)
            cluster['centroid'] = new_centroid
            cluster['count'] = count + 1
            cluster['segmentIds'].append(segment_id)
            cluster['lastSeen'] = timestamp
            cluster['weight'] = cluster.get('weight', 0) + len(text.split())
            return best_cid, False

        # create new cluster
        cid = str(uuid.uuid4())
        self.clusters[cid] = {
            'id': cid,
            'centroid': emb,
            'label': text[:120],
            'segmentIds': [segment_id],
            'count': 1,
            'weight': len(text.split()),
            'createdAt': timestamp,
            'lastSeen': timestamp,
        }
        return cid, True

    def get_cluster(self, cid: str) -> Optional[Dict[str, Any]]:
        return self.clusters.get(cid)

    def export_clusters(self):
        return list(self.clusters.values())


__all__ = ['TopicManager']
