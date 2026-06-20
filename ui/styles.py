"""Tema oscuro pulido, inspirado en NotebookLM / Obsidian."""

STYLE = """
* {
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: #e3e3e3;
}
QMainWindow, QWidget#root {
    background-color: #0f0f10;
}
QDialog {
    background-color: #1a1b1d;
}

/* ---------- Barra superior ---------- */
QWidget#topbar {
    background-color: #0f0f10;
    border-bottom: 1px solid #242528;
}
QLabel#logo {
    font-size: 18px;
}
QLabel#title {
    font-size: 16px;
    font-weight: 600;
    color: #f1f1f1;
}
QLabel#chip {
    background-color: #1d1e20;
    border: 1px solid #2c2d30;
    border-radius: 13px;
    padding: 4px 12px;
    color: #b9bdc4;
    font-size: 12px;
}

/* ---------- Paneles (Fuentes / Chat / Studio) ---------- */
QFrame#panel {
    background-color: #161718;
    border: 1px solid #232427;
    border-radius: 14px;
}
QLabel#panelTitle {
    font-size: 14px;
    font-weight: 600;
    color: #ededed;
}
QLabel#muted {
    color: #8e9398;
    font-size: 12px;
}
QLabel#emptyTitle {
    font-size: 22px;
    font-weight: 600;
    color: #f1f1f1;
}
QLabel#emptyIcon {
    font-size: 40px;
}

/* ---------- Lista de documentos ---------- */
QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget::item {
    background-color: #1d1e20;
    border: 1px solid #292a2d;
    border-radius: 10px;
    padding: 10px 10px;
    margin: 3px 0;
    color: #d4d6d9;
}
QListWidget::item:selected {
    background-color: #26303f;
    border: 1px solid #3a536f;
    color: #ffffff;
}
QListWidget::item:hover {
    background-color: #232427;
}

/* ---------- Chat ---------- */
QTextBrowser#chatView {
    background-color: transparent;
    border: none;
    color: #dfe1e4;
}

/* ---------- Barra de entrada ---------- */
QFrame#inputBar {
    background-color: #1d1e20;
    border: 1px solid #2f3033;
    border-radius: 22px;
}
QPlainTextEdit#chatInput {
    background-color: transparent;
    border: none;
    color: #ededed;
    font-size: 14px;
}
QPushButton#sendCircle {
    background-color: #8ab4f8;
    border: none;
    border-radius: 17px;
    color: #0f0f10;
    font-size: 16px;
    font-weight: 700;
}
QPushButton#sendCircle:hover { background-color: #a4c5fa; }
QPushButton#sendCircle:disabled { background-color: #34363a; color: #7d7d7d; }

/* ---------- Botones ---------- */
QPushButton {
    background-color: #1f2022;
    border: 1px solid #303134;
    border-radius: 10px;
    padding: 9px 14px;
    color: #e3e3e3;
}
QPushButton:hover { background-color: #2a2b2e; }
QPushButton:pressed { background-color: #1a1b1d; }
QPushButton:disabled { color: #6a6a6a; background-color: #1a1b1d; border-color: #262629; }
QPushButton#primary {
    background-color: #2b3340;
    border: 1px solid #3a536f;
    color: #cfe0f7;
    font-weight: 600;
}
QPushButton#primary:hover { background-color: #33414f; }
QPushButton#ghost {
    background-color: transparent;
    border: 1px solid #2c2d30;
    color: #c5c8cc;
}
QPushButton#ghost:hover { background-color: #1f2022; }

/* ---------- Tarjetas de Studio ---------- */
QPushButton#studioCard {
    background-color: #1d1e20;
    border: 1px solid #292a2d;
    border-radius: 12px;
    padding: 14px 12px;
    color: #dfe1e4;
    text-align: left;
    font-weight: 500;
}
QPushButton#studioCard:hover {
    background-color: #232733;
    border: 1px solid #3a536f;
}

/* ---------- Campos de formulario ---------- */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background-color: #1d1e20;
    border: 1px solid #303134;
    border-radius: 8px;
    padding: 7px 9px;
    color: #ededed;
    selection-background-color: #3a536f;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #4a5d72; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #1d1e20;
    border: 1px solid #303134;
    selection-background-color: #26303f;
}
QProgressBar {
    background-color: #1d1e20;
    border: 1px solid #303134;
    border-radius: 8px;
    text-align: center;
    color: #cfe0f7;
    height: 22px;
}
QProgressBar::chunk {
    background-color: #4a5d72;
    border-radius: 7px;
}

/* ---------- Banner de configuración (descarga del modelo) ---------- */
QFrame#setupBanner {
    background-color: #1b2330;
    border: 1px solid #34506e;
    border-radius: 12px;
}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical { background: transparent; width: 9px; margin: 0; }
QScrollBar::handle:vertical { background: #313234; border-radius: 4px; min-height: 26px; }
QScrollBar::handle:vertical:hover { background: #3f4042; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar:horizontal { height: 0; }

QStatusBar { color: #8e9398; background: #0f0f10; border-top: 1px solid #242528; }
QStatusBar::item { border: none; }
QToolTip {
    background-color: #1d1e20; color: #e3e3e3;
    border: 1px solid #303134; border-radius: 6px; padding: 4px 6px;
}
"""
