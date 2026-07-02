"""Ventana principal — dos vistas: Chat y Espacios (lienzo 2D).

El panel de Fuentes y el de Studio son QDockWidget: se arrastran a cualquier
lado, se hacen flotantes o se ocultan; la disposición se recuerda. Las notas
y tareas viven en los Espacios, un lienzo estilo Obsidian donde se asocian
documentos, notas, tareas y textos como tarjetas arrastrables.
"""
import html
import re

from PyQt6.QtCore import QPoint, QSettings, QSize, Qt
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core import config
from core.extractor import SUPPORTED_EXTS, is_supported
from core.notes import Workspace
from core.ollama_manager import OllamaError, list_models
from core.rag import RagEngine
from core.spaces import SpacesStore
from core.store import DEFAULT_CATEGORY, build_store
from core.chats import ChatHistoryStore
import uuid
from ui.icons import icon
from ui.markdown import md_to_html
from ui.settings_dialog import SettingsDialog
from ui.spaces_view import SpacesView
from ui.workers import (
    EnsureServerWorker,
    GenerateWorker,
    IngestWorker,
    PullWorker,
    QueryWorker,
    WarmupWorker,
)

DOC_FILTER = (
    "Documentos (*.pdf *.docx *.txt *.md *.markdown *.csv *.json *.log *.rst);;"
    "Todos los archivos (*.*)"
)

ALL_CATEGORIES = "Todas las categorías"

ICON_MUTED = "#9aa0ab"
ICON_ACCENT = "#8ea7ff"

STUDIO_ACTIONS = [
    ("align-left", "Resumen general",
     "Haz un resumen general y estructurado de los documentos."),
    ("lightbulb", "Ideas clave",
     "Enumera las ideas y datos clave de los documentos, en forma de lista."),
    ("help", "Preguntas sugeridas",
     "Sugiéreme 5 preguntas útiles que puedo hacer sobre estos documentos."),
    ("clipboard", "Puntos de acción",
     "Lista las tareas o puntos de acción mencionados en los documentos."),
    ("calendar", "Fechas y plazos",
     "Extrae las fechas, plazos y eventos importantes mencionados en los documentos."),
    ("book-open", "Glosario técnico",
     "Crea un glosario con los términos técnicos que aparecen en los documentos y su definición."),
]

NOTE_SYSTEM = (
    "Eres un asistente que redacta apuntes claros en español a partir de "
    "fragmentos de documentos. Devuelve la nota en Markdown: empieza con un "
    "título en la primera línea con '# ', y usa secciones y listas. "
    "Usa solo la información del contexto."
)

TASKS_SYSTEM = (
    "Eres un asistente que extrae tareas accionables en español a partir de "
    "fragmentos de documentos. Devuelve SOLO una lista de tareas, una por "
    "línea, cada una empezando por '- '. Sin introducción ni cierre."
)


class ChatInput(QPlainTextEdit):
    """Enter envía, Shift+Enter hace salto de línea."""

    def __init__(self, on_submit):
        super().__init__()
        self.setObjectName("chatInput")
        self._on_submit = on_submit
        self.setPlaceholderText("Pregunta sobre tus documentos…  (Shift+Enter: salto de línea)")
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
        self.setWindowTitle("Alexandria")
        self.resize(1380, 850)
        self.setAcceptDrops(True)
        # Ventana sin marco: la barra superior propia hace de barra de título.
        # Se mantienen los hints de min/max para que Aero Snap siga funcionando.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
        )

        self.cfg = config.load_config()
        self.store, self.registry = build_store(self.cfg)
        self.rag = RagEngine(self.store, self.cfg, registry=self.registry)
        self.workspace = Workspace(config.NOTES_PATH)
        self.spaces = SpacesStore(config.SPACES_PATH)
        self.chats_store = ChatHistoryStore(config.STORAGE_DIR / "chats.json")
        self._current_chat_id = uuid.uuid4().hex[:12]

        self.ingest_worker = None
        self.query_worker = None
        self.server_worker = None
        self.pull_worker = None
        self.gen_worker = None
        self.warmup_worker = None
        self._active_workers = set()

        self._messages: list[dict] = []
        self._current_answer: list[str] = []
        self._last_answer = ""
        self._extra_categories: set[str] = set()

        self._build_ui()
        self._refresh_categories()
        self._refresh_documents()
        self._update_backend_label()
        self._welcome()
        self._restore_layout()
        self._show_view(0)
        self._setup_ollama()
        self._warmup_memory()

    # =================================================================== UI
    def _build_ui(self):
        self.stack = QStackedWidget()
        self.chat_panel = self._build_chat_panel()
        self.stack.addWidget(self.chat_panel)  # índice 0: Chat
        self.spaces_view = SpacesView(
            self.spaces, self.workspace, self.registry,
            lambda m: self.statusBar().showMessage(m, 5000),
        )
        self.stack.addWidget(self.spaces_view)          # índice 1: Espacios
        self.setCentralWidget(self.stack)

        self.chat_dock = self._make_dock(
            "Chat IA", "message", "dockChat", QWidget()
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.chat_dock)
        self.chat_dock.setVisible(False)

        self.setMenuWidget(self._build_topbar())

        self.sources_dock = self._make_dock(
            "Fuentes", "folder-open", "dockSources", self._build_sources_panel()
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sources_dock)

        self.studio_dock = self._make_dock(
            "Studio", "sparkles", "dockStudio", self._build_studio_panel()
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.studio_dock)

        self._sync_panel_buttons()
        self.statusBar().showMessage("Listo")

    def _make_dock(self, title: str, icon_name: str, obj_name: str,
                   content: QWidget) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(obj_name)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        # Barra de título propia: se arrastra desde ella para mover el panel.
        titlebar = QWidget()
        titlebar.setObjectName("dockTitle")
        tl = QHBoxLayout(titlebar)
        tl.setContentsMargins(14, 8, 10, 4)
        tl.setSpacing(8)
        grip = QLabel()
        grip.setPixmap(icon("grip", "#4a505c", 14).pixmap(QSize(14, 14)))
        grip.setToolTip("Arrastra para mover este panel (o hazlo flotante)")
        ic = QLabel()
        ic.setPixmap(icon(icon_name, ICON_ACCENT, 15).pixmap(QSize(15, 15)))
        lbl = QLabel(title)
        lbl.setObjectName("dockTitleText")
        tl.addWidget(grip)
        tl.addWidget(ic)
        tl.addWidget(lbl)
        tl.addStretch(1)
        close_btn = QPushButton()
        close_btn.setObjectName("dockClose")
        close_btn.setIcon(icon("x", ICON_MUTED, 13))
        close_btn.setFixedSize(24, 24)
        close_btn.setToolTip("Ocultar panel (se reabre desde la barra superior)")
        close_btn.clicked.connect(dock.close)
        tl.addWidget(close_btn)
        dock.setTitleBarWidget(titlebar)

        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(10, 2, 10, 10)
        wl.addWidget(content)
        dock.setWidget(wrapper)
        dock.visibilityChanged.connect(lambda _v: self._sync_panel_buttons())
        return dock

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topbar")
        bar.setFixedHeight(42)
        self._topbar = bar  # zona de arrastre de la ventana (WM_NCHITTEST)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 4, 0)
        lay.setSpacing(6)

        # ---------------- Izquierda: logo, título, paneles y vistas -------
        logo = QLabel()
        logo.setPixmap(icon("library", ICON_ACCENT, 18).pixmap(QSize(18, 18)))
        title = QLabel("Alexandria")
        title.setObjectName("title")
        lay.addWidget(logo)
        lay.addWidget(title)
        lay.addSpacing(4)

        self.toggle_sources_btn = QPushButton()
        self.toggle_sources_btn.setObjectName("iconGhost")
        self.toggle_sources_btn.setIcon(icon("panel-left", ICON_MUTED, 15))
        self.toggle_sources_btn.setCheckable(True)
        self.toggle_sources_btn.setFixedSize(28, 28)
        self.toggle_sources_btn.setToolTip("Mostrar/ocultar panel de Fuentes")
        self.toggle_sources_btn.clicked.connect(
            lambda checked: self.sources_dock.setVisible(checked)
        )
        lay.addWidget(self.toggle_sources_btn)

        self.toggle_studio_btn = QPushButton()
        self.toggle_studio_btn.setObjectName("iconGhost")
        self.toggle_studio_btn.setIcon(icon("panel-right", ICON_MUTED, 15))
        self.toggle_studio_btn.setCheckable(True)
        self.toggle_studio_btn.setFixedSize(28, 28)
        self.toggle_studio_btn.setToolTip("Mostrar/ocultar panel de Studio")
        self.toggle_studio_btn.clicked.connect(
            lambda checked: self.studio_dock.setVisible(checked)
        )
        lay.addWidget(self.toggle_studio_btn)

        self.toggle_chat_btn = QPushButton()
        self.toggle_chat_btn.setObjectName("iconGhost")
        self.toggle_chat_btn.setIcon(icon("message", ICON_MUTED, 15))
        self.toggle_chat_btn.setCheckable(True)
        self.toggle_chat_btn.setFixedSize(28, 28)
        self.toggle_chat_btn.setToolTip("Mostrar/ocultar panel de Chat")
        self.toggle_chat_btn.clicked.connect(
            lambda checked: self.chat_dock.setVisible(checked)
        )
        self.toggle_chat_btn.setVisible(False)
        lay.addWidget(self.toggle_chat_btn)

        # Conmutador de vista: Chat / Espacios.
        self.chat_view_btn = QPushButton(" Chat")
        self.chat_view_btn.setObjectName("viewTab")
        self.chat_view_btn.setIcon(icon("message", ICON_MUTED, 13))
        self.chat_view_btn.setCheckable(True)
        self.chat_view_btn.setChecked(True)
        self.spaces_view_btn = QPushButton(" Espacios")
        self.spaces_view_btn.setObjectName("viewTab")
        self.spaces_view_btn.setIcon(icon("layout", ICON_MUTED, 13))
        self.spaces_view_btn.setCheckable(True)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.chat_view_btn)
        group.addButton(self.spaces_view_btn)
        self.chat_view_btn.clicked.connect(lambda: self._show_view(0))
        self.spaces_view_btn.clicked.connect(lambda: self._show_view(1))
        switcher = QFrame()
        switcher.setObjectName("viewSwitch")
        sl = QHBoxLayout(switcher)
        sl.setContentsMargins(3, 3, 3, 3)
        sl.setSpacing(2)
        sl.addWidget(self.chat_view_btn)
        sl.addWidget(self.spaces_view_btn)
        lay.addWidget(switcher)

        # ---------------- Centro: modelo de IA en uso ---------------------
        lay.addStretch(1)
        self.chip = QLabel("")
        self.chip.setObjectName("chip")
        lay.addWidget(self.chip)
        lay.addStretch(1)

        # ---------------- Derecha: acciones (solo icono) y ventana --------
        self.history_btn = QPushButton()
        self.history_btn.setObjectName("iconGhost")
        self.history_btn.setIcon(icon("history", ICON_MUTED, 16))
        self.history_btn.setFixedSize(30, 28)
        self.history_btn.setToolTip("Historial de conversaciones")
        self.history_btn.clicked.connect(self._show_history_menu)
        lay.addWidget(self.history_btn)

        new_chat_btn = QPushButton()
        new_chat_btn.setObjectName("iconGhost")
        new_chat_btn.setIcon(icon("new-chat", ICON_MUTED, 16))
        new_chat_btn.setFixedSize(30, 28)
        new_chat_btn.setToolTip("Nueva conversación")
        new_chat_btn.clicked.connect(self._new_conversation)
        lay.addWidget(new_chat_btn)

        settings_btn = QPushButton()
        settings_btn.setObjectName("iconGhost")
        settings_btn.setIcon(icon("settings", ICON_MUTED, 16))
        settings_btn.setFixedSize(30, 28)
        settings_btn.setToolTip("Configuración")
        settings_btn.clicked.connect(self._open_settings)
        lay.addWidget(settings_btn)

        lay.addSpacing(6)

        # Controles de ventana (minimizar / maximizar / cerrar).
        self.min_btn = QPushButton()
        self.min_btn.setObjectName("winBtn")
        self.min_btn.setIcon(icon("minimize", ICON_MUTED, 14))
        self.min_btn.setFixedSize(40, 28)
        self.min_btn.setToolTip("Minimizar")
        self.min_btn.clicked.connect(self.showMinimized)
        lay.addWidget(self.min_btn)

        self.max_btn = QPushButton()
        self.max_btn.setObjectName("winBtn")
        self.max_btn.setIcon(icon("maximize", ICON_MUTED, 13))
        self.max_btn.setFixedSize(40, 28)
        self.max_btn.setToolTip("Maximizar")
        self.max_btn.clicked.connect(self._toggle_maximized)
        lay.addWidget(self.max_btn)

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("winBtnClose")
        self.close_btn.setIcon(icon("x", ICON_MUTED, 14))
        self.close_btn.setFixedSize(40, 28)
        self.close_btn.setToolTip("Cerrar")
        self.close_btn.clicked.connect(self.close)
        lay.addWidget(self.close_btn)
        return bar

    # ------------------------------------------- ventana sin marco nativa
    def _toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange and hasattr(self, "max_btn"):
            if self.isMaximized():
                self.max_btn.setIcon(icon("restore", ICON_MUTED, 13))
                self.max_btn.setToolTip("Restaurar")
            else:
                self.max_btn.setIcon(icon("maximize", ICON_MUTED, 13))
                self.max_btn.setToolTip("Maximizar")

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_native_window_style()
        self._apply_rounded_corners()

    def _apply_native_window_style(self):
        """Devuelve a la ventana sin marco los estilos nativos WS_THICKFRAME,
        WS_CAPTION y los botones min/max: sin ellos Windows no permite
        redimensionar ni aplica Aero Snap. El marco visual se elimina después
        en WM_NCCALCSIZE."""
        try:
            import ctypes

            GWL_STYLE = -16
            WS_CAPTION = 0x00C00000
            WS_THICKFRAME = 0x00040000
            WS_MINIMIZEBOX = 0x00020000
            WS_MAXIMIZEBOX = 0x00010000
            SWP_FLAGS = 0x0002 | 0x0001 | 0x0004 | 0x0010 | 0x0020  # NOMOVE|NOSIZE|NOZORDER|NOACTIVATE|FRAMECHANGED

            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
            user32.SetWindowLongPtrW(
                hwnd, GWL_STYLE,
                style | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX,
            )
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        except Exception:  # noqa: BLE001
            pass

    def _apply_rounded_corners(self):
        """Esquinas redondeadas nativas de Windows 11 (DWM), con sombra."""
        try:
            import ctypes
            from ctypes import wintypes

            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(int(self.winId())),
                wintypes.DWORD(DWMWA_WINDOW_CORNER_PREFERENCE),
                ctypes.byref(ctypes.c_int(DWMWCP_ROUND)),
                ctypes.sizeof(ctypes.c_int),
            )
        except Exception:  # noqa: BLE001 — Windows 10 o sin DWM: sin redondeo
            pass

    def nativeEvent(self, event_type, message):
        """Integración con Windows de la ventana sin marco.

        - WM_NCCALCSIZE: el área cliente ocupa toda la ventana (sin marco ni
          barra de título nativos), compensando el borde al maximizar.
        - WM_NCHITTEST: los bordes redimensionan y la barra superior actúa
          como barra de título nativa (arrastrar, doble clic, Aero Snap).

        Nota: para los mensajes no gestionados se devuelve (False, 0) — llamar
        a super().nativeEvent() provoca un access violation en PyQt6.
        """
        if event_type != b"windows_generic_MSG":
            return False, 0
        import ctypes
        from ctypes import wintypes

        msg = wintypes.MSG.from_address(int(message))

        if msg.message == 0x0083 and msg.wParam:  # WM_NCCALCSIZE
            if self.isMaximized():
                user32 = ctypes.windll.user32
                try:
                    dpi = user32.GetDpiForWindow(msg.hWnd)
                    border = (user32.GetSystemMetricsForDpi(32, dpi)
                              + user32.GetSystemMetricsForDpi(92, dpi))
                except Exception:  # noqa: BLE001
                    border = user32.GetSystemMetrics(32) + user32.GetSystemMetrics(92)
                rect = wintypes.RECT.from_address(msg.lParam)  # rgrc[0]
                rect.left += border
                rect.top += border
                rect.right -= border
                rect.bottom -= border
            return True, 0

        if msg.message == 0x0084:  # WM_NCHITTEST
            x = ctypes.c_short(msg.lParam & 0xFFFF).value
            y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(msg.hWnd, ctypes.byref(rect))
            if not (rect.left <= x < rect.right and rect.top <= y < rect.bottom):
                return False, 0
            dpr = self.devicePixelRatioF() or 1.0

            if not self.isMaximized():
                m = max(4, round(6 * dpr))  # margen de redimensionado
                left, right = x - rect.left <= m, rect.right - x <= m
                top, bottom = y - rect.top <= m, rect.bottom - y <= m
                hit = {
                    (True, False, True, False): 13,   # HTTOPLEFT
                    (False, True, True, False): 14,   # HTTOPRIGHT
                    (True, False, False, True): 16,   # HTBOTTOMLEFT
                    (False, True, False, True): 17,   # HTBOTTOMRIGHT
                    (True, False, False, False): 10,  # HTLEFT
                    (False, True, False, False): 11,  # HTRIGHT
                    (False, False, True, False): 12,  # HTTOP
                    (False, False, False, True): 15,  # HTBOTTOM
                }.get((left, right, top, bottom))
                if hit:
                    return True, hit

            # Zona de la barra superior: título salvo sobre controles.
            local = QPoint(round((x - rect.left) / dpr), round((y - rect.top) / dpr))
            if local.y() < self._topbar.height():
                child = self.childAt(local)
                if (child is not None and not isinstance(child, QPushButton)
                        and (child is self._topbar
                             or self._topbar.isAncestorOf(child))):
                    return True, 2  # HTCAPTION
        return False, 0

    def _show_view(self, index: int):
        if index == 0:  # Vista de Chat
            if hasattr(self, "chat_panel") and hasattr(self, "chat_dock"):
                if self.chat_dock.widget() == self.chat_panel:
                    self.chat_dock.setWidget(QWidget())  # Liberar el panel de chat
                    self.stack.insertWidget(0, self.chat_panel)
                self.chat_dock.setVisible(False)
                self.toggle_chat_btn.setVisible(False)
            self.stack.setCurrentWidget(self.chat_panel)
        else:  # Vista de Espacios
            if hasattr(self, "chat_panel") and hasattr(self, "chat_dock"):
                self.stack.removeWidget(self.chat_panel)
                self.chat_dock.setWidget(self.chat_panel)
                self.chat_dock.setVisible(True)
                self.toggle_chat_btn.setVisible(True)
                self.toggle_chat_btn.setChecked(True)
            self.stack.setCurrentWidget(self.spaces_view)
            self.spaces_view.reload_canvas()

        self.chat_view_btn.setChecked(index == 0)
        self.spaces_view_btn.setChecked(index == 1)

    def _sync_panel_buttons(self):
        if hasattr(self, "toggle_sources_btn"):
            self.toggle_sources_btn.setChecked(self.sources_dock.isVisible())
            self.toggle_studio_btn.setChecked(self.studio_dock.isVisible())
        if hasattr(self, "toggle_chat_btn") and hasattr(self, "chat_dock"):
            self.toggle_chat_btn.setChecked(self.chat_dock.isVisible())

    def _start_worker(self, worker):
        self._active_workers.add(worker)
        worker.finished.connect(lambda: self._active_workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _panel(self) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("panel")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        return frame, lay

    # ------------------------------------------------------- panel Fuentes
    def _build_sources_panel(self) -> QWidget:
        frame, lay = self._panel()
        frame.setMinimumWidth(260)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar documento…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.addAction(
            icon("search", ICON_MUTED, 15), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search_box.textChanged.connect(self._refresh_documents)
        lay.addWidget(self.search_box)

        cat_row = QHBoxLayout()
        cat_row.setSpacing(6)
        self.category_combo = QComboBox()
        self.category_combo.currentIndexChanged.connect(self._refresh_documents)
        cat_row.addWidget(self.category_combo, 1)
        new_cat_btn = QPushButton()
        new_cat_btn.setObjectName("iconBtn")
        new_cat_btn.setIcon(icon("plus", ICON_MUTED, 15))
        new_cat_btn.setToolTip("Crear una categoría nueva")
        new_cat_btn.setFixedSize(36, 34)
        new_cat_btn.clicked.connect(self._new_category)
        cat_row.addWidget(new_cat_btn)
        lay.addLayout(cat_row)

        self.add_btn = QPushButton("  Añadir fuentes")
        self.add_btn.setObjectName("primary")
        self.add_btn.setIcon(icon("upload", "#cdd8ff", 16))
        self.add_btn.clicked.connect(self._upload)
        lay.addWidget(self.add_btn)

        self.doc_list = QListWidget()
        self.doc_list.setSpacing(0)
        self.doc_list.setIconSize(QSize(16, 16))
        self.doc_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.doc_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.doc_list.itemChanged.connect(self._on_doc_check_changed)
        self.doc_list.model().rowsMoved.connect(self._on_docs_reordered)
        self.doc_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.doc_list.customContextMenuRequested.connect(self._doc_context_menu)
        lay.addWidget(self.doc_list, 1)

        hint = QLabel(
            "Marca las fuentes que la IA debe usar. Arrastra para reordenar; "
            "clic derecho para más opciones."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.delete_btn = QPushButton("  Eliminar seleccionada")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.setIcon(icon("trash", ICON_MUTED, 15))
        self.delete_btn.clicked.connect(self._delete_selected)
        lay.addWidget(self.delete_btn)

        self.sources_count = QLabel("")
        self.sources_count.setObjectName("muted")
        lay.addWidget(self.sources_count)
        return frame

    # ---------------------------------------------------------- panel Chat
    def _build_chat_panel(self) -> QWidget:
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(10, 8, 10, 10)
        frame, lay = self._panel()
        frame.setObjectName("chatPanel")
        cl.addWidget(frame)

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

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setObjectName("chatScroll")
        self.chat_scroll.setStyleSheet("background: transparent; border: none;")
        
        self.chat_widget = QWidget()
        self.chat_widget.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(10, 10, 10, 10)
        self.chat_layout.setSpacing(12)
        
        self.chat_scroll.setWidget(self.chat_widget)
        lay.addWidget(self.chat_scroll, 1)

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
        self.send_btn = QPushButton()
        self.send_btn.setObjectName("sendCircle")
        self.send_btn.setIcon(icon("send", "#0b0c0f", 16))
        self.send_btn.setFixedSize(36, 36)
        self.send_btn.setToolTip("Enviar (Enter)")
        self.send_btn.clicked.connect(self._send)
        ib.addWidget(self.send_btn)
        lay.addWidget(self.input_bar)
        return container

    # --------------------------------------------------------- panel Studio
    def _build_studio_panel(self) -> QWidget:
        frame, lay = self._panel()
        frame.setMinimumWidth(295)

        hint = QLabel("Acciones rápidas sobre tus fuentes activas:")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 4, 0)
        il.setSpacing(8)
        for icon_name, label, prompt in STUDIO_ACTIONS:
            card = QPushButton("  " + label)
            card.setObjectName("studioCard")
            card.setIcon(icon(icon_name, ICON_ACCENT, 17))
            card.setIconSize(QSize(17, 17))
            card.setMinimumHeight(46)
            card.clicked.connect(lambda _=False, p=prompt: self._send_preset(p))
            il.addWidget(card)
        il.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        create_hint = QLabel("Crear con IA en el espacio actual:")
        create_hint.setObjectName("muted")
        lay.addWidget(create_hint)

        ai_note_btn = QPushButton("  Nota con IA")
        ai_note_btn.setObjectName("primary")
        ai_note_btn.setIcon(icon("sparkles", "#cdd8ff", 15))
        ai_note_btn.setToolTip("Genera unos apuntes y los coloca en el espacio actual")
        ai_note_btn.clicked.connect(self._ai_note)
        lay.addWidget(ai_note_btn)

        ai_tasks_btn = QPushButton("  Extraer tareas de los documentos")
        ai_tasks_btn.setObjectName("primary")
        ai_tasks_btn.setIcon(icon("list-checks", "#cdd8ff", 15))
        ai_tasks_btn.setToolTip("Extrae tareas y las coloca en el espacio actual")
        ai_tasks_btn.clicked.connect(self._ai_tasks)
        lay.addWidget(ai_tasks_btn)

        self.save_answer_btn = QPushButton("  Guardar última respuesta como nota")
        self.save_answer_btn.setIcon(icon("save", ICON_MUTED, 15))
        self.save_answer_btn.clicked.connect(self._save_answer_as_note)
        lay.addWidget(self.save_answer_btn)

        self.studio_info = QLabel("")
        self.studio_info.setObjectName("muted")
        self.studio_info.setWordWrap(True)
        lay.addWidget(self.studio_info)
        return frame

    # ============================================================== helpers
    def _clear_chat_layout(self):
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                # Limpiar layouts anidados si existieran
                pass

    def _welcome(self):
        self._clear_chat_layout()
        
        welcome_widget = QWidget()
        welcome_widget.setStyleSheet("background: transparent;")
        wl = QVBoxLayout(welcome_widget)
        wl.setContentsMargins(20, 60, 20, 20)
        wl.setSpacing(10)
        
        icon_lbl = QLabel("🏛️")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 34px; background: transparent;")
        wl.addWidget(icon_lbl)
        
        title_lbl = QLabel("Tu base de conocimiento")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet("font-size: 21px; font-weight: bold; color: #f1f1f1; background: transparent;")
        title_lbl.setWordWrap(True)
        wl.addWidget(title_lbl)
        
        desc_lbl = QLabel(
            "Añade documentos en «Fuentes», organízalos por categorías<br>"
            "y pregúntame sobre su contenido. Respondo solo con lo que has subido."
        )
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setStyleSheet("color: #8b909a; font-size: 13.5px; background: transparent;")
        desc_lbl.setWordWrap(True)
        wl.addWidget(desc_lbl)
        
        tip_lbl = QLabel(
            "Consejo: en «Espacios» tienes un lienzo libre para asociar documentos, "
            "notas y tareas<br>como tarjetas que puedes mover a tu gusto (estilo Obsidian Canvas)."
        )
        tip_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip_lbl.setStyleSheet("color: #5f646e; font-size: 12px; margin-top: 10px; background: transparent;")
        tip_lbl.setWordWrap(True)
        wl.addWidget(tip_lbl)
        
        self.chat_layout.addWidget(welcome_widget)
        self.chat_layout.addStretch(1)
        self._scroll_bottom()

    def _scroll_bottom(self):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(15, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

    def _render_chat(self):
        """Reconstruye el chat completo usando widgets nativos para tarjetas redondeadas y semitransparentes."""
        self._clear_chat_layout()
        
        for msg in self._messages:
            role = msg["role"]
            content = msg["content"]
            
            bubble = QFrame()
            # El padding interno del bocadillo se maneja aquí
            bubble.setContentsMargins(12, 12, 12, 12)
            bl = QVBoxLayout(bubble)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(4)
            
            role_lbl = QLabel()
            role_lbl.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 1.5px; background: transparent;")
            
            content_lbl = QLabel()
            content_lbl.setWordWrap(True)
            content_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            
            if role == "user":
                bubble.setObjectName("userBubble")
                bubble.setStyleSheet("""
                    QFrame#userBubble {
                        background-color: rgba(43, 49, 62, 160);
                        border: 1px solid #3a4456;
                        border-radius: 16px;
                    }
                """)
                role_lbl.setText("TÚ")
                role_lbl.setStyleSheet(role_lbl.styleSheet() + " color: #8ea7ff;")
                
                safe = html.escape(content).replace("\n", "<br>")
                content_lbl.setText(f'<div style="color: #ffffff; font-size: 13.5px; line-height: 1.45;">{safe}</div>')
                bl.addWidget(role_lbl)
                bl.addWidget(content_lbl)
                
                # Fila contenedora para alinear a la derecha
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 0, 0, 0)
                rl.addStretch(1)
                rl.addWidget(bubble, 4) # Ocupa como máximo el 80% del ancho
                self.chat_layout.addWidget(row)
            else:
                bubble.setObjectName("assistantBubble")
                bubble.setStyleSheet("""
                    QFrame#assistantBubble {
                        background-color: rgba(23, 26, 32, 170);
                        border: 1px solid #242830;
                        border-radius: 16px;
                    }
                """)
                role_lbl.setText("ASISTENTE")
                role_lbl.setStyleSheet(role_lbl.styleSheet() + " color: #9fb4c9;")
                
                body_html = md_to_html(content)
                html_styled = (
                    "<style>"
                    "p { margin: 0 0 6px 0; } p:last-child { margin: 0; } "
                    "ul, ol { margin: 0 0 6px 0; padding-left: 18px; } "
                    "li { margin-bottom: 2px; } "
                    "pre { background-color: #0b0c0f; padding: 8px; border-radius: 6px; margin: 4px 0; font-family: monospace; } "
                    "code { font-family: monospace; background-color: #0b0c0f; padding: 2px 4px; border-radius: 4px; } "
                    "</style>"
                    f'<div style="color: #dfe1e4; font-size: 13.5px; line-height: 1.45;">{body_html}</div>'
                )
                content_lbl.setText(html_styled)
                bl.addWidget(role_lbl)
                bl.addWidget(content_lbl)
                
                if msg.get("sources"):
                    label = ", ".join(html.escape(s) for s in msg["sources"])
                    src_lbl = QLabel(f"<b>Fuentes:</b> {label}")
                    src_lbl.setWordWrap(True)
                    src_lbl.setStyleSheet("color: #6f7378; font-size: 11px; margin-top: 4px; background: transparent;")
                    bl.addWidget(src_lbl)
                
                # Fila contenedora para alinear a la izquierda
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 0, 0, 0)
                rl.addWidget(bubble, 4) # Ocupa como máximo el 80%
                rl.addStretch(1)
                self.chat_layout.addWidget(row)
                
        # Añadir un stretch al final para empujar todo el contenido hacia arriba
        self.chat_layout.addStretch(1)
        self._scroll_bottom()

    def _update_backend_label(self):
        backend = self.cfg.get("backend", "claude")
        meta = config.BACKENDS.get(backend, config.BACKENDS["claude"])
        kind = "local" if meta["local"] else "nube"
        self.chip.setText(f"{meta['label']} · {config.active_model(self.cfg)} · {kind}")

    # ------------------------------------------------- disposición ventana
    def _settings(self) -> QSettings:
        return QSettings("Alexandria", "Alexandria")

    def _restore_layout(self):
        s = self._settings()
        geo = s.value("geometry")
        state = s.value("windowState")
        if geo is not None:
            self.restoreGeometry(geo)
        if state is not None:
            self.restoreState(state)
        self._sync_panel_buttons()

    def closeEvent(self, event):
        s = self._settings()
        s.setValue("geometry", self.saveGeometry())
        s.setValue("windowState", self.saveState())
        super().closeEvent(event)

    # ------------------------------------------------------- categorías
    def _all_categories(self) -> list[str]:
        cats = set(self.registry.categories()) | self._extra_categories
        return sorted(cats, key=str.casefold)

    def _refresh_categories(self):
        current = self.category_combo.currentText()
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem(icon("folder-open", ICON_MUTED, 15), ALL_CATEGORIES)
        for cat in self._all_categories():
            self.category_combo.addItem(icon("tag", ICON_MUTED, 14), cat, cat)
        idx = self.category_combo.findText(current)
        self.category_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.category_combo.blockSignals(False)

    def _current_category(self) -> str | None:
        """Categoría seleccionada como filtro, o None si «Todas»."""
        if self.category_combo.currentIndex() <= 0:
            return None
        return self.category_combo.currentData()

    def _new_category(self):
        name, ok = QInputDialog.getText(
            self, "Nueva categoría",
            "Nombre de la categoría (p. ej. «Descargadores», «Magnetotérmicos»):",
        )
        name = (name or "").strip()
        if not ok or not name:
            return
        self._extra_categories.add(name)
        self._refresh_categories()
        idx = self.category_combo.findData(name)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        self.statusBar().showMessage(f"Categoría «{name}» creada", 4000)

    # ------------------------------------------------------- documentos
    def _visible_docs(self) -> list[dict]:
        docs = self.registry.all()
        cat = self._current_category()
        if cat:
            docs = [d for d in docs if d.get("category") == cat]
        text = self.search_box.text().strip().casefold()
        if text:
            docs = [d for d in docs if text in d["filename"].casefold()]
        return docs

    def _active_doc_ids(self) -> list[str] | None:
        """Documentos que la IA debe usar: los marcados dentro del filtro actual.

        None = sin restricción (todos los documentos).
        """
        all_docs = self.registry.all()
        cat = self._current_category()
        pool = [d for d in all_docs if not cat or d.get("category") == cat]
        active = [d["id"] for d in pool if d.get("enabled", True)]
        if cat is None and len(active) == len(all_docs):
            return None
        return active

    def _refresh_documents(self):
        self.doc_list.blockSignals(True)
        self.doc_list.clear()
        docs = self._visible_docs()
        for meta in docs:
            item = QListWidgetItem(icon("file-text", "#a9b6d9", 16), meta["filename"])
            item.setData(Qt.ItemDataRole.UserRole, meta["id"])
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsDragEnabled
            )
            item.setCheckState(
                Qt.CheckState.Checked if meta.get("enabled", True)
                else Qt.CheckState.Unchecked
            )
            item.setToolTip(
                f"{meta.get('path', '')}\nCategoría: {meta.get('category', DEFAULT_CATEGORY)}"
                f"\n{meta['chunks']} fragmentos · añadido {meta.get('added_at', '')}"
            )
            self.doc_list.addItem(item)
        self.doc_list.blockSignals(False)

        total = len(self.registry.all())
        n = len(docs)
        plural = "fuente" if total == 1 else "fuentes"
        cat = self._current_category()
        scope = f" · {n} en «{cat}»" if cat else ""
        self.sources_count.setText(f"{total} {plural} en memoria{scope}")
        self.input_count.setText(f"{total} {plural}")
        self.studio_info.setText(
            "Sube documentos para activar las acciones." if total == 0
            else "Las acciones usan las fuentes activas del panel de Fuentes."
        )

    def _on_doc_check_changed(self, item: QListWidgetItem):
        doc_id = item.data(Qt.ItemDataRole.UserRole)
        enabled = item.checkState() == Qt.CheckState.Checked
        self.registry.set_enabled(doc_id, enabled)

    def _on_docs_reordered(self, *args):
        ids = [
            self.doc_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.doc_list.count())
        ]
        filtered = bool(self.search_box.text().strip()) or self._current_category()
        if filtered:
            self.statusBar().showMessage(
                "Orden aplicado a la vista; quita los filtros para guardarlo.", 5000
            )
            return
        self.registry.reorder(ids)
        self.statusBar().showMessage("Orden de fuentes guardado", 3000)

    def _doc_context_menu(self, pos):
        item = self.doc_list.itemAt(pos)
        if not item:
            return
        doc_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        space_action = menu.addAction(icon("layout", ICON_MUTED, 14), "Añadir al espacio actual")
        move_action = menu.addAction(icon("tag", ICON_MUTED, 14), "Cambiar de categoría…")
        delete_action = menu.addAction(icon("trash", ICON_MUTED, 14), "Eliminar de la memoria")
        action = menu.exec(self.doc_list.mapToGlobal(pos))
        if action is space_action:
            self._doc_to_space(doc_id)
        elif action is move_action:
            self._move_doc_category(doc_id)
        elif action is delete_action:
            self.doc_list.setCurrentItem(item)
            self._delete_selected()

    def _doc_to_space(self, doc_id: str):
        space_id = self.spaces_view.current_space_id()
        if not space_id:
            return
        if self.spaces.has_ref(space_id, doc_id):
            self.statusBar().showMessage("Ese documento ya está en el espacio actual", 4000)
            return
        pos = self.spaces_view.canvas.free_position()
        self.spaces.add_item(space_id, "doc", ref=doc_id, x=pos.x(), y=pos.y())
        self.spaces_view.reload_canvas()
        self._show_view(1)
        self.statusBar().showMessage("Documento añadido al espacio", 4000)

    def _move_doc_category(self, doc_id: str):
        meta = self.registry.get(doc_id)
        if not meta:
            return
        cats = self._all_categories()
        current = meta.get("category", DEFAULT_CATEGORY)
        idx = cats.index(current) if current in cats else 0
        cat, ok = QInputDialog.getItem(
            self, "Cambiar categoría",
            f"Categoría para «{meta['filename']}»:", cats, idx, editable=True,
        )
        cat = (cat or "").strip()
        if not ok or not cat:
            return
        self.registry.set_category(doc_id, cat)
        self._extra_categories.add(cat)
        self._refresh_categories()
        self._refresh_documents()

    def _ask_category_for_upload(self) -> str | None:
        cats = self._all_categories()
        preset = self._current_category() or DEFAULT_CATEGORY
        idx = cats.index(preset) if preset in cats else 0
        cat, ok = QInputDialog.getItem(
            self, "Categoría de los documentos",
            "¿En qué categoría quieres guardarlos?\n(Puedes escribir una nueva.)",
            cats, idx, editable=True,
        )
        if not ok:
            return None
        return (cat or "").strip() or DEFAULT_CATEGORY

    def _upload(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar documentos", "", DOC_FILTER
        )
        if paths:
            self._ingest_paths(paths)

    def _ingest_paths(self, paths: list[str]):
        if self.ingest_worker is not None:
            self.statusBar().showMessage("Espera: ya hay documentos procesándose…", 4000)
            return
        category = self._ask_category_for_upload()
        if category is None:
            return
        self._extra_categories.add(category)
        self.add_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.statusBar().showMessage("Procesando documentos…")

        self.ingest_worker = IngestWorker(paths, self.store, self.registry, category)
        self.ingest_worker.progress.connect(lambda m: self.statusBar().showMessage(m))
        self.ingest_worker.file_done.connect(lambda _meta: self._on_file_ingested())
        self.ingest_worker.file_error.connect(self._on_file_error)
        self.ingest_worker.finished_all.connect(self._on_ingest_finished)
        self._start_worker(self.ingest_worker)

    def _on_file_ingested(self):
        self._refresh_categories()
        self._refresh_documents()

    def _on_file_error(self, name: str, message: str):
        self.statusBar().showMessage(f"«{name}»: {message}", 8000)

    def _on_ingest_finished(self):
        self.ingest_worker = None
        self.add_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.statusBar().showMessage("Documentos actualizados", 4000)
        self._refresh_categories()
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
            f"¿Eliminar «{item.text().strip()}» de la base de conocimiento?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_document(doc_id)
        self.registry.remove(doc_id)
        self.spaces.remove_refs(doc_id)  # quita sus tarjetas de los espacios
        self.spaces_view.reload_canvas()
        self._refresh_categories()
        self._refresh_documents()
        self.statusBar().showMessage("Documento eliminado", 4000)

    # ------------------------------------------------------ drag & drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
            is_supported(u.toLocalFile()) for u in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [
            u.toLocalFile() for u in event.mimeData().urls()
            if is_supported(u.toLocalFile())
        ]
        skipped = len(event.mimeData().urls()) - len(paths)
        if skipped:
            exts = ", ".join(sorted(SUPPORTED_EXTS))
            self.statusBar().showMessage(
                f"{skipped} archivo(s) ignorado(s). Formatos: {exts}", 6000
            )
        if paths:
            self._ingest_paths(paths)

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
        self._start_worker(self.pull_worker)

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

    # ----------------------------------------------------- memoria (warmup)
    def _warmup_memory(self):
        self.statusBar().showMessage("Preparando la memoria (modelo de embeddings)…")
        self.warmup_worker = WarmupWorker(self.store)
        self.warmup_worker.ready.connect(
            lambda: self.statusBar().showMessage("Memoria lista", 4000)
        )
        self.warmup_worker.start()

    # -------------------------------------------------------------- chat
    def _new_conversation(self):
        self.rag.reset()
        self._messages.clear()
        self._last_answer = ""
        self._current_chat_id = uuid.uuid4().hex[:12]
        self._welcome()
        self._show_view(0)
        self.statusBar().showMessage("Conversación nueva", 3000)

    def _save_current_chat(self):
        if not self._messages:
            return
        chat = self.chats_store.get_chat(self._current_chat_id)
        if chat:
            title = chat["title"]
        else:
            title = "Nueva conversación"
            for msg in self._messages:
                if msg["role"] == "user":
                    title = msg["content"][:35] + ("..." if len(msg["content"]) > 35 else "")
                    break
        self.chats_store.save_chat(self._current_chat_id, title, self._messages, self.rag.history)

    def _show_history_menu(self):
        menu = QMenu(self)
        chats = self.chats_store.all_chats()
        if not chats:
            no_chat_act = menu.addAction("No hay conversaciones")
            no_chat_act.setEnabled(False)
        else:
            for chat in chats:
                title = chat.get("title", "Conversación sin título")
                act = menu.addAction(icon("message", ICON_MUTED, 14), title)
                act.triggered.connect(lambda _, cid=chat["id"]: self._load_chat(cid))
            
            menu.addSeparator()
            
            # Action to delete the current chat (if active)
            del_curr_act = menu.addAction("Eliminar conversación actual")
            del_curr_act.setIcon(icon("trash", "#ff6b6b", 14))
            del_curr_act.setEnabled(self._current_chat_id in [c["id"] for c in chats])
            del_curr_act.triggered.connect(self._delete_current_chat)
            
            # Action to clear all history
            clear_all_act = menu.addAction("Borrar todo el historial")
            clear_all_act.setIcon(icon("trash", "#ff6b6b", 14))
            clear_all_act.triggered.connect(self._clear_all_history)
            
        menu.exec(self.history_btn.mapToGlobal(QPoint(0, self.history_btn.height())))

    def _load_chat(self, chat_id: str):
        chat = self.chats_store.get_chat(chat_id)
        if chat:
            self._current_chat_id = chat_id
            self._messages = list(chat.get("messages", []))
            self.rag.history = list(chat.get("rag_history", []))
            self._last_answer = ""
            for msg in reversed(self._messages):
                if msg["role"] == "assistant":
                    self._last_answer = msg["content"]
                    break
            if self._messages:
                self._render_chat()
            else:
                self._welcome()
            self._show_view(0)
            self.statusBar().showMessage(f"Cargada: {chat.get('title')}", 4000)

    def _delete_current_chat(self):
        if self._current_chat_id:
            self.chats_store.delete_chat(self._current_chat_id)
            self._new_conversation()
            self.statusBar().showMessage("Conversación eliminada", 4000)

    def _clear_all_history(self):
        ret = QMessageBox.question(
            self, "Borrar historial",
            "¿Seguro que quieres borrar todo el historial de conversaciones?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            for chat in list(self.chats_store.all_chats()):
                self.chats_store.delete_chat(chat["id"])
            self._new_conversation()
            self.statusBar().showMessage("Historial de conversaciones borrado", 4000)

    def _send_preset(self, prompt: str):
        self._show_view(0)
        self.input.setPlainText(prompt)
        self._send()

    def _current_space_context_str(self) -> str | None:
        # Solo inyectar el contexto de los espacios si estamos activamente en la vista de Espacios (evita 429 en chat estándar)
        if self.stack.currentWidget() != self.spaces_view:
            return None

        all_spaces = self.spaces.spaces()
        if not all_spaces:
            return None
            
        space_blocks = []
        
        for space in all_spaces:
            items = space.get("items", [])
            if not items:
                continue
                
            notes_blocks = []
            tasks_blocks = []
            texts_blocks = []
            
            for item in items:
                item_type = item.get("type")
                ref = item.get("ref")
                
                if item_type == "note":
                    note = self.workspace.get_note(ref)
                    if note:
                        notes_blocks.append(
                            f"--- NOTA: {note.get('title', 'Sin título')} ---\n"
                            f"Contenido:\n{note.get('content', '')}"
                        )
                elif item_type == "task":
                    task = next((t for t in self.workspace.tasks() if t["id"] == ref), None)
                    if task:
                        status = "Completada" if task.get("done") else "Pendiente"
                        tasks_blocks.append(
                            f"- Tarea: {task.get('text', '')} | Estado: {status}"
                        )
                elif item_type == "text":
                    texts_blocks.append(
                        f"--- TARJETA DE TEXTO ---\n"
                        f"{item.get('text', '')}"
                    )
            
            blocks = []
            if notes_blocks:
                blocks.append("=== NOTAS ===\n" + "\n\n".join(notes_blocks))
            if tasks_blocks:
                blocks.append("=== TAREAS ===\n" + "\n".join(tasks_blocks))
            if texts_blocks:
                blocks.append("=== TARJETAS DE TEXTO ===\n" + "\n\n".join(texts_blocks))
                
            if blocks:
                space_blocks.append(
                    f"================ ESPACIO: '{space.get('name', 'Sin nombre')}' ================\n"
                    + "\n\n".join(blocks)
                )
                
        if not space_blocks:
            return None
            
        # Indicamos cuál es el espacio que está viendo activamente ahora mismo
        active_id = self.spaces_view.current_space_id()
        active_space = self.spaces.get(active_id) if active_id else None
        active_name = active_space.get("name", "Ninguno") if active_space else "Ninguno"
        
        header = f"Espacio activo actualmente en la pantalla: '{active_name}'\n\n"
        header += "A continuación se muestra el contenido (notas, tareas y textos libres) de TODOS los espacios de trabajo creados en la aplicación:\n\n"
        
        return header + "\n\n\n".join(space_blocks)

    def _send(self):
        if self.query_worker is not None:
            return
        question = self.input.toPlainText().strip()
        if not question:
            return
        self.input.clear()

        # Añadimos el mensaje del usuario y un marcador para el asistente en streaming
        self._messages.append({"role": "user", "content": question})
        self._messages.append({"role": "assistant", "content": "Pensando…", "sources": []})
        self._current_answer = []
        self._render_chat()

        self.send_btn.setEnabled(False)
        self.input.setEnabled(False)
        self.statusBar().showMessage("Pensando…")

        space_ctx = self._current_space_context_str()

        self.query_worker = QueryWorker(self.rag, question, self._active_doc_ids(), space_context=space_ctx)
        self.query_worker.token.connect(self._on_answer_token)
        self.query_worker.sources_ready.connect(self._on_sources)
        self.query_worker.error.connect(self._on_query_error)
        self.query_worker.finished_answer.connect(self._on_query_finished)
        self._start_worker(self.query_worker)

    def _on_answer_token(self, token: str):
        self._current_answer.append(token)
        if self._messages and self._messages[-1]["role"] == "assistant":
            self._messages[-1]["content"] = "".join(self._current_answer)
        self._render_chat()

    def _on_sources(self, sources: list):
        answer = "".join(self._current_answer)
        
        # Interceptar comando de apertura de documento [OPEN_DOC: nombre_archivo]
        import re
        match = re.search(r"\[OPEN_DOC:\s*(.+?)\]", answer)
        if match:
            filename = match.group(1).strip()
            answer = re.sub(r"\[OPEN_DOC:\s*(.+?)\]", "", answer).strip()
            
            all_docs = self.registry.all()
            doc = next((d for d in all_docs if d["filename"].lower() == filename.lower() or filename.lower() in d["filename"].lower()), None)
            if doc and doc.get("path"):
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(doc["path"]))
                self.statusBar().showMessage(f"Documento abierto: {doc['filename']}", 4000)
            else:
                self.statusBar().showMessage(f"No se pudo encontrar el archivo: {filename}", 4000)

        self._last_answer = answer
        if self._messages and self._messages[-1]["role"] == "assistant":
            self._messages[-1]["content"] = answer
            self._messages[-1]["sources"] = sources
        else:
            self._messages.append(
                {"role": "assistant", "content": answer, "sources": sources}
            )
        self._save_current_chat()

    def _on_query_error(self, message: str):
        partial = "".join(self._current_answer)
        content = f"{partial}\n\n⚠ {message}" if partial.strip() else f"⚠ {message}"
        if self._messages and self._messages[-1]["role"] == "assistant":
            self._messages[-1]["content"] = content
        else:
            self._messages.append({"role": "assistant", "content": content, "sources": []})
        self._save_current_chat()
        self._render_chat()

    def _on_query_finished(self):
        self._render_chat()
        self.send_btn.setEnabled(True)
        self.input.setEnabled(True)
        self.statusBar().showMessage("Listo", 3000)
        self.query_worker = None
        self.input.setFocus()

    # ---------------------------------------------- IA → espacio actual
    def _save_answer_as_note(self):
        if not self._last_answer.strip():
            self.statusBar().showMessage("Todavía no hay ninguna respuesta que guardar", 4000)
            return
        title = "Respuesta del chat"
        for msg in reversed(self._messages):
            if msg["role"] == "user":
                title = msg["content"][:60]
                break
        note = self.workspace.add_note(title, self._last_answer, source="chat")
        self.spaces_view.add_note_card(note["id"])
        self._show_view(1)
        self.statusBar().showMessage("Respuesta guardada como nota en el espacio", 4000)

    def _ai_note(self):
        if self.gen_worker is not None:
            self.statusBar().showMessage("La IA ya está generando algo, espera…", 4000)
            return
        topic, ok = QInputDialog.getText(
            self, "Nota con IA",
            "¿Sobre qué tema quieres la nota? (usará tus fuentes activas)",
        )
        topic = (topic or "").strip()
        if not ok or not topic:
            return
        self.statusBar().showMessage(f"Generando nota sobre «{topic}»…")
        prompt = f"Redacta unos apuntes completos y bien organizados sobre: {topic}"
        self.gen_worker = GenerateWorker(
            self.rag, prompt, self._active_doc_ids(), system=NOTE_SYSTEM
        )
        self.gen_worker.done.connect(lambda text: self._on_ai_note_done(topic, text))
        self.gen_worker.error.connect(self._on_gen_error)
        self._start_worker(self.gen_worker)

    def _on_ai_note_done(self, topic: str, text: str):
        self.gen_worker = None
        title = topic
        m = re.match(r"^#\s+(.+)$", text.strip().split("\n", 1)[0])
        if m:
            title = m.group(1).strip()
            text = text.strip().split("\n", 1)[1] if "\n" in text.strip() else ""
        note = self.workspace.add_note(title, text.strip(), source="ia")
        self.spaces_view.add_note_card(note["id"])
        self._show_view(1)
        self.statusBar().showMessage("Nota generada en el espacio actual", 4000)

    def _on_gen_error(self, message: str):
        self.gen_worker = None
        self.statusBar().showMessage(f"⚠ {message}", 8000)

    def _ai_tasks(self):
        if self.gen_worker is not None:
            self.statusBar().showMessage("La IA ya está generando algo, espera…", 4000)
            return
        self.statusBar().showMessage("Extrayendo tareas de los documentos…")
        prompt = (
            "Extrae todas las tareas, acciones pendientes y pasos a seguir "
            "mencionados en los documentos."
        )
        self.gen_worker = GenerateWorker(
            self.rag, prompt, self._active_doc_ids(), system=TASKS_SYSTEM
        )
        self.gen_worker.done.connect(self._on_ai_tasks_done)
        self.gen_worker.error.connect(self._on_gen_error)
        self._start_worker(self.gen_worker)

    def _on_ai_tasks_done(self, text: str):
        self.gen_worker = None
        added = 0
        for line in text.split("\n"):
            line = line.strip()
            m = re.match(r"^(?:[-*•]|\d+[.)])\s+(.+)$", line)
            if m:
                task_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", m.group(1)).strip()
                if task_text:
                    task = self.workspace.add_task(task_text, source="ia")
                    self.spaces_view.add_task_card(task["id"])
                    added += 1
        self._show_view(1)
        self.statusBar().showMessage(
            f"{added} tarea(s) añadida(s) al espacio actual" if added
            else "La IA no encontró tareas en los documentos", 5000
        )

    # ----------------------------------------------------------- ajustes
    def _open_settings(self):
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
