"""Utilidades para hablar con el servidor local de Ollama (embebido o del sistema)."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import requests

APP_DIR = Path(__file__).resolve().parent.parent
# Si colocas el binario aquí, la app usa SU PROPIO Ollama (modo embebido/portátil):
#   vendor/ollama/ollama.exe   y los modelos en  vendor/ollama/models
VENDOR_DIR = APP_DIR / "vendor" / "ollama"


class OllamaError(Exception):
    pass


# Modelos recomendados para análisis de documentos (RAG) en español.
# Pensados para una GPU con 16 GB de VRAM (caben enteros y van rápidos).
RECOMMENDED_MODELS = [
    ("qwen2.5:14b", "★ Recomendado · ~9 GB · mejor calidad y español, cabe en tu GPU"),
    ("qwen2.5:7b", "Rápido y ligero · ~4.7 GB"),
    ("llama3.1:8b", "Equilibrado · ~4.9 GB"),
    ("gemma2:9b", "Alternativa de Google · ~5.4 GB"),
]


def find_ollama_binary() -> str | None:
    """Devuelve la ruta al binario de Ollama: primero el embebido, luego el del sistema."""
    for name in ("ollama.exe", "ollama"):
        candidate = VENDOR_DIR / name
        if candidate.exists():
            return str(candidate)
    found = shutil.which("ollama")
    if found:
        return found
    # Ubicación típica de instalación en Windows.
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    if local.exists():
        return str(local)
    return None


def ensure_server(url: str, timeout: float = 25.0) -> bool:
    """Arranca el servidor de Ollama si no está ya en ejecución. True si está disponible."""
    if is_running(url, timeout=2.0):
        return True
    exe = find_ollama_binary()
    if not exe:
        return False

    env = dict(os.environ)
    # En modo embebido, los modelos viven junto a la app (portátil).
    if VENDOR_DIR.exists():
        env.setdefault("OLLAMA_MODELS", str(VENDOR_DIR / "models"))

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # sin ventana de consola
    try:
        subprocess.Popen(
            [exe, "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception:  # noqa: BLE001
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_running(url, timeout=2.0):
            return True
        time.sleep(0.8)
    return False


def is_running(url: str, timeout: float = 3.0) -> bool:
    try:
        r = requests.get(f"{url.rstrip('/')}/api/tags", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def list_models(url: str, timeout: float = 4.0) -> list[str]:
    try:
        r = requests.get(f"{url.rstrip('/')}/api/tags", timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise OllamaError(str(e)) from e
    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]


def warmup_model(url: str, model: str, keep_alive: str = "30m",
                 num_ctx: int = 8192) -> None:
    """Precarga el modelo en memoria (VRAM) para que la primera respuesta
    no pague el coste de cargar el modelo. Llamar en segundo plano.

    `num_ctx` debe coincidir con el usado en las peticiones de chat: si las
    opciones cambian, Ollama vuelve a recargar el modelo."""
    try:
        requests.post(
            f"{url.rstrip('/')}/api/chat",
            json={
                "model": model, "messages": [], "keep_alive": keep_alive,
                "options": {"num_ctx": num_ctx},
            },
            timeout=(5, 180),
        )
    except requests.RequestException:
        pass  # sin conexión o modelo remoto: no es crítico


def pull_model(url: str, model: str, on_progress) -> None:
    """Descarga/actualiza un modelo. on_progress(status:str, percent:int).

    percent es -1 cuando no hay información de tamaño todavía.
    """
    url = url.rstrip("/")
    try:
        resp = requests.post(
            f"{url}/api/pull",
            json={"model": model, "stream": True},
            stream=True,
            timeout=(10, None),  # conexión 10s, lectura sin límite
        )
    except requests.exceptions.ConnectionError as e:
        raise OllamaError(
            f"No se pudo conectar con Ollama en {url}. ¿Está en ejecución?"
        ) from e
    if resp.status_code != 200:
        raise OllamaError(f"Ollama respondió {resp.status_code}: {resp.text[:200]}")

    for line in resp.iter_lines():
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("error"):
            raise OllamaError(data["error"])
        status = data.get("status", "")
        total = data.get("total")
        completed = data.get("completed")
        percent = int(completed / total * 100) if total and completed else -1
        on_progress(status, percent)
        if status == "success":
            return
