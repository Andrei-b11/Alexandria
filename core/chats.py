"""Historial de conversaciones del chat, persistidas en storage/chats.json.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path


class ChatHistoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._chats = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._chats = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._chats, f, indent=2, ensure_ascii=False)

    def all_chats(self) -> list[dict]:
        return list(self._chats)

    def get_chat(self, chat_id: str) -> dict | None:
        return next((c for c in self._chats if c["id"] == chat_id), None)

    def save_chat(self, chat_id: str, title: str, messages: list, rag_history: list) -> dict:
        chat = self.get_chat(chat_id)
        if chat:
            chat["title"] = title
            chat["messages"] = list(messages)
            chat["rag_history"] = list(rag_history)
            chat["updated_at"] = datetime.now().isoformat(timespec="seconds")
        else:
            chat = {
                "id": chat_id,
                "title": title,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "messages": list(messages),
                "rag_history": list(rag_history)
            }
            self._chats.insert(0, chat)
        self._save()
        return chat

    def delete_chat(self, chat_id: str) -> None:
        self._chats = [c for c in self._chats if c["id"] != chat_id]
        self._save()
