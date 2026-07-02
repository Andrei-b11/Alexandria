"""Base vectorial persistente (la 'memoria') y registro de documentos.

Usamos ChromaDB para guardar los embeddings en disco y un modelo local de
sentence-transformers para generarlos. Los embeddings se calculan una sola vez
por documento y quedan persistidos, de modo que la IA no tiene que volver a
leer el PDF cada vez que se le pregunta. La memoria es la misma para todos los
motores de IA (Claude, Gemini, Groq, OpenAI u Ollama).
"""
import json
import threading
from datetime import datetime
from pathlib import Path

import chromadb

from . import config

DEFAULT_CATEGORY = "General"


class VectorStore:
    def __init__(self, persist_dir: Path, embedding_model_name: str):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._model_name = embedding_model_name
        self._model = None  # carga perezosa (la primera vez descarga el modelo)
        self._model_lock = threading.Lock()  # evita cargas dobles concurrentes

        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

    # -- Embeddings ---------------------------------------------------------
    def _ensure_model(self):
        with self._model_lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                try:
                    # Primero sin red: usa la copia local ya descargada
                    # (más rápido y sin avisos de HF Hub).
                    self._model = SentenceTransformer(
                        self._model_name, local_files_only=True
                    )
                except Exception:  # noqa: BLE001 — primera vez: descargar
                    self._model = SentenceTransformer(self._model_name)
        return self._model

    def warmup(self) -> None:
        """Carga el modelo de embeddings (llamar en segundo plano al arrancar)."""
        self._ensure_model()

    def _embed(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        vectors = model.encode(
            texts,
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    # -- Escritura ----------------------------------------------------------
    def add_document(self, doc_id: str, filename: str, chunks: list[str]) -> None:
        if not chunks:
            return
        embeddings = self._embed(chunks)
        ids = [f"{doc_id}:{i}" for i in range(len(chunks))]
        metadatas = [
            {"doc_id": doc_id, "source": filename, "chunk_index": i}
            for i in range(len(chunks))
        ]
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

    def delete_document(self, doc_id: str) -> None:
        self.collection.delete(where={"doc_id": doc_id})

    # -- Lectura ------------------------------------------------------------
    def query(self, text: str, top_k: int = 5, doc_ids: list[str] | None = None) -> list[dict]:
        """Busca los fragmentos más relevantes.

        `doc_ids` limita la búsqueda a esos documentos (categoría o selección
        del usuario). None = todos los documentos.
        """
        if self.collection.count() == 0:
            return []
        if doc_ids is not None and not doc_ids:
            return []  # el usuario no tiene ninguna fuente activa
        where = None
        if doc_ids is not None:
            if len(doc_ids) == 1:
                where = {"doc_id": doc_ids[0]}
            else:
                where = {"doc_id": {"$in": doc_ids}}
        query_emb = self._embed([text])
        res = self.collection.query(
            query_embeddings=query_emb,
            n_results=top_k,
            where=where,
        )
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        results = []
        for doc, meta, dist in zip(docs, metas, dists):
            results.append(
                {
                    "text": doc,
                    "source": (meta or {}).get("source", "desconocido"),
                    "distance": dist,
                }
            )
        return results

    def is_empty(self) -> bool:
        return self.collection.count() == 0


class DocumentRegistry:
    """Índice en JSON de los documentos ya procesados, con categorías."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._items: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._items = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._items = []
        # Migración: documentos antiguos sin categoría ni estado.
        changed = False
        for it in self._items:
            if "category" not in it:
                it["category"] = DEFAULT_CATEGORY
                changed = True
            if "enabled" not in it:
                it["enabled"] = True
                changed = True
        if changed:
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._items, f, indent=2, ensure_ascii=False)

    def all(self) -> list[dict]:
        return list(self._items)

    def has(self, doc_id: str) -> bool:
        return any(it["id"] == doc_id for it in self._items)

    def get(self, doc_id: str) -> dict | None:
        return next((it for it in self._items if it["id"] == doc_id), None)

    def add(self, doc_id: str, filename: str, path: str, chunks: int,
            category: str = DEFAULT_CATEGORY) -> dict:
        meta = {
            "id": doc_id,
            "filename": filename,
            "path": path,
            "chunks": chunks,
            "category": category or DEFAULT_CATEGORY,
            "enabled": True,
            "added_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._items.append(meta)
        self._save()
        return meta

    def remove(self, doc_id: str) -> None:
        self._items = [it for it in self._items if it["id"] != doc_id]
        self._save()

    def set_category(self, doc_id: str, category: str) -> None:
        meta = self.get(doc_id)
        if meta:
            meta["category"] = category or DEFAULT_CATEGORY
            self._save()

    def set_enabled(self, doc_id: str, enabled: bool) -> None:
        meta = self.get(doc_id)
        if meta:
            meta["enabled"] = bool(enabled)
            self._save()

    def reorder(self, ordered_ids: list[str]) -> None:
        """Reordena los documentos según la lista de ids (arrastrar y soltar)."""
        by_id = {it["id"]: it for it in self._items}
        reordered = [by_id[i] for i in ordered_ids if i in by_id]
        rest = [it for it in self._items if it["id"] not in set(ordered_ids)]
        self._items = reordered + rest
        self._save()

    def categories(self) -> list[str]:
        cats = {it.get("category", DEFAULT_CATEGORY) for it in self._items}
        cats.add(DEFAULT_CATEGORY)
        return sorted(cats, key=str.casefold)


def build_store(cfg: dict) -> tuple[VectorStore, DocumentRegistry]:
    store = VectorStore(config.CHROMA_DIR, cfg["embedding_model"])
    registry = DocumentRegistry(config.REGISTRY_PATH)
    return store, registry
