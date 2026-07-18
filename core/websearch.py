"""Búsqueda web sin dependencias externas ni claves de API.

Fuente principal: DuckDuckGo Lite (HTML sencillo y estable). Respaldo:
la API de búsqueda de Wikipedia en español. Se usa cuando el RAG no
encuentra nada relevante en los documentos. Cualquier fallo (sin red,
bloqueo, cambio de HTML…) devuelve lista vacía y la app sigue funcionando
solo con documentos y el conocimiento del modelo.
"""
import html
import re
from urllib.parse import quote, unquote

import requests

# Ojo: el UA completo de Chrome dispara la página-desafío (202) de DuckDuckGo;
# este UA simple pasa sin problemas.
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

_TAG_RE = re.compile(r"<[^>]+>")
# Recorre el HTML en orden: cada resultado es un enlace seguido de su snippet.
_LITE_RE = re.compile(
    r"href=\"(?P<url>[^\"]+)\"[^>]*class=['\"]result-link['\"]>(?P<title>.*?)</a>"
    r"|class=['\"]result-snippet['\"]>(?P<snippet>.*?)</td>",
    re.S,
)


def _clean(fragment: str) -> str:
    return html.unescape(_TAG_RE.sub("", fragment)).strip()


def _is_ad(url: str, title: str) -> bool:
    return (
        "more info" in title.lower()
        or "ads-by-microsoft" in url
        or ("vqd=" in url and "iurl=" in url)
        or "duckduckgo.com/y.js" in url
    )


def _search_ddg_lite(query: str, max_results: int, timeout: float) -> list[dict]:
    resp = requests.post(
        "https://lite.duckduckgo.com/lite/",
        data={"q": query},
        headers={"User-Agent": _UA},
        timeout=timeout,
    )
    if resp.status_code != 200:
        return []

    results: list[dict] = []
    current: dict | None = None
    for m in _LITE_RE.finditer(resp.text):
        if m.group("url") is not None:
            url = m.group("url")
            title = _clean(m.group("title"))
            # DuckDuckGo puede devolver URLs de redirección con el destino en `uddg`
            r = re.search(r"uddg=([^&\"]+)", url)
            if r:
                url = unquote(r.group(1))
            if _is_ad(url, title):
                current = None
                continue
            current = {"title": title, "url": url, "snippet": ""}
            results.append(current)
        elif current is not None:
            current["snippet"] = _clean(m.group("snippet"))
            current = None
        if len(results) >= max_results and current is None:
            break
    return [r for r in results if r["title"]][:max_results]


def _search_wikipedia(query: str, max_results: int, timeout: float) -> list[dict]:
    resp = requests.get(
        "https://es.wikipedia.org/w/api.php",
        params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": max_results, "srprop": "snippet",
        },
        headers={"User-Agent": "Alexandria/1.0"},
        timeout=timeout,
    )
    resp.raise_for_status()
    hits = resp.json().get("query", {}).get("search", [])
    return [
        {
            "title": h.get("title", ""),
            "url": "https://es.wikipedia.org/wiki/" + quote(h.get("title", "").replace(" ", "_")),
            "snippet": _clean(h.get("snippet", "")),
        }
        for h in hits
    ]


def search_web(query: str, max_results: int = 4, timeout: float = 8.0) -> list[dict]:
    """Devuelve [{"title", "url", "snippet"}, …] o [] si todo falla."""
    try:
        results = _search_ddg_lite(query, max_results, timeout)
        if results:
            return results
    except requests.RequestException:
        pass
    try:
        return _search_wikipedia(query, max_results, timeout)
    except requests.RequestException:
        return []
