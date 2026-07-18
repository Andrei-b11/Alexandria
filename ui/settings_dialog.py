"""Diálogo de Ajustes: motor de IA, claves, IA local (Ollama y LM Studio),
parámetros del RAG y apariencia del chat.

Ventana sin marco con barra de título propia, siguiendo el mismo estilo que
la ventana principal.
"""
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import config, lmstudio, ollama_manager
from ui.icons import icon
from ui.styles import CURRENT as THEME
from ui.thinking import geometry_static_pixmap
from ui.workers import PullWorker

CLAUDE_MODELS = [
    ("claude-sonnet-5", "★ Recomendado · calidad/precio excelente"),
    ("claude-opus-4-8", "Máxima calidad (más caro)"),
    ("claude-haiku-4-5-20251001", "Muy rápido y barato"),
]
GEMINI_MODELS = [
    ("gemini-2.5-flash", "★ Recomendado · rápido, con capa gratuita"),
    ("gemini-2.5-pro", "Máxima calidad de Google"),
    ("gemini-2.0-flash", "Alternativa ligera"),
]
GROQ_MODELS = [
    ("llama-3.3-70b-versatile", "★ Recomendado · muy rápido"),
    ("llama-3.1-8b-instant", "Ultrarrápido y ligero"),
    ("openai/gpt-oss-120b", "Modelo abierto grande"),
]
OPENAI_MODELS = [
    ("gpt-4o-mini", "★ Recomendado · barato y capaz"),
    ("gpt-4o", "Calidad alta"),
    ("gpt-4.1-mini", "Alternativa reciente"),
]

ACCENT_PRESETS = [
    ("#8ea7ff", "Índigo (original)"),
    ("#7dd4a8", "Verde menta"),
    ("#ffc46b", "Ámbar"),
    ("#ff8fb3", "Rosa"),
    ("#6fd6e8", "Cian"),
    ("#b79cff", "Violeta"),
    ("#ff9e80", "Coral"),
]


def _swatch(color: str, size: int = 14) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor(color))
    return QIcon(pm)


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(680)
        self._cfg = cfg
        self._installed: list[str] = []
        self._pull_worker = None
        self._drag = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("settingsFrame")
        frame.setStyleSheet(
            f"QFrame#settingsFrame {{ background-color: {THEME['SURFACE']}; "
            f"border: 1px solid {THEME['BORDER']}; border-radius: 16px; }} "
            # Con la ventana translúcida, los QScrollArea deben ser transparentes
            # para no pintar un fondo claro por defecto.
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        outer.addWidget(frame)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 8, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self._build_titlebar())

        self.tabs = QTabWidget()
        self.tabs.tabBar().setUsesScrollButtons(False)
        self.tabs.addTab(self._build_general_tab(), icon("settings", "#9aa0ab", 15), "General")
        self.tabs.addTab(self._build_cloud_tab(), icon("cloud", "#9aa0ab", 15), "IA en la nube")
        self.tabs.addTab(self._build_local_tab(), icon("monitor", "#9aa0ab", 15), "IA local")
        self.tabs.addTab(self._build_appearance_tab(), icon("layout", "#9aa0ab", 15), "Apariencia")
        layout.addWidget(self.tabs)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.save_btn = QPushButton("  Guardar")
        self.save_btn.setObjectName("primary")
        self.save_btn.setIcon(icon("save", "#cdd8ff", 14))
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self._refresh_ollama_status()

    # -------------------------------------------- barra de título (arrastre)
    def _build_titlebar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(2, 0, 0, 0)
        hl.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(geometry_static_pixmap(22))
        logo.setFixedSize(22, 22)
        title = QLabel("Ajustes")
        title.setObjectName("title")
        hl.addWidget(logo)
        hl.addWidget(title)
        hl.addStretch(1)
        close_btn = QPushButton()
        close_btn.setObjectName("winBtnClose")
        close_btn.setIcon(icon("x", "#9aa0ab", 14))
        close_btn.setFixedSize(36, 26)
        close_btn.clicked.connect(self.reject)
        hl.addWidget(close_btn)
        return bar

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and event.position().y() <= 44):
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        else:
            self._drag = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag = None
        super().mouseReleaseEvent(event)

    # -------------------------------------------------------------- pestañas
    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(8, 14, 8, 8)

        self.backend = QComboBox()
        for key, meta in config.BACKENDS.items():
            self.backend.addItem(meta["label"], key)
        idx = self.backend.findData(self._cfg.get("backend", "claude"))
        self.backend.setCurrentIndex(max(0, idx))
        form.addRow("Motor de IA activo:", self.backend)

        hint = QLabel(
            "La memoria de documentos es local y compartida: puedes cambiar de "
            "motor cuando quieras sin volver a procesar nada. El botón «IA: App / "
            "IA: Directo» de la barra superior alterna entre responder con tus "
            "documentos o chatear con el modelo a pelo."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        form.addRow("", hint)

        self.top_k = QSpinBox()
        self.top_k.setRange(1, 20)
        self.top_k.setValue(int(self._cfg.get("top_k", 6)))
        form.addRow("Fragmentos por consulta:", self.top_k)

        self.history_turns = QSpinBox()
        self.history_turns.setRange(0, 20)
        self.history_turns.setValue(int(self._cfg.get("history_turns", 6)))
        self.history_turns.setToolTip(
            "Cuántas preguntas/respuestas anteriores recuerda el chat.\n"
            "0 = cada pregunta empieza de cero."
        )
        form.addRow("Memoria de conversación (turnos):", self.history_turns)

        self.web_search = QCheckBox("Buscar en internet si los documentos no tienen la respuesta")
        self.web_search.setChecked(bool(self._cfg.get("web_search", True)))
        form.addRow("", self.web_search)

        emb = QLabel(f"Modelo de embeddings (memoria local):\n{self._cfg.get('embedding_model')}")
        emb.setObjectName("muted")
        emb.setWordWrap(True)
        form.addRow("", emb)
        return w

    def _api_section(self, form: QFormLayout, title: str, key_value: str,
                     placeholder: str, models: list, model_value: str, url: str):
        header = QLabel(title)
        header.setStyleSheet("font-weight:600; font-size:13px; margin-top:6px;")
        form.addRow(header)

        key_edit = QLineEdit(key_value)
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_edit.setPlaceholderText(placeholder)
        form.addRow("API key:", key_edit)

        model_combo = QComboBox()
        model_combo.setEditable(True)
        for model_id, desc in models:
            model_combo.addItem(f"{model_id}", model_id)
            model_combo.setItemData(model_combo.count() - 1, desc, 3)  # ToolTipRole
        model_combo.setCurrentText(model_value)
        form.addRow("Modelo:", model_combo)

        link = QLabel(f'<a href="{url}" style="color:#8ea7ff;">Conseguir API key</a>')
        link.setOpenExternalLinks(True)
        form.addRow("", link)
        return key_edit, model_combo

    def _build_cloud_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        form.setContentsMargins(8, 14, 8, 8)

        cfg = self._cfg
        self.claude_key, self.claude_model = self._api_section(
            form, "Claude (Anthropic)", cfg.get("anthropic_api_key", ""),
            "sk-ant-…", CLAUDE_MODELS, cfg.get("claude_model", "claude-sonnet-5"),
            "https://console.anthropic.com",
        )
        self.gemini_key, self.gemini_model = self._api_section(
            form, "Gemini (Google)", cfg.get("gemini_api_key", ""),
            "AIza…", GEMINI_MODELS, cfg.get("gemini_model", "gemini-2.5-flash"),
            "https://aistudio.google.com/apikey",
        )
        self.groq_key, self.groq_model = self._api_section(
            form, "Groq", cfg.get("groq_api_key", ""),
            "gsk_…", GROQ_MODELS, cfg.get("groq_model", "llama-3.3-70b-versatile"),
            "https://console.groq.com/keys",
        )
        self.openai_key, self.openai_model = self._api_section(
            form, "OpenAI", cfg.get("openai_api_key", ""),
            "sk-…", OPENAI_MODELS, cfg.get("openai_model", "gpt-4o-mini"),
            "https://platform.openai.com/api-keys",
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(w)
        scroll.setMinimumHeight(380)
        return scroll

    def _build_local_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 14, 8, 8)
        layout.setSpacing(10)

        # ----------------------------------------------------------- Ollama
        oll_header = QLabel("Ollama")
        oll_header.setStyleSheet("font-weight:600; font-size:13px;")
        layout.addWidget(oll_header)

        form = QFormLayout()
        form.setSpacing(10)
        self.ollama_url = QLineEdit(self._cfg.get("ollama_url", "http://localhost:11434"))
        form.addRow("URL de Ollama:", self.ollama_url)

        self.ollama_model = QComboBox()
        self.ollama_model.setEditable(True)
        for model_id, _desc in ollama_manager.RECOMMENDED_MODELS:
            self.ollama_model.addItem(model_id)
        self.ollama_model.setCurrentText(self._cfg.get("ollama_model", "qwen2.5:14b"))
        self.ollama_model.currentTextChanged.connect(self._on_model_changed)
        form.addRow("Modelo Ollama:", self.ollama_model)

        self.model_desc = QLabel("")
        self.model_desc.setObjectName("muted")
        self.model_desc.setWordWrap(True)
        form.addRow("", self.model_desc)
        layout.addLayout(form)

        self.ollama_status = QLabel("Comprobando Ollama…")
        self.ollama_status.setObjectName("muted")
        self.ollama_status.setWordWrap(True)
        layout.addWidget(self.ollama_status)

        btn_row = QHBoxLayout()
        self.check_btn = QPushButton("  Comprobar")
        self.check_btn.setIcon(icon("refresh", "#9aa0ab", 14))
        self.check_btn.clicked.connect(self._refresh_ollama_status)
        self.download_btn = QPushButton("  Descargar modelo seleccionado")
        self.download_btn.setIcon(icon("download", "#cdd8ff", 14))
        self.download_btn.setObjectName("primary")
        self.download_btn.clicked.connect(self._download_model)
        btn_row.addWidget(self.check_btn)
        btn_row.addWidget(self.download_btn, 1)
        layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        # -------------------------------------------------------- LM Studio
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #242830; background: #242830; max-height: 1px;")
        layout.addSpacing(4)
        layout.addWidget(sep)

        lms_header = QLabel("LM Studio")
        lms_header.setStyleSheet("font-weight:600; font-size:13px; margin-top:4px;")
        layout.addWidget(lms_header)

        lms_form = QFormLayout()
        lms_form.setSpacing(10)
        self.lms_url = QLineEdit(self._cfg.get("lmstudio_url", "http://localhost:1234"))
        lms_form.addRow("URL de LM Studio:", self.lms_url)

        self.lms_model = QComboBox()
        self.lms_model.setEditable(True)
        self.lms_model.setCurrentText(self._cfg.get("lmstudio_model", ""))
        lms_form.addRow("Modelo LM Studio:", self.lms_model)
        layout.addLayout(lms_form)

        self.lms_status = QLabel(
            "Abre LM Studio y arranca el servidor local (Developer → Start Server); "
            "después pulsa «Detectar modelos»."
        )
        self.lms_status.setObjectName("muted")
        self.lms_status.setWordWrap(True)
        layout.addWidget(self.lms_status)

        lms_btn = QPushButton("  Detectar modelos de LM Studio")
        lms_btn.setIcon(icon("refresh", "#9aa0ab", 14))
        lms_btn.clicked.connect(self._refresh_lmstudio)
        layout.addWidget(lms_btn)

        layout.addStretch(1)
        self._on_model_changed(self.ollama_model.currentText())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(w)
        scroll.setMinimumHeight(380)
        return scroll

    def _build_appearance_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(8, 14, 8, 8)

        self.theme = QComboBox()
        self.theme.addItem(icon("monitor", "#9aa0ab", 14), "  Oscuro (original)", "dark")
        self.theme.addItem(icon("lightbulb", "#e8a33d", 14), "  Claro · acentos grises", "light")
        idx = self.theme.findData(self._cfg.get("theme", "dark"))
        self.theme.setCurrentIndex(max(0, idx))
        form.addRow("Tema de la aplicación:", self.theme)

        self.chat_style = QComboBox()
        self.chat_style.addItem(icon("message", "#8ea7ff", 14), "  Alexandria · burbujas con acento", "alexandria")
        self.chat_style.addItem(icon("monitor", "#9aa0ab", 14), "  LM Studio · minimalista, texto plano", "lmstudio")
        idx = self.chat_style.findData(self._cfg.get("chat_style", "alexandria"))
        self.chat_style.setCurrentIndex(max(0, idx))
        form.addRow("Estilo del chat:", self.chat_style)

        style_hint = QLabel(
            "LM Studio: tus mensajes en burbuja compacta a la derecha y las "
            "respuestas como texto plano a ancho completo, con el nombre del "
            "modelo encima."
        )
        style_hint.setObjectName("muted")
        style_hint.setWordWrap(True)
        form.addRow("", style_hint)

        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(10.0, 20.0)
        self.font_size.setSingleStep(0.5)
        self.font_size.setDecimals(1)
        self.font_size.setSuffix(" px")
        self.font_size.setValue(float(self._cfg.get("chat_font_size", 13.5)))
        form.addRow("Tamaño de letra del chat:", self.font_size)

        self.accent = QComboBox()
        for color, name in ACCENT_PRESETS:
            self.accent.addItem(_swatch(color), f"  {name}", color)
        current = self._cfg.get("chat_accent", "#8ea7ff")
        idx = self.accent.findData(current)
        if idx < 0:
            self.accent.addItem(_swatch(current), f"  Personalizado ({current})", current)
            idx = self.accent.count() - 1
        self.accent.setCurrentIndex(idx)
        form.addRow("Color de acento:", self.accent)

        op_row = QWidget()
        ol = QHBoxLayout(op_row)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(10)
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(60, 255)
        self.opacity.setValue(int(self._cfg.get("chat_bubble_opacity", 170)))
        self.opacity_lbl = QLabel("")
        self.opacity_lbl.setObjectName("muted")
        self.opacity_lbl.setFixedWidth(40)
        self.opacity.valueChanged.connect(
            lambda v: self.opacity_lbl.setText(f"{round(v / 255 * 100)}%")
        )
        self.opacity_lbl.setText(f"{round(self.opacity.value() / 255 * 100)}%")
        ol.addWidget(self.opacity, 1)
        ol.addWidget(self.opacity_lbl)
        form.addRow("Opacidad de burbujas:", op_row)

        self.show_sources = QCheckBox("Mostrar las fuentes bajo cada respuesta")
        self.show_sources.setChecked(bool(self._cfg.get("chat_show_sources", True)))
        form.addRow("", self.show_sources)

        self.thinking_anim = QCheckBox("Animación geométrica mientras la IA piensa")
        self.thinking_anim.setChecked(bool(self._cfg.get("chat_thinking_anim", True)))
        form.addRow("", self.thinking_anim)

        hint = QLabel(
            "El icono junto a cada respuesta es el fotograma exacto en el que la "
            "IA terminó de pensar: único para cada respuesta."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return w

    # ------------------------------------------------------------ LM Studio
    def _refresh_lmstudio(self):
        url = self.lms_url.text().strip()
        if not lmstudio.is_running(url):
            self.lms_status.setText(
                f"⚠ LM Studio no responde en {url}. Abre LM Studio y activa el "
                "servidor local (Developer → Start Server)."
            )
            return
        try:
            models = lmstudio.list_models(url)
        except lmstudio.LMStudioError as e:
            self.lms_status.setText(f"⚠ {e}")
            return
        current = self.lms_model.currentText()
        self.lms_model.clear()
        for m in models:
            self.lms_model.addItem(m)
        if current:
            self.lms_model.setCurrentText(current)
        elif models:
            self.lms_model.setCurrentIndex(0)
        self.lms_status.setText(
            "✓ LM Studio activo. Modelos: " + (", ".join(models) or "ninguno cargado")
        )

    # ------------------------------------------------------------ Ollama
    def _on_model_changed(self, model_id: str):
        descs = dict(ollama_manager.RECOMMENDED_MODELS)
        if model_id in self._installed:
            self.model_desc.setText("✓ Ya instalado en tu equipo.")
        elif model_id in descs:
            self.model_desc.setText(descs[model_id] + "  (no descargado aún)")
        else:
            self.model_desc.setText("Modelo personalizado.")

    def _refresh_ollama_status(self):
        url = self.ollama_url.text().strip()
        if not ollama_manager.is_running(url):
            self.ollama_status.setText(
                "⚠ Ollama no responde. Ábrelo (icono de la bandeja) o ejecuta «ollama serve»."
            )
            self._installed = []
            return
        try:
            self._installed = ollama_manager.list_models(url)
        except ollama_manager.OllamaError as e:
            self.ollama_status.setText(f"⚠ {e}")
            return

        existing = {self.ollama_model.itemText(i) for i in range(self.ollama_model.count())}
        for m in self._installed:
            if m not in existing:
                self.ollama_model.addItem(m)

        if self._installed:
            self.ollama_status.setText(
                "✓ Ollama activo. Instalados: " + ", ".join(self._installed)
            )
        else:
            self.ollama_status.setText("✓ Ollama activo. No hay modelos descargados todavía.")
        self._on_model_changed(self.ollama_model.currentText())

    def _download_model(self):
        if self._pull_worker is not None:
            return
        url = self.ollama_url.text().strip()
        model = self.ollama_model.currentText().strip()
        if not model:
            return
        if not ollama_manager.is_running(url):
            self.ollama_status.setText("⚠ Ollama no responde. Inícialo antes de descargar.")
            return

        self.download_btn.setEnabled(False)
        self.check_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # indeterminado hasta tener tamaño
        self.progress.setFormat("Iniciando…")

        self._pull_worker = PullWorker(url, model)
        self._pull_worker.progress.connect(self._on_pull_progress)
        self._pull_worker.done.connect(self._on_pull_done)
        self._pull_worker.error.connect(self._on_pull_error)
        self._pull_worker.start()

    def _on_pull_progress(self, status: str, percent: int):
        if percent >= 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
            self.progress.setFormat(f"{status} · {percent}%")
        else:
            self.progress.setRange(0, 0)
            self.progress.setFormat(status)

    def _finish_pull(self):
        self.download_btn.setEnabled(True)
        self.check_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self._pull_worker = None

    def _on_pull_done(self):
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat("✓ Modelo descargado")
        self._finish_pull()
        self._refresh_ollama_status()

    def _on_pull_error(self, message: str):
        self.progress.setVisible(False)
        self.ollama_status.setText(f"⚠ Error al descargar: {message}")
        self._finish_pull()

    # ------------------------------------------------------------- salida
    def values(self) -> dict:
        return {
            "backend": self.backend.currentData(),
            "anthropic_api_key": self.claude_key.text().strip(),
            "claude_model": self.claude_model.currentText().strip(),
            "gemini_api_key": self.gemini_key.text().strip(),
            "gemini_model": self.gemini_model.currentText().strip(),
            "groq_api_key": self.groq_key.text().strip(),
            "groq_model": self.groq_model.currentText().strip(),
            "openai_api_key": self.openai_key.text().strip(),
            "openai_model": self.openai_model.currentText().strip(),
            "ollama_url": self.ollama_url.text().strip(),
            "ollama_model": self.ollama_model.currentText().strip(),
            "lmstudio_url": self.lms_url.text().strip(),
            "lmstudio_model": self.lms_model.currentText().strip(),
            "top_k": self.top_k.value(),
            "history_turns": self.history_turns.value(),
            "web_search": self.web_search.isChecked(),
            "theme": self.theme.currentData(),
            "chat_style": self.chat_style.currentData(),
            "chat_font_size": self.font_size.value(),
            "chat_accent": self.accent.currentData(),
            "chat_bubble_opacity": self.opacity.value(),
            "chat_show_sources": self.show_sources.isChecked(),
            "chat_thinking_anim": self.thinking_anim.isChecked(),
        }
