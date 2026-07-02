"""Vista de Espacios: lienzo 2D + barra de herramientas.

Cada espacio asocia libremente documentos, notas, tareas y textos como
tarjetas que se arrastran por el lienzo (estilo Obsidian Canvas).
"""
from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.canvas import SpaceCanvas
from ui.icons import icon

ICON_MUTED = "#9aa0ab"


class NoteEditDialog(QDialog):
    """Editor de una nota (título + contenido Markdown)."""

    def __init__(self, title: str, content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar nota")
        self.setMinimumSize(520, 420)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("Título…")
        lay.addWidget(self.title_edit)
        self.body_edit = QPlainTextEdit(content)
        self.body_edit.setPlaceholderText("Contenido… (admite Markdown)")
        lay.addWidget(self.body_edit, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def values(self) -> tuple[str, str]:
        return self.title_edit.text().strip(), self.body_edit.toPlainText()


class SpacesView(QWidget):
    """Barra de herramientas + lienzo del espacio activo."""

    def __init__(self, spaces, workspace, registry, status_cb, parent=None):
        super().__init__(parent)
        self.spaces = spaces
        self.workspace = workspace
        self.registry = registry
        self.status = status_cb
        self._space_id: str | None = None

        self.canvas = SpaceCanvas()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 8, 2, 10)
        lay.setSpacing(8)
        lay.addLayout(self._build_toolbar())

        self.canvas.positions_changed.connect(self._save_positions)
        self.canvas.card_double_clicked.connect(self._open_item)
        self.canvas.card_context.connect(self._card_menu)
        self.canvas.card_check_toggled.connect(self._toggle_task)
        self.canvas.canvas_context.connect(self._canvas_menu)
        self.canvas.delete_requested.connect(self._remove_items)
        lay.addWidget(self.canvas, 1)

        self.hint = QLabel(
            "Arrastra las tarjetas para organizarlas · rueda: zoom · "
            "arrastra el fondo: moverte · doble clic: abrir · Supr: quitar del espacio"
        )
        self.hint.setObjectName("muted")
        lay.addWidget(self.hint)

        self.reload_spaces()

    # ------------------------------------------------------------ toolbar
    def _tool_btn(self, icon_name: str, tooltip: str, slot, text: str = "") -> QPushButton:
        btn = QPushButton(("  " + text) if text else "")
        btn.setIcon(icon(icon_name, ICON_MUTED, 15))
        btn.setToolTip(tooltip)
        if not text:
            btn.setFixedSize(36, 34)
            btn.setObjectName("iconBtn")
        btn.clicked.connect(slot)
        return btn

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self.space_combo = QComboBox()
        self.space_combo.setMinimumWidth(180)
        self.space_combo.currentIndexChanged.connect(self._on_space_changed)
        bar.addWidget(self.space_combo)

        bar.addWidget(self._tool_btn("plus", "Crear un espacio nuevo", self._new_space))
        bar.addWidget(self._tool_btn("pen", "Renombrar este espacio", self._rename_space))
        bar.addWidget(self._tool_btn("trash", "Eliminar este espacio", self._delete_space))

        sep = QLabel("·")
        sep.setObjectName("muted")
        bar.addWidget(sep)

        note_btn = self._tool_btn("pen", "Crear una nota en este espacio",
                                  self._new_note, "Nota")
        text_btn = self._tool_btn("align-left", "Añadir una tarjeta de texto libre",
                                  self._new_text, "Texto")
        task_btn = self._tool_btn("list-checks", "Añadir una tarea",
                                  self._new_task, "Tarea")
        doc_btn = self._tool_btn("file-text", "Asociar un documento de la memoria",
                                 self._add_doc, "Documento")
        for b in (note_btn, text_btn, task_btn, doc_btn):
            bar.addWidget(b)

        bar.addStretch(1)
        bar.addWidget(self._tool_btn("refresh", "Centrar la vista en las tarjetas",
                                     self.canvas.center_content))
        return bar

    # ------------------------------------------------------------ espacios
    def current_space_id(self) -> str | None:
        return self._space_id

    def reload_spaces(self, select_id: str | None = None):
        self.spaces.ensure_default()
        target = select_id or self._space_id
        self.space_combo.blockSignals(True)
        self.space_combo.clear()
        for sp in self.spaces.spaces():
            self.space_combo.addItem(icon("folder-open", ICON_MUTED, 14), sp["name"], sp["id"])
        idx = self.space_combo.findData(target) if target else 0
        self.space_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.space_combo.blockSignals(False)
        self._space_id = self.space_combo.currentData()
        self.reload_canvas()

    def _on_space_changed(self):
        self._space_id = self.space_combo.currentData()
        self.reload_canvas()
        self.canvas.center_content()

    def _new_space(self):
        name, ok = QInputDialog.getText(self, "Nuevo espacio", "Nombre del espacio:")
        name = (name or "").strip()
        if not ok or not name:
            return
        sp = self.spaces.add_space(name)
        self.reload_spaces(select_id=sp["id"])
        self.status(f"Espacio «{name}» creado")

    def _rename_space(self):
        sp = self.spaces.get(self._space_id) if self._space_id else None
        if not sp:
            return
        name, ok = QInputDialog.getText(
            self, "Renombrar espacio", "Nuevo nombre:", text=sp["name"]
        )
        name = (name or "").strip()
        if not ok or not name:
            return
        self.spaces.rename_space(sp["id"], name)
        self.reload_spaces(select_id=sp["id"])

    def _delete_space(self):
        sp = self.spaces.get(self._space_id) if self._space_id else None
        if not sp:
            return
        confirm = QMessageBox.question(
            self, "Eliminar espacio",
            f"¿Eliminar el espacio «{sp['name']}»?\n"
            "Las notas, tareas y documentos NO se borran; solo este lienzo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.spaces.delete_space(sp["id"])
        self._space_id = None
        self.reload_spaces()

    # -------------------------------------------------------------- lienzo
    def _resolve(self, item: dict) -> tuple[str, str, bool | None] | None:
        """Devuelve (título, cuerpo, checked) de una tarjeta, o None si su
        referencia ya no existe."""
        kind = item["type"]
        if kind == "text":
            text = item.get("text", "")
            first, _, rest = text.partition("\n")
            return (first.strip() or "Texto", rest.strip(), None)
        if kind == "note":
            note = self.workspace.get_note(item.get("ref"))
            if not note:
                return None
            return (note["title"], note.get("content", ""), None)
        if kind == "doc":
            meta = self.registry.get(item.get("ref"))
            if not meta:
                return None
            body = (f"Categoría: {meta.get('category', '')}\n"
                    f"{meta.get('chunks', 0)} fragmentos en memoria")
            return (meta["filename"], body, None)
        if kind == "task":
            task = next((t for t in self.workspace.tasks()
                         if t["id"] == item.get("ref")), None)
            if not task:
                return None
            return (task["text"], "", bool(task.get("done")))
        return None

    def reload_canvas(self):
        self.canvas.clear_cards()
        sp = self.spaces.get(self._space_id) if self._space_id else None
        if not sp:
            return
        stale = []
        for item in sp["items"]:
            resolved = self._resolve(item)
            if resolved is None:
                stale.append(item["id"])
                continue
            title, body, checked = resolved
            self.canvas.add_card(item["id"], item["type"], title, body,
                                 item.get("x", 0), item.get("y", 0), checked)
        for item_id in stale:  # limpia tarjetas cuya referencia se borró
            self.spaces.remove_item(sp["id"], item_id)

    def _save_positions(self):
        if self._space_id:
            self.spaces.set_positions(self._space_id, self.canvas.positions())

    def _add_card_here(self, kind: str, ref: str | None = None, text: str = "",
                       pos=None):
        p = pos or self.canvas.free_position()
        self.spaces.add_item(self._space_id, kind, ref=ref, text=text,
                             x=p.x(), y=p.y())
        self.reload_canvas()

    # -------------------------------------------------- crear tarjetas
    def _new_note(self, pos=None):
        dlg = NoteEditDialog("", "", self)
        dlg.setWindowTitle("Nueva nota")
        if not dlg.exec():
            return
        title, content = dlg.values()
        if not title and not content.strip():
            return
        note = self.workspace.add_note(title or "Sin título", content)
        self._add_card_here("note", ref=note["id"], pos=pos)
        self.status("Nota creada en el espacio")

    def _new_text(self, pos=None):
        text, ok = QInputDialog.getMultiLineText(
            self, "Tarjeta de texto", "Texto (la primera línea será el título):"
        )
        if not ok or not text.strip():
            return
        self._add_card_here("text", text=text.strip(), pos=pos)

    def _new_task(self, pos=None):
        text, ok = QInputDialog.getText(self, "Nueva tarea", "Descripción de la tarea:")
        text = (text or "").strip()
        if not ok or not text:
            return
        task = self.workspace.add_task(text)
        self._add_card_here("task", ref=task["id"], pos=pos)

    def _add_doc(self, pos=None):
        docs = self.registry.all()
        if not docs:
            self.status("No hay documentos en la memoria todavía")
            return
        labels = [f"{d['filename']}  ·  {d.get('category', '')}" for d in docs]
        choice, ok = QInputDialog.getItem(
            self, "Asociar documento", "Documento de la memoria:", labels, 0,
            editable=False,
        )
        if not ok:
            return
        meta = docs[labels.index(choice)]
        if self.spaces.has_ref(self._space_id, meta["id"]):
            self.status("Ese documento ya está en este espacio")
            return
        self._add_card_here("doc", ref=meta["id"], pos=pos)

    def add_note_card(self, note_id: str):
        """Añade al espacio actual una nota ya creada (IA / chat)."""
        if self._space_id and not self.spaces.has_ref(self._space_id, note_id):
            self._add_card_here("note", ref=note_id)

    def add_task_card(self, task_id: str):
        if self._space_id and not self.spaces.has_ref(self._space_id, task_id):
            self._add_card_here("task", ref=task_id)

    # ------------------------------------------------------ interacciones
    def _open_item(self, item_id: str):
        item = self.spaces.get_item(self._space_id, item_id)
        if not item:
            return
        kind = item["type"]
        if kind == "note":
            note = self.workspace.get_note(item.get("ref"))
            if not note:
                return
            dlg = NoteEditDialog(note["title"], note.get("content", ""), self)
            if dlg.exec():
                title, content = dlg.values()
                self.workspace.update_note(note["id"], title, content)
                self.reload_canvas()
        elif kind == "text":
            text, ok = QInputDialog.getMultiLineText(
                self, "Editar texto", "Texto:", item.get("text", "")
            )
            if ok:
                self.spaces.update_item_text(self._space_id, item_id, text.strip())
                self.reload_canvas()
        elif kind == "doc":
            meta = self.registry.get(item.get("ref"))
            if meta and meta.get("path"):
                QDesktopServices.openUrl(QUrl.fromLocalFile(meta["path"]))
        elif kind == "task":
            task = next((t for t in self.workspace.tasks()
                         if t["id"] == item.get("ref")), None)
            if not task:
                return
            text, ok = QInputDialog.getText(
                self, "Editar tarea", "Descripción:", text=task["text"]
            )
            text = (text or "").strip()
            if ok and text:
                self.workspace.update_task_text(task["id"], text)
                self.reload_canvas()

    def _toggle_task(self, item_id: str, checked: bool):
        item = self.spaces.get_item(self._space_id, item_id)
        if item and item["type"] == "task":
            self.workspace.set_task_done(item.get("ref"), checked)
            self.reload_canvas()

    def _remove_items(self, ids: list[str]):
        for item_id in ids:
            self.spaces.remove_item(self._space_id, item_id)
        self.reload_canvas()
        self.status(f"{len(ids)} tarjeta(s) quitada(s) del espacio")

    def _card_menu(self, item_id: str, screen_pos):
        item = self.spaces.get_item(self._space_id, item_id)
        if not item:
            return
        kind = item["type"]
        menu = QMenu(self)
        open_labels = {
            "note": "Editar nota", "text": "Editar texto",
            "doc": "Abrir documento", "task": "Editar tarea",
        }
        open_action = menu.addAction(icon("pen", ICON_MUTED, 14), open_labels[kind])
        remove_action = menu.addAction(
            icon("x", ICON_MUTED, 14), "Quitar del espacio"
        )
        delete_action = None
        if kind in ("note", "task"):
            what = "nota" if kind == "note" else "tarea"
            delete_action = menu.addAction(
                icon("trash", ICON_MUTED, 14), f"Eliminar {what} definitivamente"
            )
        chosen = menu.exec(screen_pos)
        if chosen is open_action:
            self._open_item(item_id)
        elif chosen is remove_action:
            self._remove_items([item_id])
        elif delete_action is not None and chosen is delete_action:
            ref = item.get("ref")
            if kind == "note":
                self.workspace.delete_note(ref)
            else:
                self.workspace.delete_task(ref)
            self.spaces.remove_refs(ref)
            self.reload_canvas()

    def _canvas_menu(self, scene_pos, screen_pos):
        menu = QMenu(self)
        note_action = menu.addAction(icon("pen", ICON_MUTED, 14), "Nueva nota aquí")
        text_action = menu.addAction(icon("align-left", ICON_MUTED, 14), "Texto aquí")
        task_action = menu.addAction(icon("list-checks", ICON_MUTED, 14), "Tarea aquí")
        doc_action = menu.addAction(icon("file-text", ICON_MUTED, 14), "Asociar documento…")
        chosen = menu.exec(screen_pos)
        if chosen is note_action:
            self._new_note(pos=scene_pos)
        elif chosen is text_action:
            self._new_text(pos=scene_pos)
        elif chosen is task_action:
            self._new_task(pos=scene_pos)
        elif chosen is doc_action:
            self._add_doc(pos=scene_pos)
