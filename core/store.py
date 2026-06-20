"""Base vectorial persistente (la 'memoria') y registro de documentos.

Usamos ChromaDB para guardar los embeddings en disco y un modelo local de
sentence-transformers para generarlos. Los embeddings se calculan una sola vez
por documento y quedan persistidos, de modo que la IA no tiene que volver a
leer el PDF cada vez que se le pregunta.
"""
import json
from datetime import datetime
from pathlib import Path

import chromadb

from . import config


class VectorStore:
    def __init__(self, persist_dir: Path, embedding_model_name: str):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._model_name = embedding_model_name
        self._model = None  # carga perezosa (la primera vez descarga el modelo)

        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

    # -- Embeddings ---------------------------------------------------------
    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def _embed(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        vectors = model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
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
    def query(self, text: str, top_k: int = 5) -> list[dict]:
        if self.collection.count() == 0:
            return []
        query_emb = self._embed([text])
        res = self.collection.query(
            query_embeddings=query_emb,
            n_results=top_k,
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
    """Lleva un índice en JSON de los documentos ya procesados."""

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

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._items, f, indent=2, ensure_ascii=False)

    def all(self) -> list[dict]:
        return list(self._items)

    def has(self, doc_id: str) -> bool:
        return any(it["id"] == doc_id for it in self._items)

    def add(self, doc_id: str, filename: str, path: str, chunks: int) -> dict:
        meta = {
            "id": doc_id,
            "filename": filename,
            "path": path,
            "chunks": chunks,
            "added_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._items.append(meta)
        self._save()
        return meta

    def remove(self, doc_id: str) -> None:
        self._items = [it for it in self._items if it["id"] != doc_id]
        self._save()


def build_store(cfg: dict) -> tuple[VectorStore, DocumentRegistry]:
    store = VectorStore(config.CHROMA_DIR, cfg["embedding_model"])
    registry = DocumentRegistry(config.REGISTRY_PATH)
    return store, registry
