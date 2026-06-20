"""Motores de IA: Claude (API) y Ollama (local). Respuesta en streaming."""
import json

import requests

from . import config


class LLMError(Exception):
    pass


def stream_answer(cfg: dict, system: str, user: str, on_token) -> None:
    backend = cfg.get("backend", "claude")
    if backend == "claude":
        _stream_claude(cfg, system, user, on_token)
    elif backend == "ollama":
        _stream_ollama(cfg, system, user, on_token)
    else:
        raise LLMError(f"Motor de IA desconocido: {backend}")


def _stream_claude(cfg: dict, system: str, user: str, on_token) -> None:
    import anthropic

    api_key = config.get_api_key(cfg)
    if not api_key:
        raise LLMError(
            "Falta la API key de Anthropic. Configúrala en Ajustes "
            "(o en la variable de entorno ANTHROPIC_API_KEY)."
        )
    client = anthropic.Anthropic(api_key=api_key)
    model = cfg.get("claude_model", "claude-opus-4-8")
    try:
        with client.messages.stream(
            model=model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            for text in stream.text_stream:
                on_token(text)
    except anthropic.AuthenticationError as e:
        raise LLMError("API key de Anthropic inválida.") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("No hay conexión con la API de Anthropic.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Error de la API de Anthropic ({e.status_code}): {e.message}") from e


def _stream_ollama(cfg: dict, system: str, user: str, on_token) -> None:
    url = cfg.get("ollama_url", "http://localhost:11434").rstrip("/")
    model = cfg.get("ollama_model", "llama3.1")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
    }
    try:
        resp = requests.post(
            f"{url}/api/chat", json=payload, stream=True, timeout=300
        )
    except requests.exceptions.ConnectionError as e:
        raise LLMError(
            f"No se pudo conectar con Ollama en {url}. "
            "¿Está Ollama en ejecución? (comando: 'ollama serve')"
        ) from e
    if resp.status_code == 404:
        raise LLMError(
            f"El modelo '{model}' no está en Ollama. "
            f"Descárgalo con: ollama pull {model}"
        )
    if resp.status_code != 200:
        raise LLMError(f"Ollama respondió con error {resp.status_code}: {resp.text[:200]}")

    for line in resp.iter_lines():
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("error"):
            raise LLMError(f"Ollama: {data['error']}")
        token = (data.get("message") or {}).get("content", "")
        if token:
            on_token(token)
        if data.get("done"):
            break
