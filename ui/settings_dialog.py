"""Diálogo de Ajustes: motor de IA activo, claves por proveedor y parámetros."""
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import config, ollama_manager
from ui.icons import icon
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


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(560)
        self._cfg = cfg
        self._installed: list[str] = []
        self._pull_worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), icon("settings", "#9aa0ab", 15), "General")
        self.tabs.addTab(self._build_cloud_tab(), icon("cloud", "#9aa0ab", 15), "IA en la nube")
        self.tabs.addTab(self._build_ollama_tab(), icon("monitor", "#9aa0ab", 15), "IA local (Ollama)")
        layout.addWidget(self.tabs)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._refresh_ollama_status()

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
            "motor cuando quieras sin volver a procesar nada."
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

    def _build_ollama_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 14, 8, 8)
        layout.setSpacing(10)
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
        layout.addStretch(1)

        self._on_model_changed(self.ollama_model.currentText())
        return w

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
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
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
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(True)
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
            "top_k": self.top_k.value(),
            "history_turns": self.history_turns.value(),
        }
