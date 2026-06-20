"""Ventana principal — layout de 3 columnas estilo NotebookLM."""
import html

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core import config
from core.ollama_manager import OllamaError, list_models
from core.rag import RagEngine
from core.store import build_store
from ui.settings_dialog import SettingsDialog
from ui.workers import EnsureServerWorker, IngestWorker, PullWorker, QueryWorker

DOC_FILTER = (
    "Documentos (*.pdf *.docx *.txt *.md *.markdown *.csv *.json *.log *.rst);;"
    "Todos los archivos (*.*)"
)

STUDIO_ACTIONS = [
    ("📄  Resumen general", "Haz un resumen general y estructurado de los documentos."),
    ("🔑  Ideas clave", "Enumera las ideas y datos clave de los documentos, en forma de lista."),
    ("❓  Preguntas sugeridas", "Sugiéreme 5 preguntas útiles que puedo hacer sobre estos documentos."),
    ("📋  Puntos de acción", "Lista las tareas o puntos de acción mencionados en los documentos."),
    ("🗓  Fechas y plazos", "Extrae las fechas, plazos y eventos importantes mencionados en los documentos."),
]


class ChatInput(QPlainTextEdit):
    """Enter envía, Shift+Enter hace salto de línea."""

    def __init__(self, on_submit):
        super().__init__()
        self.setObjectName("chatInput")
        self._on_submit = on_submit
        self.setPlaceholderText("Pregunta sobre tus documentos…")
        self.setFixedHeight(40)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self._on_submit()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Biblioteca de Alejandría")
        self.resize(1280, 800)

        self.cfg = config.load_config()
        self.store, self.registry = build_store(self.cfg)
        self.rag = RagEngine(self.store, self.cfg)
        self.ingest_worker = None
        self.query_worker = None
        self.server_worker = None
        self.pull_worker = None
        self._conversation_started = False

        self._build_ui()
        self._refresh_documents()
        self._update_backend_label()
        self._welcome()
        self._setup_ollama()

    # =================================================================== UI
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_topbar())

        body = QHBoxLayout()
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(12)
        body.addWidget(self._build_sources_panel())
        body.addWidget(self._build_chat_panel(), 1)
        body.addWidget(self._build_studio_panel())
        outer.addLayout(body, 1)

        self.statusBar().showMessage("Listo")

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topbar")
        bar.setFixedHeight(58)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 0, 18, 0)
        lay.setSpacing(10)

        logo = QLabel("📚")
        logo.setObjectName("logo")
        title = QLabel("Biblioteca de Alejandría")
        title.setObjectName("title")
        lay.addWidget(logo)
        lay.addWidget(title)
        lay.addStretch(1)

        self.chip = QLabel("")
        self.chip.setObjectName("chip")
        lay.addWidget(self.chip)

        settings_btn = QPushButton("⚙  Configuración")
        settings_btn.setObjectName("ghost")
        settings_btn.clicked.connect(self._open_settings)
        lay.addWidget(settings_btn)
        return bar

    def _panel(self, width: int | None = None) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("panel")
        if width:
            frame.setFixedWidth(width)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        return frame, lay

    def _build_sources_panel(self) -> QWidget:
        frame, lay = self._panel(width=280)

        header = QLabel("Fuentes")
        header.setObjectName("panelTitle")
        lay.addWidget(header)

        self.add_btn = QPushButton("➕  Añadir fuentes")
        self.add_btn.setObjectName("primary")
        self.add_btn.clicked.connect(self._upload)
        lay.addWidget(self.add_btn)

        self.doc_list = QListWidget()
        self.doc_list.setSpacing(0)
        lay.addWidget(self.doc_list, 1)

        self.delete_btn = QPushButton("🗑  Eliminar seleccionada")
        self.delete_btn.clicked.connect(self._delete_selected)
        lay.addWidget(self.delete_btn)

        self.sources_count = QLabel("")
        self.sources_count.setObjectName("muted")
        lay.addWidget(self.sources_count)
        return frame

    def _build_chat_panel(self) -> QWidget:
        frame, lay = self._panel()

        header = QLabel("Chat")
        header.setObjectName("panelTitle")
        lay.addWidget(header)

        # Banner de configuración (descarga del modelo de Ollama).
        self.setup_banner = QFrame()
        self.setup_banner.setObjectName("setupBanner")
        bl = QVBoxLayout(self.setup_banner)
        bl.setContentsMargins(14, 12, 14, 12)
        bl.setSpacing(8)
        self.setup_label = QLabel("")
        self.setup_label.setWordWrap(True)
        self.setup_progress = QProgressBar()
        self.setup_progress.setVisible(False)
        bl.addWidget(self.setup_label)
        bl.addWidget(self.setup_progress)
        self.setup_banner.setVisible(False)
        lay.addWidget(self.setup_banner)

        self.chat = QTextBrowser()
        self.chat.setObjectName("chatView")
        self.chat.setOpenExternalLinks(True)
        lay.addWidget(self.chat, 1)

        self.input_bar = QFrame()
        self.input_bar.setObjectName("inputBar")
        self.input_bar.setFixedHeight(56)
        ib = QHBoxLayout(self.input_bar)
        ib.setContentsMargins(16, 6, 8, 6)
        ib.setSpacing(8)
        self.input = ChatInput(self._send)
        ib.addWidget(self.input, 1)
        self.input_count = QLabel("")
        self.input_count.setObjectName("muted")
        ib.addWidget(self.input_count)
        self.send_btn = QPushButton("➤")
        self.send_btn.setObjectName("sendCircle")
        self.send_btn.setFixedSize(34, 34)
        self.send_btn.clicked.connect(self._send)
        ib.addWidget(self.send_btn)
        lay.addWidget(self.input_bar)
        return frame

    def _build_studio_panel(self) -> QWidget:
        frame, lay = self._panel(width=300)

        header = QLabel("Studio")
        header.setObjectName("panelTitle")
        lay.addWidget(header)

        hint = QLabel("Acciones rápidas sobre tus documentos:")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(8)
        for label, prompt in STUDIO_ACTIONS:
            card = QPushButton(label)
            card.setObjectName("studioCard")
            card.setMinimumHeight(48)
            card.clicked.connect(lambda _=False, p=prompt: self._send_preset(p))
            il.addWidget(card)
        il.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        self.studio_info = QLabel("")
        self.studio_info.setObjectName("muted")
        self.studio_info.setWordWrap(True)
        lay.addWidget(self.studio_info)
        return frame

    # ============================================================== helpers
    def _welcome(self):
        self.chat.clear()
        self._insert_html(
            '<div style="margin-top:40px; text-align:center;">'
            '<p style="font-size:34px; margin:0;">🗂️</p>'
            '<p style="font-size:20px; color:#f1f1f1; margin:10px 0 4px 0;">'
            "Tu base de conocimiento</p>"
            '<p style="color:#8e9398; margin:0;">Añade documentos en «Fuentes» y '
            "pregúntame sobre su contenido.<br>Respondo solo con lo que has subido.</p>"
            "</div>"
        )

    def _cursor_end(self) -> QTextCursor:
        c = self.chat.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        return c

    def _scroll_bottom(self):
        sb = self.chat.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _insert_html(self, content: str):
        c = self._cursor_end()
        c.insertHtml(content)
        self.chat.setTextCursor(c)
        self._scroll_bottom()

    def _insert_text(self, text: str, color: str = "#dfe1e4"):
        c = self._cursor_end()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        c.insertText(text, fmt)
        self.chat.setTextCursor(c)
        self._scroll_bottom()

    def _update_backend_label(self):
        if self.cfg.get("backend") == "ollama":
            self.chip.setText(f"● Ollama · {self.cfg.get('ollama_model')}")
        else:
            self.chip.setText(f"● Claude · {self.cfg.get('claude_model')}")

    def _refresh_documents(self):
        self.doc_list.clear()
        docs = self.registry.all()
        for meta in docs:
            item = QListWidgetItem(f"📄  {meta['filename']}")
            item.setData(Qt.ItemDataRole.UserRole, meta["id"])
            item.setToolTip(f"{meta.get('path','')}\n{meta['chunks']} fragmentos")
            self.doc_list.addItem(item)
        n = len(docs)
        plural = "fuente" if n == 1 else "fuentes"
        self.sources_count.setText(f"{n} {plural} en memoria")
        self.input_count.setText(f"{n} {plural}")
        self.studio_info.setText(
            "Sube documentos para activar las acciones." if n == 0
            else f"{n} {plural} listas para consultar."
        )

    # ----------------------------------------------------- banner Ollama
    def _show_setup_banner(self, text: str, indeterminate=False, with_progress=False):
        self.setup_label.setText(text)
        self.setup_progress.setVisible(with_progress or indeterminate)
        if indeterminate:
            self.setup_progress.setRange(0, 0)
            self.setup_progress.setFormat("")
        self.setup_banner.setVisible(True)

    def _hide_setup_banner(self):
        self.setup_banner.setVisible(False)

    def _setup_ollama(self):
        if self.cfg.get("backend") != "ollama":
            self._hide_setup_banner()
            return
        self._show_setup_banner("Iniciando la IA local (Ollama)…", indeterminate=True)
        self.server_worker = EnsureServerWorker(self.cfg.get("ollama_url"))
        self.server_worker.result.connect(self._on_server_ready)
        self.server_worker.start()

    def _on_server_ready(self, ok: bool):
        self.server_worker = None
        if not ok:
            self._show_setup_banner(
                "No se encontró Ollama. Instálalo desde ollama.com o coloca el binario "
                "en la carpeta vendor/ollama para que sea totalmente embebido.",
                indeterminate=False,
            )
            return
        model = self.cfg.get("ollama_model")
        try:
            installed = list_models(self.cfg.get("ollama_url"))
        except OllamaError:
            installed = []
        if model in installed:
            self._hide_setup_banner()
            self.statusBar().showMessage("IA local lista", 4000)
            return
        # Auto-descarga del modelo la primera vez.
        self._show_setup_banner(
            f"Preparando la IA local: descargando el modelo «{model}» "
            "(solo la primera vez)…",
            with_progress=True,
        )
        self._set_sending(False)
        self.pull_worker = PullWorker(self.cfg.get("ollama_url"), model)
        self.pull_worker.progress.connect(self._on_setup_progress)
        self.pull_worker.done.connect(self._on_setup_done)
        self.pull_worker.error.connect(self._on_setup_error)
        self.pull_worker.start()

    def _on_setup_progress(self, status: str, percent: int):
        if percent >= 0:
            self.setup_progress.setRange(0, 100)
            self.setup_progress.setValue(percent)
            self.setup_progress.setFormat(f"{status} · {percent}%")
        else:
            self.setup_progress.setRange(0, 0)
            self.setup_progress.setFormat(status)

    def _on_setup_done(self):
        self.pull_worker = None
        self._hide_setup_banner()
        self._set_sending(True)
        self.statusBar().showMessage("IA local lista", 4000)

    def _on_setup_error(self, message: str):
        self.pull_worker = None
        self._show_setup_banner(f"Error preparando la IA local: {message}", indeterminate=False)
        self._set_sending(True)

    def _set_sending(self, enabled: bool):
        self.send_btn.setEnabled(enabled)
        self.input.setEnabled(enabled)

    # --------------------------------------------------------- documentos
    def _upload(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar documentos", "", DOC_FILTER
        )
        if not paths:
            return
        self.add_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.statusBar().showMessage("Procesando documentos…")

        self.ingest_worker = IngestWorker(paths, self.store, self.registry)
        self.ingest_worker.progress.connect(lambda m: self.statusBar().showMessage(m))
        self.ingest_worker.file_done.connect(lambda _meta: self._refresh_documents())
        self.ingest_worker.file_error.connect(self._on_file_error)
        self.ingest_worker.finished_all.connect(self._on_ingest_finished)
        self.ingest_worker.start()

    def _on_file_error(self, name: str, message: str):
        self.statusBar().showMessage(f"«{name}»: {message}", 8000)

    def _on_ingest_finished(self):
        self.add_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.statusBar().showMessage("Documentos actualizados", 4000)
        self._refresh_documents()

    def _delete_selected(self):
        item = self.doc_list.currentItem()
        if not item:
            self.statusBar().showMessage("Selecciona un documento para eliminar", 4000)
            return
        doc_id = item.data(Qt.ItemDataRole.UserRole)
        confirm = QMessageBox.question(
            self,
            "Eliminar documento",
            f"¿Eliminar {item.text().strip()} de la base de conocimiento?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_document(doc_id)
        self.registry.remove(doc_id)
        self._refresh_documents()
        self.statusBar().showMessage("Documento eliminado", 4000)

    # -------------------------------------------------------------- chat
    def _send_preset(self, prompt: str):
        self.input.setPlainText(prompt)
        self._send()

    def _send(self):
        if self.query_worker is not None:
            return
        question = self.input.toPlainText().strip()
        if not question:
            return
        if not self._conversation_started:
            self.chat.clear()
            self._conversation_started = True
        self.input.clear()

        safe = html.escape(question).replace("\n", "<br>")
        self._insert_html(
            '<p style="margin:16px 0 2px 0; color:#7f9bb8; font-size:11px; '
            'letter-spacing:1px;"><b>TÚ</b></p>'
            f'<p style="margin:0 0 2px 0; color:#ededed;">{safe}</p>'
        )
        self._insert_html(
            '<p style="margin:14px 0 2px 0; color:#8fb0c9; font-size:11px; '
            'letter-spacing:1px;"><b>ASISTENTE</b></p>'
        )
        c = self._cursor_end()
        c.insertBlock()
        self.chat.setTextCursor(c)

        self.send_btn.setEnabled(False)
        self.input.setEnabled(False)
        self.statusBar().showMessage("Pensando…")

        self.query_worker = QueryWorker(self.rag, question)
        self.query_worker.token.connect(lambda t: self._insert_text(t))
        self.query_worker.sources_ready.connect(self._on_sources)
        self.query_worker.error.connect(self._on_query_error)
        self.query_worker.finished_answer.connect(self._on_query_finished)
        self.query_worker.start()

    def _on_sources(self, sources: list):
        if sources:
            label = ", ".join(html.escape(s) for s in sources)
            self._insert_html(
                f'<p style="margin:8px 0 2px 0; color:#6f7378; font-size:11px;">'
                f"Fuentes: {label}</p>"
            )

    def _on_query_error(self, message: str):
        self._insert_html(
            f'<p style="margin:4px 0; color:#d08a8a;">⚠ {html.escape(message)}</p>'
        )

    def _on_query_finished(self):
        self.send_btn.setEnabled(True)
        self.input.setEnabled(True)
        self.statusBar().showMessage("Listo", 3000)
        self.query_worker = None
        self.input.setFocus()

    # ----------------------------------------------------------- ajustes
    def _open_settings(self):
        prev_backend = self.cfg.get("backend")
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec():
            self.cfg.update(dlg.values())
            config.save_config(self.cfg)
            self._update_backend_label()
            self.statusBar().showMessage("Configuración guardada", 3000)
            if self.cfg.get("backend") == "ollama":
                self._setup_ollama()
            else:
                self._hide_setup_banner()
