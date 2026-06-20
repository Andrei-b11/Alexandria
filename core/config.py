"""Carga y guardado de la configuración de la aplicación."""
import json
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.json"
STORAGE_DIR = APP_DIR / "storage"
CHROMA_DIR = STORAGE_DIR / "chroma"
REGISTRY_PATH = STORAGE_DIR / "documents.json"

DEFAULTS = {
    # Motor de IA: "claude" (API) o "ollama" (local)
    "backend": "claude",
    "anthropic_api_key": "",
    "claude_model": "claude-opus-4-8",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "qwen2.5:14b",
    # Modelo de embeddings (memoria). Multilingüe, ideal para español.
    "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    # Nº de fragmentos relevantes que se recuperan por pregunta.
    "top_k": 5,
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save_config(cfg: dict) -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    # Solo persistimos las claves conocidas.
    data = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_api_key(cfg: dict) -> str:
    """La clave de la config tiene prioridad; si no, variable de entorno."""
    return (cfg.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
