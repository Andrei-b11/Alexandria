"""Utilidades para hablar con el servidor local de LM Studio.

LM Studio expone una API compatible con OpenAI en http://localhost:1234/v1
(sin clave). Aquí solo se necesita comprobar si está activo y listar los
modelos cargados/descargados.
"""
import requests


class LMStudioError(Exception):
    pass


def is_running(url: str, timeout: float = 3.0) -> bool:
    try:
        r = requests.get(f"{url.rstrip('/')}/v1/models", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def list_models(url: str, timeout: float = 4.0) -> list[str]:
    try:
        r = requests.get(f"{url.rstrip('/')}/v1/models", timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise LMStudioError(str(e)) from e
    return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
