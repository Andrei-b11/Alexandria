"""Motor RAG: recupera fragmentos relevantes y genera la respuesta.

Mantiene memoria de la conversación (los últimos N turnos) para que se puedan
hacer preguntas de seguimiento, y permite limitar la búsqueda a un subconjunto
de documentos (categoría o fuentes marcadas por el usuario).
"""
from .llm import stream_chat

SYSTEM_PROMPT = (
    "Eres un asistente experto que responde preguntas basándose en el contexto proporcionado, "
    "el cual puede incluir fragmentos de documentos de la base de conocimiento y también "
    "notas, tareas y textos del espacio actual de trabajo (canvas).\n"
    "Reglas:\n"
    "- Responde siempre en español, de forma clara, directa y concisa.\n"
    "- Usa solo la información del contexto (documentos y elementos del espacio).\n"
    "- Si la respuesta no aparece en el contexto, di explícitamente: 'No encuentro esa información en las fuentes ni en el espacio.'\n"
    "- Cuando sea útil, indica la procedencia del dato, p. ej. (Fuente: informe.pdf) o (Nota: Título de la nota) o (Tarea: Texto de la tarea).\n"
    "- No inventes datos ni uses conocimiento externo.\n"
    "- Usa formato Markdown (títulos, listas, **negritas**) cuando mejore la lectura.\n"
    "- Da directamente la respuesta final, sin describir tu razonamiento interno.\n"
    "- Si el usuario te pide explícitamente abrir un documento, PDF o archivo por su nombre y ese archivo existe en el listado de documentos disponibles, responde confirmando la apertura y añade al final de tu respuesta EXACTAMENTE la etiqueta '[OPEN_DOC: nombre_del_archivo.pdf]'. Ejemplo: [OPEN_DOC: informe.pdf]"
)


def _build_context(results: list[dict]) -> str:
    blocks = []
    for i, r in enumerate(results, start=1):
        blocks.append(f"[Fuente {i}: {r['source']}]\n{r['text']}")
    return "\n\n---\n\n".join(blocks)


def _unique_sources(results: list[dict]) -> list[str]:
    seen, sources = set(), []
    for r in results:
        if r["source"] not in seen:
            seen.add(r["source"])
            sources.append(r["source"])
    return sources


class RagEngine:
    def __init__(self, store, cfg: dict, registry=None):
        self.store = store
        self.cfg = cfg  # se lee en vivo; los cambios de Ajustes aplican al instante
        self.registry = registry
        self.history: list[dict] = []  # [{"role": ..., "content": ...}]

    def reset(self) -> None:
        """Empieza una conversación nueva (olvida los turnos anteriores)."""
        self.history.clear()

    def answer(self, question: str, on_token, doc_ids: list[str] | None = None,
               space_context: str | None = None) -> list[str]:
        """Responde con memoria de conversación. Devuelve las fuentes usadas."""
        top_k = int(self.cfg.get("top_k", 5))
        results = self.store.query(question, top_k=top_k, doc_ids=doc_ids)
        if not results and not space_context:
            if doc_ids is not None and not doc_ids:
                on_token(
                    "No hay ninguna fuente activa. Marca al menos un documento "
                    "en el panel de Fuentes (o cambia de categoría)."
                )
            else:
                on_token(
                    "No hay documentos en la base de conocimiento todavía. "
                    "Sube algún PDF o documento primero."
                )
            return []

        context = _build_context(results)
        
        full_context = ""
        if self.registry:
            all_docs = self.registry.all()
            if all_docs:
                doc_list_str = "Documentos disponibles en la base de conocimiento:\n" + "\n".join(f"- {d['filename']}" for d in all_docs)
                full_context += f"{doc_list_str}\n\n"
        if context:
            full_context += f"Contexto extraído de los fragmentos de documentos:\n\n{context}\n\n"
        if space_context:
            full_context += f"Contexto extraído de las notas, tareas y textos del espacio actual:\n\n{space_context}\n\n"

        user_msg = (
            f"{full_context}"
            f"Pregunta del usuario: {question}"
        )

        # Historial reciente (sin el contexto de turnos anteriores, para no
        # inflar el coste) + la pregunta actual con su contexto.
        max_msgs = max(0, int(self.cfg.get("history_turns", 6))) * 2
        messages = self.history[-max_msgs:] + [{"role": "user", "content": user_msg}]

        buffer: list[str] = []

        def collect(token: str):
            buffer.append(token)
            on_token(token)

        stream_chat(self.cfg, SYSTEM_PROMPT, messages, collect)

        # Guardamos el turno "limpio" (pregunta sin contexto) en el historial.
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": "".join(buffer)})
        return _unique_sources(results)

    def generate(self, prompt: str, on_token, doc_ids: list[str] | None = None,
                 system: str | None = None) -> list[str]:
        """Generación puntual (notas, tareas…) sin tocar el historial del chat."""
        top_k = int(self.cfg.get("top_k", 5))
        results = self.store.query(prompt, top_k=top_k, doc_ids=doc_ids)
        if not results:
            raise ValueError("No hay documentos disponibles para esta acción.")
        context = _build_context(results)
        user_msg = (
            f"Contexto extraído de los documentos:\n\n{context}\n\n"
            f"Instrucción: {prompt}"
        )
        stream_chat(self.cfg, system or SYSTEM_PROMPT,
                    [{"role": "user", "content": user_msg}], on_token)
        return _unique_sources(results)
