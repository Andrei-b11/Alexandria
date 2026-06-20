"""Motor RAG: recupera fragmentos relevantes y genera la respuesta."""
from .llm import stream_answer

SYSTEM_PROMPT = (
    "Eres un asistente experto de una empresa que responde preguntas basándote "
    "ÚNICAMENTE en los fragmentos de documentos proporcionados como contexto.\n"
    "Reglas:\n"
    "- Responde siempre en español, de forma clara, directa y concisa.\n"
    "- Usa solo la información del contexto. Si la respuesta no aparece en el "
    "contexto, di explícitamente: 'No encuentro esa información en los documentos.'\n"
    "- Cuando sea útil, indica de qué documento sale el dato, p. ej. (Fuente: informe.pdf).\n"
    "- No inventes datos ni uses conocimiento externo.\n"
    "- Da directamente la respuesta final, sin describir tu razonamiento interno."
)


def _build_context(results: list[dict]) -> str:
    blocks = []
    for i, r in enumerate(results, start=1):
        blocks.append(f"[Fuente {i}: {r['source']}]\n{r['text']}")
    return "\n\n---\n\n".join(blocks)


class RagEngine:
    def __init__(self, store, cfg: dict):
        self.store = store
        self.cfg = cfg  # se lee en vivo; los cambios de Ajustes aplican al instante

    def answer(self, question: str, on_token) -> list[str]:
        top_k = int(self.cfg.get("top_k", 5))
        results = self.store.query(question, top_k=top_k)
        if not results:
            on_token(
                "No hay documentos en la base de conocimiento todavía. "
                "Sube algún PDF o documento primero."
            )
            return []

        context = _build_context(results)
        user_msg = (
            f"Contexto extraído de los documentos:\n\n{context}\n\n"
            f"Pregunta del usuario: {question}"
        )
        stream_answer(self.cfg, SYSTEM_PROMPT, user_msg, on_token)

        # Fuentes únicas conservando el orden de relevancia.
        seen, sources = set(), []
        for r in results:
            if r["source"] not in seen:
                seen.add(r["source"])
                sources.append(r["source"])
        return sources
