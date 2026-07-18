"""Motor RAG: recupera fragmentos relevantes y genera la respuesta.

Mantiene memoria de la conversación (los últimos N turnos) para que se puedan
hacer preguntas de seguimiento, y permite limitar la búsqueda a un subconjunto
de documentos (categoría o fuentes marcadas por el usuario).
"""
from .llm import stream_chat
from .websearch import search_web

# Distancia coseno a partir de la cual los fragmentos recuperados se
# consideran irrelevantes y se recurre a la búsqueda web.
WEAK_MATCH_DISTANCE = 0.75

SYSTEM_PROMPT = (
    "Eres el asistente de Alexandria: respondes preguntas y actúas como agente dentro de la app. "
    "El contexto puede incluir fragmentos de documentos de la base de conocimiento, notas/tareas/"
    "textos de los espacios de trabajo y, a veces, resultados de búsqueda en internet.\n"
    "Reglas:\n"
    "- Responde siempre en español, de forma clara, directa y concisa.\n"
    "- Tienes memoria de la conversación actual: usa los mensajes anteriores para resolver "
    "referencias y preguntas de seguimiento («resúmelo», «¿y el segundo punto?», «hazlo más corto»…).\n"
    "- Prioridad de la información: 1º los documentos y el espacio; 2º los resultados de internet "
    "incluidos en el contexto, citándolos como (Web: título); 3º tu propio conocimiento general.\n"
    "- Si una parte de tu respuesta procede de tu conocimiento general y no del contexto, "
    "empiézala con «💡 Nota (conocimiento general):» para dejarlo claro.\n"
    "- Cuando uses documentos indica la procedencia, p. ej. (Fuente: informe.pdf) o (Nota: Título).\n"
    "- Usa formato Markdown (títulos, listas, **negritas**) cuando mejore la lectura.\n"
    "- Da directamente la respuesta final, sin describir tu razonamiento interno.\n"
    "\n"
    "Herramientas de agente — puedes realizar acciones reales en la app añadiendo etiquetas "
    "AL FINAL de tu respuesta, cada una en su propia línea:\n"
    "- [ADD_TASK: texto de la tarea] → crea una tarea en el espacio actual. Una etiqueta por tarea.\n"
    "- [ADD_NOTE: Título :: contenido en Markdown] → crea una nota en el espacio actual.\n"
    "- [OPEN_DOC: nombre_del_archivo.pdf] → abre ese documento con la aplicación predeterminada del sistema. "
    "Copia el nombre EXACTO tal y como aparece en la lista de documentos disponibles. "
    "Si el usuario pide abrir un PDF/documento por su nombre, usa SIEMPRE esta etiqueta.\n"
    "Úsalas únicamente cuando el usuario pida crear, apuntar, planificar o abrir algo "
    "(p. ej. «créame una tarea…», «apunta una nota con…», «hazme un plan y guárdalo»). "
    "Confirma en el texto de tu respuesta qué acción has realizado. "
    "Nunca muestres estas etiquetas como ejemplo ni hables de ellas al usuario."
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


DIRECT_SYSTEM = (
    "Eres un asistente de IA útil y directo. Responde siempre en español, "
    "usando formato Markdown cuando mejore la lectura. Tienes memoria de la "
    "conversación actual."
)


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

        # Respaldo: si los documentos no aportan nada relevante, buscamos en
        # internet (si está activado) y dejamos que el modelo use además su
        # conocimiento general (el prompt de sistema se lo permite).
        web_results: list[dict] = []
        best = min((r["distance"] for r in results), default=None)
        weak = not results or (best is not None and best > WEAK_MATCH_DISTANCE)
        if weak and self.cfg.get("web_search", True):
            web_results = search_web(question)

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
        if web_results:
            web_blocks = "\n\n".join(
                f"[Web {i}: {r['title']}]\nURL: {r['url']}\n{r['snippet']}"
                for i, r in enumerate(web_results, start=1)
            )
            full_context += (
                "Resultados de búsqueda en internet (la pregunta no encontró "
                f"nada relevante en los documentos):\n\n{web_blocks}\n\n"
            )
        if not context and not space_context and not web_results:
            full_context += (
                "(No se ha encontrado contexto relevante en los documentos para "
                "esta pregunta; responde con la conversación y tu conocimiento general.)\n\n"
            )

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
        sources = _unique_sources(results)
        sources += [f"🌐 {r['title']}" for r in web_results if r.get("title")]
        return sources

    def chat_direct(self, question: str, on_token) -> list[str]:
        """Modo directo: chatea con el modelo a pelo (sin RAG, sin agente),
        como si usaras Ollama o LM Studio directamente. Comparte el historial
        de la conversación con el modo app."""
        max_msgs = max(0, int(self.cfg.get("history_turns", 6))) * 2
        messages = self.history[-max_msgs:] + [{"role": "user", "content": question}]

        buffer: list[str] = []

        def collect(token: str):
            buffer.append(token)
            on_token(token)

        stream_chat(self.cfg, DIRECT_SYSTEM, messages, collect)
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": "".join(buffer)})
        return []

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
