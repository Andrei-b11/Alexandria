"""Hilos en segundo plano para no bloquear la interfaz."""
import hashlib
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.chunker import chunk_text
from core.extractor import extract_text
from core.ollama_manager import ensure_server, pull_model


def _file_hash(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()[:32]


class WarmupWorker(QObject):
    """Precarga el modelo de embeddings al arrancar para que la primera
    búsqueda o subida sea instantánea.

    Usa un hilo daemon (no QThread): si se cierra la app a mitad de carga,
    el hilo muere con el proceso sin avisos de Qt.
    """

    ready = pyqtSignal()

    def __init__(self, store):
        super().__init__()
        self.store = store

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="warmup").start()

    def _run(self):
        try:
            self.store.warmup()
        except Exception:  # noqa: BLE001 — sin modelo aún; se cargará al usarse
            pass
        self.ready.emit()


class IngestWorker(QThread):
    """Procesa documentos: extrae texto, trocea, genera embeddings y persiste."""

    progress = pyqtSignal(str)
    file_done = pyqtSignal(dict)
    file_error = pyqtSignal(str, str)  # nombre, mensaje
    finished_all = pyqtSignal()

    def __init__(self, paths, store, registry, category: str = "General"):
        super().__init__()
        self.paths = paths
        self.store = store
        self.registry = registry
        self.category = category

    def run(self):
        for path in self.paths:
            name = Path(path).name
            try:
                self.progress.emit(f"Leyendo «{name}»…")
                doc_id = _file_hash(path)
                if self.registry.has(doc_id):
                    self.file_error.emit(name, "Ya está en la base de conocimiento.")
                    continue

                text = extract_text(path)
                chunks = chunk_text(text)
                if not chunks:
                    self.file_error.emit(name, "No se extrajo texto del documento.")
                    continue

                self.progress.emit(
                    f"Generando memoria de «{name}» ({len(chunks)} fragmentos)…"
                )
                self.store.add_document(doc_id, name, chunks)
                meta = self.registry.add(
                    doc_id, name, str(path), len(chunks), category=self.category
                )
                self.file_done.emit(meta)
            except Exception as e:  # noqa: BLE001
                self.file_error.emit(name, str(e))
        self.finished_all.emit()


class CancelledError(Exception):
    """El usuario detuvo la generación."""


class QueryWorker(QThread):
    """Recupera contexto y transmite la respuesta de la IA token a token."""

    token = pyqtSignal(str)
    sources_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    finished_answer = pyqtSignal()
    cancelled = False  # poner a True para detener la generación en curso

    def __init__(self, rag_engine, question, doc_ids=None, space_context=None,
                 direct=False):
        super().__init__()
        self.rag = rag_engine
        self.question = question
        self.doc_ids = doc_ids
        self.space_context = space_context
        self.direct = direct  # modo chat directo: sin RAG ni agente

    def _emit_token(self, t: str):
        if self.cancelled:
            raise CancelledError()
        self.token.emit(t)

    def run(self):
        try:
            if self.direct:
                sources = self.rag.chat_direct(self.question, self._emit_token)
            else:
                sources = self.rag.answer(
                    self.question, self._emit_token,
                    doc_ids=self.doc_ids, space_context=self.space_context,
                )
            self.sources_ready.emit(sources)
        except CancelledError:
            self.sources_ready.emit([])  # respuesta parcial, sin fuentes
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
        finally:
            self.finished_answer.emit()


class GenerateWorker(QThread):
    """Generación puntual con IA (notas, tareas…): devuelve el texto completo."""

    done = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, rag_engine, prompt, doc_ids=None, system=None):
        super().__init__()
        self.rag = rag_engine
        self.prompt = prompt
        self.doc_ids = doc_ids
        self.system = system

    def run(self):
        buffer: list[str] = []
        try:
            self.rag.generate(
                self.prompt, buffer.append, doc_ids=self.doc_ids, system=self.system
            )
            self.done.emit("".join(buffer))
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))


class PullWorker(QThread):
    """Descarga un modelo de Ollama mostrando el progreso."""

    progress = pyqtSignal(str, int)  # estado, porcentaje (-1 si desconocido)
    done = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, url, model):
        super().__init__()
        self.url = url
        self.model = model

    def run(self):
        try:
            pull_model(self.url, self.model, lambda s, p: self.progress.emit(s, p))
            self.done.emit()
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))


class EnsureServerWorker(QObject):
    """Arranca el servidor de Ollama (embebido o del sistema) en segundo plano.

    Hilo daemon: su espera (hasta 25 s) no retrasa el cierre de la app.
    """

    result = pyqtSignal(bool)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="ollama-server").start()

    def _run(self):
        self.result.emit(ensure_server(self.url))
