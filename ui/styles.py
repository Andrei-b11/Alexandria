"""Tema oscuro moderno (2026): superficies suaves, acento índigo, bordes 16px.

Inspirado en NotebookLM (paneles y chat) y Notion (notas y tareas), con una
identidad propia más sobria.
"""

# Paleta central
BG = "#0b0c0f"          # fondo de la app
SURFACE = "#131519"     # paneles
SURFACE_2 = "#1a1d23"   # tarjetas / campos
BORDER = "#242830"
BORDER_SOFT = "#1e2229"
TEXT = "#e6e8ec"
MUTED = "#8b909a"
ACCENT = "#8ea7ff"      # índigo suave
ACCENT_DIM = "#2a3350"

STYLE = f"""
* {{
    font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QWidget#root {{
    background-color: {BG};
}}
QDialog {{
    background-color: {SURFACE};
}}

/* ---------- Barra superior ---------- */
QWidget#topbar {{
    background-color: {BG};
    border-bottom: none;
}}
QLabel#logo {{ font-size: 18px; }}
QLabel#title {{
    font-size: 14px;
    font-weight: 650;
    color: #f4f5f7;
    letter-spacing: 0.2px;
}}
QLabel#chip {{
    background-color: transparent;
    border: none;
    padding: 3px 12px;
    color: {MUTED};
    font-size: 11px;
}}

/* ---------- Paneles acoplables ---------- */
QDockWidget {{
    background-color: {BG};
    color: {TEXT};
}}
QDockWidget > QWidget {{ background-color: {BG}; }}
QWidget#dockTitle {{ background-color: {BG}; }}
QLabel#dockTitleText {{
    font-size: 13px;
    font-weight: 650;
    color: #dfe2e8;
    letter-spacing: 0.3px;
}}
QPushButton#dockClose {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 0;
}}
QPushButton#dockClose:hover {{ background: {SURFACE_2}; }}
QMainWindow::separator {{
    background: {BG};
    width: 5px;
    height: 5px;
}}
QMainWindow::separator:hover {{ background: {ACCENT_DIM}; }}

/* ---------- Paneles ---------- */
QFrame#panel {{
    background-color: {SURFACE};
    border: 1px solid {BORDER_SOFT};
    border-radius: 16px;
}}
QFrame#chatPanel {{
    background-color: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #131519, stop:1 #22252c);
    background-image: url(assets/halftone.svg);
    background-position: top left;
    border: 1px solid {BORDER_SOFT};
    border-radius: 16px;
}}
QFrame#userBubble {{
    background-color: rgba(43, 49, 62, 160);
    border: 1px solid #3a4456;
    border-radius: 16px;
}}
QFrame#assistantBubble {{
    background-color: rgba(23, 26, 32, 170);
    border: 1px solid #242830;
    border-radius: 16px;
}}
QLabel#panelTitle {{
    font-size: 14px;
    font-weight: 650;
    color: #f0f1f3;
    letter-spacing: 0.3px;
}}
QLabel#muted {{
    color: {MUTED};
    font-size: 12px;
}}

/* ---------- Listas (documentos, notas, tareas) ---------- */
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER_SOFT};
    border-radius: 10px;
    padding: 9px 10px;
    margin: 3px 2px;
    color: #d4d6d9;
}}
QListWidget::item:selected {{
    background-color: {ACCENT_DIM};
    border: 1px solid #40507e;
    color: #ffffff;
}}
QListWidget::item:hover {{ background-color: #20242c; }}
QListView::drop-indicator {{
    background: {ACCENT};
    height: 2px;
    border-radius: 1px;
}}
QListWidget::indicator {{
    width: 15px; height: 15px;
    border-radius: 4px;
    border: 1px solid #3a3f4a;
    background: {SURFACE};
}}
QListWidget::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    image: none;
}}

/* ---------- Chat ---------- */
QTextBrowser#chatView {{
    background-color: transparent;
    border: none;
    color: #dfe1e4;
}}

/* ---------- Barra de entrada ---------- */
QFrame#inputBar {{
    background-color: {SURFACE_2};
    border: 1px solid #2b303a;
    border-radius: 24px;
}}
QFrame#inputBar:focus-within {{ border: 1px solid {ACCENT}; }}
QPlainTextEdit#chatInput {{
    background-color: transparent;
    border: none;
    color: #f0f1f3;
    font-size: 14px;
}}
QPushButton#sendCircle {{
    background-color: {ACCENT};
    border: none;
    border-radius: 17px;
    color: #0b0c0f;
    font-size: 16px;
    font-weight: 700;
}}
QPushButton#sendCircle:hover {{ background-color: #a7baff; }}
QPushButton#sendCircle:disabled {{ background-color: #2b2f38; color: #6d727c; }}

/* ---------- Botones ---------- */
QPushButton {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 13px;
    color: {TEXT};
}}
QPushButton:hover {{ background-color: #21252d; border-color: #303645; }}
QPushButton:pressed {{ background-color: #171a1f; }}
QPushButton:disabled {{ color: #676c76; background-color: #15171c; border-color: {BORDER_SOFT}; }}
QPushButton#primary {{
    background-color: {ACCENT_DIM};
    border: 1px solid #3d4a75;
    color: #cdd8ff;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: #323d61; }}
QPushButton#ghost {{
    background-color: transparent;
    border: 1px solid {BORDER};
    color: #c5c8cc;
}}
QPushButton#ghost:hover {{ background-color: {SURFACE_2}; }}
QPushButton#iconBtn {{
    padding: 8px 10px;
    border-radius: 10px;
}}
QPushButton#iconGhost {{
    background: transparent;
    border: none;
    border-radius: 9px;
    padding: 0;
}}
QPushButton#iconGhost:hover {{ background: {SURFACE_2}; }}
QPushButton#iconGhost:checked {{
    background: {SURFACE_2};
}}

/* ---------- Controles de ventana ---------- */
QPushButton#winBtn, QPushButton#winBtnClose {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0;
}}
QPushButton#winBtn:hover {{ background: {SURFACE_2}; }}
QPushButton#winBtn:pressed {{ background: {BORDER}; }}
QPushButton#winBtnClose:hover {{ background: #c42b1c; }}
QPushButton#winBtnClose:pressed {{ background: #a02015; }}

/* ---------- Conmutador Chat / Espacios ---------- */
QFrame#viewSwitch {{
    background: transparent;
    border: none;
}}
QPushButton#viewTab {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 4px 12px;
    color: {MUTED};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#viewTab:hover {{
    color: #c6cad2;
    background: {SURFACE_2};
}}
QPushButton#viewTab:checked {{
    background: {SURFACE_2};
    color: #eef0f4;
}}

/* ---------- Lienzo de Espacios ---------- */
QGraphicsView#canvas {{
    background: transparent;
    border: 1px solid {BORDER_SOFT};
    border-radius: 16px;
}}
QPushButton#danger:hover {{
    background-color: #3a2226;
    border-color: #5c3038;
    color: #f0b7bd;
}}

/* ---------- Tarjetas de Studio ---------- */
QPushButton#studioCard {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
    padding: 13px 12px;
    color: #dfe1e4;
    text-align: left;
    font-weight: 500;
}}
QPushButton#studioCard:hover {{
    background-color: #1e2330;
    border: 1px solid #3d4a75;
}}

/* ---------- Pestañas (Studio / Notas / Tareas y Ajustes) ---------- */
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    border: none;
    border-radius: 9px;
    padding: 7px 10px;
    margin-right: 3px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {SURFACE_2};
    color: #eef0f4;
}}
QTabBar::tab:hover:!selected {{ color: #c6cad2; }}

/* ---------- Campos de formulario ---------- */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 10px;
    color: #f0f1f3;
    selection-background-color: #3d4a75;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT_DIM};
}}
QProgressBar {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    text-align: center;
    color: #cdd8ff;
    height: 22px;
}}
QProgressBar::chunk {{
    background-color: #4c5b8f;
    border-radius: 7px;
}}

/* ---------- Banner de configuración ---------- */
QFrame#setupBanner {{
    background-color: #171d2c;
    border: 1px solid #33406a;
    border-radius: 12px;
}}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #2c3038; border-radius: 4px; min-height: 26px; }}
QScrollBar::handle:vertical:hover {{ background: #3a3f4a; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}

QStatusBar {{ color: {MUTED}; background: {BG}; border-top: 1px solid {BORDER_SOFT}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{
    background-color: {SURFACE_2}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 6px;
}}
QMenu {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 5px;
}}
QMenu::item {{ padding: 7px 20px; border-radius: 7px; }}
QMenu::item:selected {{ background-color: {ACCENT_DIM}; }}
"""
