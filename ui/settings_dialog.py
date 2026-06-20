"""Diálogo de Ajustes: motor de IA, claves, parámetros y gestión de modelos Ollama."""
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from core import ollama_manager
from ui.workers import PullWorker


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(480)
        self._cfg = cfg
        self._installed: list[str] = []
        self._pull_worker = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.backend = QComboBox()
        self.backend.addItem("Claude API (en la nube)", "claude")
        self.backend.addItem("Ollama (local)", "ollama")
        idx = self.backend.findData(cfg.get("backend", "claude"))
        self.backend.setCurrentIndex(max(0, idx))
        form.addRow("Motor de IA:", self.backend)

        self.api_key = QLineEdit(cfg.get("anthropic_api_key", ""))
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-ant-…")
        form.addRow("API key Anthropic:", self.api_key)

        self.claude_model = QComboBox()
        self.claude_model.setEditable(True)
        for m in ("claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"):
            self.claude_model.addItem(m)
        self.claude_model.setCurrentText(cfg.get("claude_model", "claude-opus-4-8"))
        form.addRow("Modelo Claude:", self.claude_model)

        self.ollama_url = QLineEdit(cfg.get("ollama_url", "http://localhost:11434"))
        form.addRow("URL de Ollama:", self.ollama_url)

        self.ollama_model = QComboBox()
        self.ollama_model.setEditable(True)
        for model_id, _desc in ollama_manager.RECOMMENDED_MODELS:
            self.ollama_model.addItem(model_id)
        self.ollama_model.setCurrentText(cfg.get("ollama_model", "qwen2.5:14b"))
        self.ollama_model.currentTextChanged.connect(self._on_model_changed)
        form.addRow("Modelo Ollama:", self.ollama_model)

        self.model_desc = QLabel("")
        self.model_desc.setObjectName("status")
        self.model_desc.setWordWrap(True)
        form.addRow("", self.model_desc)

        self.top_k = QSpinBox()
        self.top_k.setRange(1, 20)
        self.top_k.setValue(int(cfg.get("top_k", 5)))
        form.addRow("Fragmentos por consulta:", self.top_k)

        layout.addLayout(form)
        layout.addWidget(self._separator())

        # --- Gestión de modelos Ollama ------------------------------------
        section = QLabel("Gestión de modelos Ollama")
        section.setObjectName("sectionLabel")
        layout.addWidget(section)

        self.ollama_status = QLabel("Comprobando Ollama…")
        self.ollama_status.setObjectName("status")
        self.ollama_status.setWordWrap(True)
        layout.addWidget(self.ollama_status)

        btn_row = QHBoxLayout()
        self.check_btn = QPushButton("↻  Comprobar")
        self.check_btn.clicked.connect(self._refresh_ollama_status)
        self.download_btn = QPushButton("⬇  Descargar modelo seleccionado")
        self.download_btn.setObjectName("primary")
        self.download_btn.clicked.connect(self._download_model)
        btn_row.addWidget(self.check_btn)
        btn_row.addWidget(self.download_btn, 1)
        layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        layout.addWidget(self._separator())

        emb = QLabel(f"Modelo de embeddings (memoria): {cfg.get('embedding_model')}")
        emb.setObjectName("status")
        emb.setWordWrap(True)
        layout.addWidget(emb)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._on_model_changed(self.ollama_model.currentText())
        self._refresh_ollama_status()

    # ------------------------------------------------------------ helpers
    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#333333;")
        return line

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

        # Añade los instalados al desplegable (sin duplicar).
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
            "anthropic_api_key": self.api_key.text().strip(),
            "claude_model": self.claude_model.currentText().strip(),
            "ollama_url": self.ollama_url.text().strip(),
            "ollama_model": self.ollama_model.currentText().strip(),
            "top_k": self.top_k.value(),
        }
