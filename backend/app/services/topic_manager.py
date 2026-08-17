from typing import Dict, Any, Optional, Tuple, List
from .local_models import LocalModelManager
from datetime import datetime, timezone
import numpy as np
import uuid


class TopicManager:
    """Simple in-memory incremental topic clustering using embedding centroids.

    Not a production-grade clusterer, but sufficient for an MVP: keep per-cluster
    centroid vectors and assign new segments by cosine similarity threshold.

    Real-time transcription must stay fast, so segment assignment (`add_segment`)
    is a cheap greedy nearest-centroid lookup. To correct the over-fragmentation
    that greedy assignment inevitably produces (near-duplicate topics phrased
    differently ending up as separate clusters), `reanalyze()` performs a
    heavier, periodic batch pass that merges near-duplicate clusters and prunes
    weak, isolated single-mention clusters. This is intended to be called
    on a cadence (e.g. every few finalized segments) rather than per-segment.
    """

    def __init__(self, model_manager: Optional[LocalModelManager] = None, sim_threshold: float = 0.72,
                 merge_threshold: float = 0.80, reclassify_threshold: float = 0.60,
                 prune_max_weight: int = 4, prune_min_age_seconds: float = 20.0):
        self.model_manager = model_manager or LocalModelManager()
        self.sim_threshold = sim_threshold
        # merge_threshold: clusters this similar are almost certainly the same topic
        self.merge_threshold = merge_threshold
        # reclassify_threshold: looser bar used only during batch reanalysis to
        # fold weak/tiny clusters into a reasonably-related neighbor
        self.reclassify_threshold = reclassify_threshold
        # prune_*: criteria for discarding a cluster entirely as noise if it
        # never grew and has no reasonable neighbor to merge into
        self.prune_max_weight = prune_max_weight
        self.prune_min_age_seconds = prune_min_age_seconds
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

    def _age_seconds(self, cluster: Dict[str, Any]) -> float:
        ts = cluster.get('createdAt')
        if not ts:
            return 0.0
        try:
            created = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (now - created).total_seconds()
        except Exception:
            return 0.0

    def reanalyze(self) -> Dict[str, List[Any]]:
        """Batch pass that corrects over-fragmentation from greedy assignment.

        Two things happen:
        1. Merge: any pair of clusters whose centroids are near-identical
           (>= merge_threshold) are almost certainly the same topic phrased
           differently — the smaller/newer one is folded into the larger.
        2. Prune/reclassify: tiny, single-mention clusters that never grew and
           are old enough to have had a chance to accumulate more segments are
           either folded into their closest reasonably-similar neighbor
           (>= reclassify_threshold) or discarded entirely as noise if no
           such neighbor exists.

        Returns {'merged': [(absorbed_id, survivor_id), ...], 'removed': [id, ...]}
        Callers are responsible for propagating these changes (e.g. emitting
        nodesRemoved in a graph patch) to any downstream store/UI.
        """
        merged: List[Tuple[str, str]] = []
        removed: List[str] = []

        if len(self.clusters) < 2:
            return {'merged': merged, 'removed': removed}

        # --- Pass 1: merge near-duplicate clusters ---
        changed = True
        while changed and len(self.clusters) > 1:
            changed = False
            ids = list(self.clusters.keys())
            centroids = np.stack([self.clusters[i]['centroid'] for i in ids])
            norms = np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-10
            normed = centroids / norms
            sim_matrix = normed.dot(normed.T)
            np.fill_diagonal(sim_matrix, -1.0)

            best_i, best_j = np.unravel_index(np.argmax(sim_matrix), sim_matrix.shape)
            best_sim = float(sim_matrix[best_i, best_j])
            if best_sim < self.merge_threshold:
                break

            id_a, id_b = ids[best_i], ids[best_j]
            a, b = self.clusters[id_a], self.clusters[id_b]
            # absorb the smaller (by weight) into the larger; ties favor the older cluster
            if a.get('weight', 0) >= b.get('weight', 0):
                survivor_id, absorbed_id = id_a, id_b
            else:
                survivor_id, absorbed_id = id_b, id_a
            survivor, absorbed = self.clusters[survivor_id], self.clusters[absorbed_id]

            total = survivor.get('count', 1) + absorbed.get('count', 1)
            survivor['centroid'] = (
                survivor['centroid'] * survivor.get('count', 1) + absorbed['centroid'] * absorbed.get('count', 1)
            ) / total
            survivor['count'] = total
            survivor['weight'] = survivor.get('weight', 0) + absorbed.get('weight', 0)
            survivor['segmentIds'] = list(dict.fromkeys(survivor.get('segmentIds', []) + absorbed.get('segmentIds', [])))
            survivor['lastSeen'] = max(survivor.get('lastSeen') or '', absorbed.get('lastSeen') or '')

            del self.clusters[absorbed_id]
            merged.append((absorbed_id, survivor_id))
            changed = True

        # --- Pass 2: reclassify or prune weak, isolated single-mention clusters ---
        if len(self.clusters) > 1:
            ids = list(self.clusters.keys())
            centroids = np.stack([self.clusters[i]['centroid'] for i in ids])
            norms = np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-10
            normed = centroids / norms
            sim_matrix = normed.dot(normed.T)
            np.fill_diagonal(sim_matrix, -1.0)

            for idx, cid in enumerate(ids):
                if cid not in self.clusters:
                    continue  # already merged/removed earlier this pass
                cluster = self.clusters[cid]
                is_weak = cluster.get('count', 1) <= 1 and cluster.get('weight', 0) <= self.prune_max_weight
                if not is_weak:
                    continue
                if self._age_seconds(cluster) < self.prune_min_age_seconds:
                    continue  # give it a chance to grow before judging it

                sims_row = sim_matrix[idx]
                best_idx = int(np.argmax(sims_row))
                best_sim = float(sims_row[best_idx])
                best_cid = ids[best_idx]

                if best_cid in self.clusters and best_sim >= self.reclassify_threshold:
                    survivor = self.clusters[best_cid]
                    total = survivor.get('count', 1) + cluster.get('count', 1)
                    survivor['centroid'] = (
                        survivor['centroid'] * survivor.get('count', 1) + cluster['centroid'] * cluster.get('count', 1)
                    ) / total
                    survivor['count'] = total
                    survivor['weight'] = survivor.get('weight', 0) + cluster.get('weight', 0)
                    survivor['segmentIds'] = list(dict.fromkeys(survivor.get('segmentIds', []) + cluster.get('segmentIds', [])))
                    del self.clusters[cid]
                    merged.append((cid, best_cid))
                else:
                    # No reasonable home for this fragment — discard as noise
                    del self.clusters[cid]
                    removed.append(cid)

        return {'merged': merged, 'removed': removed}


__all__ = ['TopicManager']
