"""Local model manager for embeddings and generation.

This module expects a `models/manifest.json` produced by `scripts/download_models.py`.
It provides a small helper class to lazily load the sentence-transformers embedding
model and a seq2seq generation model (e.g., `flan-t5-small`) from the local paths.
"""
from pathlib import Path
import json
from typing import Optional, List


class LocalModelManager:
    def __init__(self, models_root: Optional[Path] = None):
        # default to backend/models (two levels up from this file: backend)
        default_root = Path(models_root) if models_root else (Path(__file__).resolve().parents[2] / 'models')
        self.root = Path(default_root)
        self.manifest = {}
        self._embed = None
        self._pipeline = None
        self._load_manifest()

    def _load_manifest(self) -> None:
        manifest_path = self.root / 'manifest.json'
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                self.manifest = json.load(f)

    def embedding_model_path(self) -> Optional[str]:
        return self.manifest.get('embed_model')

    def gen_model_path(self) -> Optional[str]:
        return self.manifest.get('gen_model')

    def load_embedding(self):
        if self._embed is None:
            try:
                from sentence_transformers import SentenceTransformer
                path = self.embedding_model_path()
                if path and Path(path).exists():
                    self._embed = SentenceTransformer(path)
                else:
                    # fallback to HF id (will download on first use)
                    self._embed = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as exc:
                raise RuntimeError(f'Failed to load embedding model: {exc}')
        return self._embed

    def embed(self, texts: List[str]):
        model = self.load_embedding()
        return model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

    def load_generator_pipeline(self):
        if self._pipeline is None:
            try:
                from transformers import pipeline
                path = self.gen_model_path()
                # Prefer explicitly disabling remote code execution when supported.
                try:
                    if path and Path(path).exists():
                        # load pipeline from local directory (disable remote code execution)
                        self._pipeline = pipeline('text2text-generation', model=path, tokenizer=path, device=-1, trust_remote_code=False)
                    else:
                        # fallback to HF model id (this may download)
                        self._pipeline = pipeline('text2text-generation', model='google/flan-t5-small', device=-1, trust_remote_code=False)
                except TypeError:
                    # older transformers versions may not accept `trust_remote_code`; fall back safely
                    if path and Path(path).exists():
                        self._pipeline = pipeline('text2text-generation', model=path, tokenizer=path, device=-1)
                    else:
                        self._pipeline = pipeline('text2text-generation', model='google/flan-t5-small', device=-1)
            except Exception as exc:
                raise RuntimeError(f'Failed to load generator pipeline: {exc}')
        return self._pipeline

    def generate(self, prompt: str, max_length: int = 64, num_return_sequences: int = 1):
        pipe = self.load_generator_pipeline()
        outs = pipe(prompt, max_length=max_length, num_return_sequences=num_return_sequences)
        return [o.get('generated_text') for o in outs]


__all__ = ['LocalModelManager']
