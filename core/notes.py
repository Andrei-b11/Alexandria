"""Notas y tareas (estilo Notion), persistidas en storage/notes.json.

Las notas y tareas pueden crearse a mano o generarse con la IA a partir de los
documentos de la base de conocimiento.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Workspace:
    """CRUD sencillo de notas y tareas sobre un único archivo JSON."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data = {"notes": [], "tasks": []}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._data["notes"] = list(data.get("notes", []))
                    self._data["tasks"] = list(data.get("tasks", []))
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    # ----------------------------------------------------------- Notas
    def notes(self) -> list[dict]:
        return list(self._data["notes"])

    def get_note(self, note_id: str) -> dict | None:
        return next((n for n in self._data["notes"] if n["id"] == note_id), None)

    def add_note(self, title: str, content: str = "", source: str = "manual") -> dict:
        note = {
            "id": uuid.uuid4().hex[:12],
            "title": title.strip() or "Sin título",
            "content": content,
            "source": source,  # "manual" | "ia" | "chat"
            "created_at": _now(),
            "updated_at": _now(),
        }
        self._data["notes"].insert(0, note)
        self._save()
        return note

    def update_note(self, note_id: str, title: str, content: str) -> None:
        note = self.get_note(note_id)
        if note:
            note["title"] = title.strip() or "Sin título"
            note["content"] = content
            note["updated_at"] = _now()
            self._save()

    def delete_note(self, note_id: str) -> None:
        self._data["notes"] = [n for n in self._data["notes"] if n["id"] != note_id]
        self._save()

    # ----------------------------------------------------------- Tareas
    def tasks(self) -> list[dict]:
        return list(self._data["tasks"])

    def add_task(self, text: str, source: str = "manual") -> dict:
        task = {
            "id": uuid.uuid4().hex[:12],
            "text": text.strip(),
            "done": False,
            "source": source,
            "created_at": _now(),
        }
        self._data["tasks"].append(task)
        self._save()
        return task

    def update_task_text(self, task_id: str, text: str) -> None:
        for t in self._data["tasks"]:
            if t["id"] == task_id:
                t["text"] = text.strip() or t["text"]
                self._save()
                return

    def set_task_done(self, task_id: str, done: bool) -> None:
        for t in self._data["tasks"]:
            if t["id"] == task_id:
                t["done"] = bool(done)
                self._save()
                return

    def delete_task(self, task_id: str) -> None:
        self._data["tasks"] = [t for t in self._data["tasks"] if t["id"] != task_id]
        self._save()

    def reorder_tasks(self, ordered_ids: list[str]) -> None:
        """Reordena las tareas según la lista de ids (arrastrar y soltar)."""
        by_id = {t["id"]: t for t in self._data["tasks"]}
        reordered = [by_id[i] for i in ordered_ids if i in by_id]
        rest = [t for t in self._data["tasks"] if t["id"] not in set(ordered_ids)]
        self._data["tasks"] = reordered + rest
        self._save()

    def clear_done_tasks(self) -> int:
        before = len(self._data["tasks"])
        self._data["tasks"] = [t for t in self._data["tasks"] if not t.get("done")]
        self._save()
        return before - len(self._data["tasks"])
