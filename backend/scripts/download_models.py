#!/usr/bin/env python3
"""Download local models for YapMap MVP:
- sentence-transformers/all-MiniLM-L6-v2 (embeddings)
- google/flan-t5-small (generator)
- vosk small english model (STT)

Writes a `manifest.json` under the models directory with local paths.
"""
from pathlib import Path
import json
import argparse
from huggingface_hub import snapshot_download
import requests
from tqdm import tqdm
import zipfile


def download_hf_model(repo_id: str, out_dir: Path) -> str:
    print(f"Downloading HF model {repo_id} into {out_dir}")
    path = snapshot_download(repo_id=repo_id, cache_dir=str(out_dir))
    print(f"Downloaded HF model {repo_id} -> {path}")
    return str(path)


def download_vosk(url: str, out_dir: Path) -> str:
    out_zip = out_dir / "vosk_model.zip"
    print(f"Downloading Vosk model from {url} to {out_zip}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(out_zip, "wb") as f, tqdm(total=total, unit='B', unit_scale=True, desc='vosk') as pbar:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    print("Extracting Vosk model...")
    with zipfile.ZipFile(out_zip, 'r') as z:
        z.extractall(out_dir)

    # remove zip
    try:
        out_zip.unlink()
    except Exception:
        pass

    # find extracted dir
    for child in out_dir.iterdir():
        if child.is_dir() and 'vosk-model' in child.name:
            return str(child)

    return str(out_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models-dir', default='models', help='Directory to write downloaded models')
    args = parser.parse_args()

    base = Path(args.models_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    hf_dir = base / 'hf'
    hf_dir.mkdir(exist_ok=True)
    manifest = {}

    hf_models = {
        'embed_model': 'sentence-transformers/all-MiniLM-L6-v2',
        'gen_model': 'google/flan-t5-small',
    }

    for key, repo in hf_models.items():
        try:
            print(f"Downloading {key} from HF repo {repo}...")
            path = download_hf_model(repo, hf_dir)
            manifest[key] = path
        except Exception as e:
            print(f"Failed to download {repo}: {e}")

    # Vosk model (small English)
    vosk_url = 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip'
    vosk_dir = base / 'vosk'
    vosk_dir.mkdir(exist_ok=True)
    try:
        path = download_vosk(vosk_url, vosk_dir)
        manifest['vosk_model'] = path
    except Exception as e:
        print(f"Failed to download Vosk model: {e}")

    manifest_path = base / 'manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print('Download complete. Manifest written to', manifest_path)
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
