"""Hilos en segundo plano para no bloquear la interfaz."""
import hashlib
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from core.chunker import chunk_text
from core.extractor import extract_text
from core.ollama_manager import ensure_server, pull_model


def _file_hash(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()[:32]


class IngestWorker(QThread):
    """Procesa documentos: extrae texto, trocea, genera embeddings y persiste."""

    progress = pyqtSignal(str)
    file_done = pyqtSignal(dict)
    file_error = pyqtSignal(str, str)  # nombre, mensaje
    finished_all = pyqtSignal()

    def __init__(self, paths, store, registry):
        super().__init__()
        self.paths = paths
        self.store = store
        self.registry = registry

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
                meta = self.registry.add(doc_id, name, str(path), len(chunks))
                self.file_done.emit(meta)
            except Exception as e:  # noqa: BLE001
                self.file_error.emit(name, str(e))
        self.finished_all.emit()


class QueryWorker(QThread):
    """Recupera contexto y transmite la respuesta de la IA token a token."""

    token = pyqtSignal(str)
    sources_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    finished_answer = pyqtSignal()

    def __init__(self, rag_engine, question):
        super().__init__()
        self.rag = rag_engine
        self.question = question

    def run(self):
        try:
            sources = self.rag.answer(self.question, lambda t: self.token.emit(t))
            self.sources_ready.emit(sources)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
        finally:
            self.finished_answer.emit()


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


class EnsureServerWorker(QThread):
    """Arranca el servidor de Ollama (embebido o del sistema) en segundo plano."""

    result = pyqtSignal(bool)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        self.result.emit(ensure_server(self.url))
