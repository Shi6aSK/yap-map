"""
NLP topic extraction service using KeyBERT + sentence-transformers.
Model: all-mpnet-base-v2 (~420 MB, downloads automatically on first use).
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

_kw_model: Any = None
_st_model: Any = None


def _get_models():
    """Lazy-load KeyBERT + sentence-transformers model (downloads on first call)."""
    global _kw_model, _st_model
    if _kw_model is not None:
        return _kw_model, _st_model
    try:
        from sentence_transformers import SentenceTransformer
        from keybert import KeyBERT
        logger.info("Loading sentence-transformers model 'all-mpnet-base-v2' (downloading if needed)…")
        _st_model = SentenceTransformer("all-mpnet-base-v2")
        _kw_model = KeyBERT(model=_st_model)
        logger.info("NLP model ready.")
    except Exception as exc:
        logger.warning("Could not load KeyBERT/sentence-transformers: %s. Falling back to frequency extraction.", exc)
        _kw_model = None
        _st_model = None
    return _kw_model, _st_model


_STOP = set([
    "the","and","for","are","you","that","with","this","have","from","was",
    "what","when","where","how","a","an","in","on","of","to","is","it","i",
    "we","they","be","as","at","by","or","if","but","not","do","so","can",
    "will","just","about","your","yeah","yes","no","um","uh","okay","ok",
    "like","right","well","actually","basically","kind","got","get","going",
    "think","know","want","really","very","much","still","even","maybe",
    "something","way","thing","things","make","time","see","use","also",
    "never","always","every","lot","many","more","most","some","another",
    "other","new","old","good","great","work","need","come","say","said",
    "look","then","than","here","there","because","though","while","already",
])

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}", re.IGNORECASE)


def _is_noisy(label: str) -> bool:
    if _UUID_RE.search(label):
        return True
    clean = re.sub(r"[^a-z0-9]", "", label.lower())
    if len(clean) > 8 and all(c in "0123456789abcdef" for c in clean):
        return True
    return False


def _fallback_extract(text: str, top_n: int) -> dict:
    """Simple frequency-based fallback when model not available."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    words = [w for w in words if w not in _STOP]
    counts = Counter(words)
    # Build simple bigrams
    bigrams = []
    toks = [w for w in text.lower().split() if re.match(r"[a-z]{3,}", w) and w not in _STOP]
    for i in range(len(toks) - 1):
        bigrams.append(f"{toks[i]} {toks[i+1]}")
    bi_counts = Counter(bigrams)

    candidates = {}
    for w, c in counts.items():
        candidates[w] = c * 1.5
    for b, c in bi_counts.items():
        candidates[b] = max(candidates.get(b, 0), c * 3)

    sorted_cands = sorted(candidates.items(), key=lambda x: -x[1])[:top_n]
    topics = [{"label": k, "score": round(v / max(1, sorted_cands[0][1]), 3)} for k, v in sorted_cands if k]
    return {"topics": topics, "edges": []}


def extract_graph_topics(text: str, top_n: int = 30) -> dict:
    """
    Extract keyphrases and build a semantic similarity graph.
    Returns: { topics: [{label, score}], edges: [{source, target, value}] }
    """
    if not text or len(text.strip()) < 30:
        return {"topics": [], "edges": []}

    kw_model, st_model = _get_models()

    if kw_model is None:
        return _fallback_extract(text, top_n)

    # Extract keywords with MMR for diversity
    try:
        raw_kws = kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 3),
            stop_words="english",
            use_mmr=True,
            diversity=0.55,
            top_n=min(top_n, 40),
        )
    except Exception as exc:
        logger.warning("KeyBERT extraction error: %s", exc)
        return _fallback_extract(text, top_n)

    if not raw_kws:
        return _fallback_extract(text, top_n)

    # Filter noise (UUIDs, pure numbers, very short tokens)
    kws = [(kw, score) for kw, score in raw_kws
           if kw and len(kw) >= 3 and not _is_noisy(kw)]

    topics = [{"label": kw, "score": round(float(score), 4)} for kw, score in kws]

    # Build semantic similarity edges
    edges: list[dict] = []
    if len(kws) >= 2 and st_model is not None:
        try:
            from sentence_transformers import util
            labels = [kw for kw, _ in kws]
            embeddings = st_model.encode(labels, convert_to_tensor=True, show_progress_bar=False)
            cos_scores = util.cos_sim(embeddings, embeddings)
            for i in range(len(labels)):
                for j in range(i + 1, len(labels)):
                    sim = float(cos_scores[i][j])
                    if 0.25 < sim < 0.99:  # exclude self-similar pairs
                        edges.append({
                            "source": labels[i],
                            "target": labels[j],
                            "value": round(sim * 5, 2),
                        })
        except Exception as exc:
            logger.warning("Edge construction failed: %s", exc)

    return {"topics": topics, "edges": edges}
