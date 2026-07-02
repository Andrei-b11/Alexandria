"""Espacios: lienzos 2D (estilo Obsidian Canvas) persistidos en spaces.json.

Un espacio contiene tarjetas posicionadas libremente. Cada tarjeta referencia
una nota o tarea del Workspace, un documento del registro, o lleva su propio
texto (tarjeta de texto). Quitar una tarjeta del espacio NO borra la nota,
tarea o documento subyacente.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

# Tipos de tarjeta: "note" | "doc" | "task" | "text"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SpacesStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._spaces: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._spaces = list(data.get("spaces", []))
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"spaces": self._spaces}, f, indent=2, ensure_ascii=False)

    # --------------------------------------------------------- espacios
    def spaces(self) -> list[dict]:
        return list(self._spaces)

    def get(self, space_id: str) -> dict | None:
        return next((s for s in self._spaces if s["id"] == space_id), None)

    def add_space(self, name: str) -> dict:
        space = {
            "id": uuid.uuid4().hex[:12],
            "name": name.strip() or "Espacio",
            "created_at": _now(),
            "items": [],
        }
        self._spaces.append(space)
        self._save()
        return space

    def rename_space(self, space_id: str, name: str) -> None:
        space = self.get(space_id)
        if space:
            space["name"] = name.strip() or space["name"]
            self._save()

    def delete_space(self, space_id: str) -> None:
        self._spaces = [s for s in self._spaces if s["id"] != space_id]
        self._save()

    def ensure_default(self) -> dict:
        """Garantiza que exista al menos un espacio y lo devuelve."""
        if not self._spaces:
            return self.add_space("Mi espacio")
        return self._spaces[0]

    # --------------------------------------------------------- tarjetas
    def add_item(self, space_id: str, kind: str, ref: str | None = None,
                 text: str = "", x: float = 0, y: float = 0) -> dict | None:
        space = self.get(space_id)
        if not space:
            return None
        item = {
            "id": uuid.uuid4().hex[:12],
            "type": kind,
            "ref": ref,
            "text": text,
            "x": round(x, 1),
            "y": round(y, 1),
        }
        space["items"].append(item)
        self._save()
        return item

    def get_item(self, space_id: str, item_id: str) -> dict | None:
        space = self.get(space_id)
        if not space:
            return None
        return next((it for it in space["items"] if it["id"] == item_id), None)

    def set_positions(self, space_id: str, positions: dict[str, tuple]) -> None:
        """Guarda las posiciones {item_id: (x, y)} de golpe."""
        space = self.get(space_id)
        if not space:
            return
        for it in space["items"]:
            if it["id"] in positions:
                x, y = positions[it["id"]]
                it["x"], it["y"] = round(x, 1), round(y, 1)
        self._save()

    def update_item_text(self, space_id: str, item_id: str, text: str) -> None:
        item = self.get_item(space_id, item_id)
        if item:
            item["text"] = text
            self._save()

    def remove_item(self, space_id: str, item_id: str) -> None:
        space = self.get(space_id)
        if space:
            space["items"] = [it for it in space["items"] if it["id"] != item_id]
            self._save()

    def remove_refs(self, ref: str) -> None:
        """Elimina de todos los espacios las tarjetas que referencian `ref`
        (al borrar definitivamente una nota, tarea o documento)."""
        changed = False
        for space in self._spaces:
            before = len(space["items"])
            space["items"] = [it for it in space["items"] if it.get("ref") != ref]
            changed = changed or len(space["items"]) != before
        if changed:
            self._save()

    def has_ref(self, space_id: str, ref: str) -> bool:
        space = self.get(space_id)
        if not space:
            return False
        return any(it.get("ref") == ref for it in space["items"])
