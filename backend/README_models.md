# Model downloads for YapMap local MVP

This folder contains helper scripts to download and manage local models used by the MVP.

Supported downloads (script `scripts/download_models.py`):

- `sentence-transformers/all-MiniLM-L6-v2` — embedding model (small, CPU-friendly)
- `google/flan-t5-small` — generation model for summarization & prompt generation
- `vosk-model-small-en-us-0.15` — Vosk small English STT model for CPU streaming

Usage
1. Install minimal Python tools for downloading (no heavy ML libs required for the downloader):

```powershell
cd backend
python -m pip install --upgrade pip
python -m pip install huggingface-hub tqdm requests
```

2. Run the downloader (this will fetch models into `backend/models/`):

```powershell
python scripts/download_models.py --models-dir models
```

3. A `backend/models/manifest.json` file will be created mapping logical names to local paths.

Notes
- The downloader uses `huggingface_hub.snapshot_download` for HF models and an HTTP download for Vosk. If you plan to run the models, install the packages from `backend/requirements.txt` or a virtualenv as appropriate.
- For running CPU inference with `transformers`, you will need `torch` installed. For lower memory/CPU usage, consider exporting to ONNX and running via `onnxruntime`.
- The Vosk model requires `ffmpeg` / appropriate audio transcoding for some input formats. See `pydub` / `ffmpeg` docs.
