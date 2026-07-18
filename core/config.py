"""Carga y guardado de la configuración de la aplicación."""
import json
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.json"
STORAGE_DIR = APP_DIR / "storage"
CHROMA_DIR = STORAGE_DIR / "chroma"
REGISTRY_PATH = STORAGE_DIR / "documents.json"
NOTES_PATH = STORAGE_DIR / "notes.json"
SPACES_PATH = STORAGE_DIR / "spaces.json"

DEFAULTS = {
    # Motor de IA activo: "claude", "gemini", "groq", "openai" u "ollama".
    "backend": "claude",
    # --- Claude (Anthropic) ---
    "anthropic_api_key": "",
    "claude_model": "claude-sonnet-5",
    # --- Gemini (Google) ---
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    # --- Groq ---
    "groq_api_key": "",
    "groq_model": "llama-3.3-70b-versatile",
    # --- OpenAI ---
    "openai_api_key": "",
    "openai_model": "gpt-4o-mini",
    # --- Ollama (local) ---
    "ollama_url": "http://localhost:11434",
    "ollama_model": "qwen2.5:14b",
    # --- LM Studio (local, API compatible con OpenAI) ---
    "lmstudio_url": "http://localhost:1234",
    "lmstudio_model": "",
    "lmstudio_num_ctx": 8192,  # informativo, para el medidor de contexto
    # Modo de chat: "app" (RAG + agente integrado) o "directo" (chat puro
    # con el modelo, como usar Ollama/LM Studio a pelo).
    "chat_mode": "app",
    # --- Apariencia del chat ---
    # Tema global: "dark" (oscuro) o "light" (claro con acentos grises).
    "theme": "dark",
    # Estilo: "alexandria" (burbujas) o "lmstudio" (minimalista, texto plano).
    "chat_style": "alexandria",
    "chat_font_size": 13.5,
    "chat_accent": "#8ea7ff",
    "chat_bubble_opacity": 170,     # 0-255
    "chat_show_sources": True,
    "chat_thinking_anim": True,
    # Modelo de embeddings (memoria). Multilingüe, ideal para español.
    # La memoria es LOCAL y compartida por todos los motores de IA.
    "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    # Nº de fragmentos relevantes que se recuperan por pregunta.
    "top_k": 6,
    # Nº de turnos de conversación que se recuerdan en el chat.
    "history_turns": 6,
    # Buscar en internet cuando los documentos no tienen la respuesta.
    "web_search": True,
    # Ventana de contexto y persistencia del modelo en Ollama.
    "ollama_num_ctx": 8192,
    "ollama_keep_alive": "30m",
}

# Metadatos de cada motor para la interfaz.
BACKENDS = {
    "claude": {"label": "Claude (Anthropic)", "key_field": "anthropic_api_key", "model_field": "claude_model", "local": False},
    "gemini": {"label": "Gemini (Google)", "key_field": "gemini_api_key", "model_field": "gemini_model", "local": False},
    "groq": {"label": "Groq", "key_field": "groq_api_key", "model_field": "groq_model", "local": False},
    "openai": {"label": "OpenAI", "key_field": "openai_api_key", "model_field": "openai_model", "local": False},
    "ollama": {"label": "Ollama (local)", "key_field": None, "model_field": "ollama_model", "local": True},
    "lmstudio": {"label": "LM Studio (local)", "key_field": None, "model_field": "lmstudio_model", "local": True},
}

# Variables de entorno aceptadas como alternativa a la clave guardada.
_ENV_KEYS = {
    "anthropic_api_key": ("ANTHROPIC_API_KEY",),
    "gemini_api_key": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "groq_api_key": ("GROQ_API_KEY",),
    "openai_api_key": ("OPENAI_API_KEY",),
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


def get_api_key(cfg: dict, field: str = "anthropic_api_key") -> str:
    """La clave de la config tiene prioridad; si no, variables de entorno."""
    value = (cfg.get(field) or "").strip()
    if value:
        return value
    for env in _ENV_KEYS.get(field, ()):
        value = os.environ.get(env, "").strip()
        if value:
            return value
    return ""


def active_model(cfg: dict) -> str:
    """Nombre del modelo del motor activo (para mostrar en la interfaz)."""
    backend = cfg.get("backend", "claude")
    meta = BACKENDS.get(backend, BACKENDS["claude"])
    return cfg.get(meta["model_field"], "")
