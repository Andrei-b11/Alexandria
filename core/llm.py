"""Motores de IA en streaming: Claude, Gemini, Groq, OpenAI y Ollama.

Todos comparten la misma interfaz: reciben un mensaje de sistema y una lista de
mensajes [{"role": "user"|"assistant", "content": str}] y van entregando la
respuesta token a token mediante el callback `on_token`.

La memoria de documentos (embeddings) es siempre local; cambiar de motor no
requiere volver a procesar nada.
"""
import json

import requests

from . import config


class LLMError(Exception):
    pass


def stream_chat(cfg: dict, system: str, messages: list[dict], on_token) -> None:
    backend = cfg.get("backend", "claude")
    if backend == "claude":
        _stream_claude(cfg, system, messages, on_token)
    elif backend == "gemini":
        _stream_gemini(cfg, system, messages, on_token)
    elif backend == "groq":
        _stream_openai_compat(
            cfg, system, messages, on_token,
            base_url="https://api.groq.com/openai/v1",
            key_field="groq_api_key", model_field="groq_model",
            provider="Groq",
        )
    elif backend == "openai":
        _stream_openai_compat(
            cfg, system, messages, on_token,
            base_url="https://api.openai.com/v1",
            key_field="openai_api_key", model_field="openai_model",
            provider="OpenAI",
        )
    elif backend == "ollama":
        _stream_ollama(cfg, system, messages, on_token)
    else:
        raise LLMError(f"Motor de IA desconocido: {backend}")


# --------------------------------------------------------------- Claude
def _stream_claude(cfg: dict, system: str, messages: list[dict], on_token) -> None:
    import anthropic

    api_key = config.get_api_key(cfg, "anthropic_api_key")
    if not api_key:
        raise LLMError(
            "Falta la API key de Anthropic. Configúrala en Ajustes "
            "(o en la variable de entorno ANTHROPIC_API_KEY)."
        )
    client = anthropic.Anthropic(api_key=api_key)
    model = cfg.get("claude_model", "claude-sonnet-5")
    try:
        with client.messages.stream(
            model=model,
            max_tokens=4096,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                on_token(text)
    except anthropic.AuthenticationError as e:
        raise LLMError("API key de Anthropic inválida.") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("No hay conexión con la API de Anthropic.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Error de la API de Anthropic ({e.status_code}): {e.message}") from e


# --------------------------------------------------------------- Gemini
def _stream_gemini(cfg: dict, system: str, messages: list[dict], on_token) -> None:
    api_key = config.get_api_key(cfg, "gemini_api_key")
    if not api_key:
        raise LLMError(
            "Falta la API key de Gemini. Consigue una gratis en "
            "https://aistudio.google.com y pégala en Ajustes."
        )
    model = cfg.get("gemini_model", "gemini-2.5-flash")
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:streamGenerateContent?alt=sse"
    )
    try:
        resp = requests.post(
            url,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=body,
            stream=True,
            timeout=(10, 300),
        )
    except requests.RequestException as e:
        raise LLMError("No hay conexión con la API de Gemini.") from e
    if resp.status_code in (401, 403):
        raise LLMError("API key de Gemini inválida o sin permisos.")
    if resp.status_code == 404:
        raise LLMError(f"El modelo de Gemini «{model}» no existe o no está disponible.")
    if resp.status_code != 200:
        raise LLMError(f"Error de la API de Gemini ({resp.status_code}): {resp.text[:200]}")

    for data in _iter_sse(resp):
        for cand in data.get("candidates", []):
            for part in (cand.get("content") or {}).get("parts", []):
                text = part.get("text", "")
                if text:
                    on_token(text)


# ------------------------------------------- Groq / OpenAI (API compatible)
def _stream_openai_compat(
    cfg: dict, system: str, messages: list[dict], on_token,
    *, base_url: str, key_field: str, model_field: str, provider: str,
) -> None:
    api_key = config.get_api_key(cfg, key_field)
    if not api_key:
        raise LLMError(f"Falta la API key de {provider}. Configúrala en Ajustes.")
    model = cfg.get(model_field, "")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": True,
    }
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            stream=True,
            timeout=(10, 300),
        )
    except requests.RequestException as e:
        raise LLMError(f"No hay conexión con la API de {provider}.") from e
    if resp.status_code == 401:
        raise LLMError(f"API key de {provider} inválida.")
    if resp.status_code == 404:
        raise LLMError(f"El modelo «{model}» no existe en {provider}.")
    if resp.status_code != 200:
        raise LLMError(f"Error de {provider} ({resp.status_code}): {resp.text[:200]}")

    for data in _iter_sse(resp):
        for choice in data.get("choices", []):
            token = (choice.get("delta") or {}).get("content", "")
            if token:
                on_token(token)


def _iter_sse(resp):
    """Itera los eventos `data: {...}` de una respuesta SSE."""
    for line in resp.iter_lines(chunk_size=1):
        if not line:
            continue
        line = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if chunk == "[DONE]":
            return
        try:
            yield json.loads(chunk)
        except json.JSONDecodeError:
            continue


# --------------------------------------------------------------- Ollama
def _stream_ollama(cfg: dict, system: str, messages: list[dict], on_token) -> None:
    url = cfg.get("ollama_url", "http://localhost:11434").rstrip("/")
    model = cfg.get("ollama_model", "llama3.1")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
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

    for line in resp.iter_lines(chunk_size=1):
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
