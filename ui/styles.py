"""Temas de la aplicación: oscuro (original) y claro con acentos grises.

`PALETTES` define los tokens de color de cada tema; `apply_theme(app, name)`
construye la hoja de estilos y la aplica en vivo. `CURRENT` es el diccionario
de tokens del tema activo (se actualiza in situ, así que las referencias
importadas siguen siendo válidas tras cambiar de tema).
"""

PALETTES = {
    "dark": {
        # Paleta central
        "BG": "#0b0c0f",
        "SURFACE": "#131519",
        "SURFACE_2": "#1a1d23",
        "BORDER": "#242830",
        "BORDER_SOFT": "#1e2229",
        "TEXT": "#e6e8ec",
        "TEXT_STRONG": "#f4f5f7",
        "MUTED": "#8b909a",
        "FAINT": "#5f646e",
        "ACCENT": "#8ea7ff",
        "ACCENT_HOVER": "#a7baff",
        "ACCENT_DIM": "#2a3350",
        "ACCENT_DIM_BORDER": "#3d4a75",
        "ACCENT_TEXT": "#cdd8ff",
        "HOVER": "#21252d",
        "PRESSED": "#171a1f",
        "SCROLL": "#2c3038",
        "SCROLL_HOVER": "#3a3f4a",
        "SEND_FG": "#0b0c0f",
        # Chat
        "CHAT_GRAD_0": "#131519",
        "CHAT_GRAD_1": "#22252c",
        "CHAT_HALFTONE": "background-image: url(assets/halftone.svg); background-position: top left;",
        "CHAT_USER_RGB": "43, 49, 62",
        "CHAT_USER_BORDER": "#3a4456",
        "CHAT_AI_RGB": "23, 26, 32",
        "CHAT_AI_BORDER": "#242830",
        "CHAT_TEXT": "#dfe1e4",
        "CHAT_TEXT_STRONG": "#ffffff",
        "CODE_BG": "#0b0c0f",
        "ROLE_AI": "#9fb4c9",
        "SRC_TEXT": "#6f7378",
        "LMS_USER_BG": "#2b2d31",
        "LMS_PANEL_BG": "#17181c",
        "INPUT_BORDER": "#2b303a",
    },
    "light": {
        # Tema claro con acentos en tonos grises
        "BG": "#f2f3f5",
        "SURFACE": "#fafbfc",
        "SURFACE_2": "#e9ebee",
        "BORDER": "#d0d4da",
        "BORDER_SOFT": "#dfe2e7",
        "TEXT": "#26292e",
        "TEXT_STRONG": "#17191d",
        "MUTED": "#6b7078",
        "FAINT": "#9aa0a8",
        "ACCENT": "#5a6270",
        "ACCENT_HOVER": "#454c58",
        "ACCENT_DIM": "#dcdfe4",
        "ACCENT_DIM_BORDER": "#b9bec7",
        "ACCENT_TEXT": "#3a404a",
        "HOVER": "#e2e4e9",
        "PRESSED": "#d7dade",
        "SCROLL": "#c3c7cd",
        "SCROLL_HOVER": "#a9aeb6",
        "SEND_FG": "#ffffff",
        # Chat
        "CHAT_GRAD_0": "#fafbfc",
        "CHAT_GRAD_1": "#eef0f3",
        "CHAT_HALFTONE": "",
        "CHAT_USER_RGB": "223, 226, 231",
        "CHAT_USER_BORDER": "#c6cbd2",
        "CHAT_AI_RGB": "255, 255, 255",
        "CHAT_AI_BORDER": "#dfe2e7",
        "CHAT_TEXT": "#2b2e33",
        "CHAT_TEXT_STRONG": "#17191d",
        "CODE_BG": "#e9ebee",
        "ROLE_AI": "#5a6270",
        "SRC_TEXT": "#84898f",
        "LMS_USER_BG": "#e4e6ea",
        "LMS_PANEL_BG": "#f6f7f9",
        "INPUT_BORDER": "#c9cdd4",
    },
}

CURRENT: dict = dict(PALETTES["dark"])

# Compatibilidad con código que importa los tokens sueltos.
BG = CURRENT["BG"]
SURFACE = CURRENT["SURFACE"]
SURFACE_2 = CURRENT["SURFACE_2"]
BORDER = CURRENT["BORDER"]
BORDER_SOFT = CURRENT["BORDER_SOFT"]
TEXT = CURRENT["TEXT"]
MUTED = CURRENT["MUTED"]
ACCENT = CURRENT["ACCENT"]
ACCENT_DIM = CURRENT["ACCENT_DIM"]


def build_style(p: dict) -> str:
    return f"""
* {{
    font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: {p['TEXT']};
}}
QMainWindow, QWidget#root {{
    background-color: {p['BG']};
}}
QDialog {{
    background-color: {p['SURFACE']};
}}

/* ---------- Barra superior ---------- */
QWidget#topbar {{
    background-color: {p['BG']};
    border-bottom: none;
}}
QLabel#logo {{ font-size: 18px; }}
QLabel#title {{
    font-size: 14px;
    font-weight: 650;
    color: {p['TEXT_STRONG']};
    letter-spacing: 0.2px;
}}
QLabel#chip {{
    background-color: transparent;
    border: none;
    padding: 3px 12px;
    color: {p['MUTED']};
    font-size: 11px;
}}

/* ---------- Paneles acoplables ---------- */
QDockWidget {{
    background-color: {p['BG']};
    color: {p['TEXT']};
}}
QDockWidget > QWidget {{ background-color: {p['BG']}; }}
QWidget#dockTitle {{ background-color: {p['BG']}; }}
QLabel#dockTitleText {{
    font-size: 13px;
    font-weight: 650;
    color: {p['TEXT_STRONG']};
    letter-spacing: 0.3px;
}}
QPushButton#dockClose {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 0;
}}
QPushButton#dockClose:hover {{ background: {p['SURFACE_2']}; }}
QMainWindow::separator {{
    background: {p['BG']};
    width: 5px;
    height: 5px;
}}
QMainWindow::separator:hover {{ background: {p['ACCENT_DIM']}; }}

/* ---------- Paneles ---------- */
QFrame#panel {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['BORDER_SOFT']};
    border-radius: 16px;
}}
QFrame#chatPanel {{
    background-color: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 {p['CHAT_GRAD_0']}, stop:1 {p['CHAT_GRAD_1']});
    {p['CHAT_HALFTONE']}
    border: 1px solid {p['BORDER_SOFT']};
    border-radius: 16px;
}}
QFrame#userBubble {{
    background-color: rgba({p['CHAT_USER_RGB']}, 160);
    border: 1px solid {p['CHAT_USER_BORDER']};
    border-radius: 16px;
}}
QFrame#assistantBubble {{
    background-color: rgba({p['CHAT_AI_RGB']}, 170);
    border: 1px solid {p['CHAT_AI_BORDER']};
    border-radius: 16px;
}}
QLabel#panelTitle {{
    font-size: 14px;
    font-weight: 650;
    color: {p['TEXT_STRONG']};
    letter-spacing: 0.3px;
}}
QLabel#muted {{
    color: {p['MUTED']};
    font-size: 12px;
}}

/* ---------- Listas (documentos, notas, tareas) ---------- */
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background-color: {p['SURFACE_2']};
    border: 1px solid {p['BORDER_SOFT']};
    border-radius: 10px;
    padding: 9px 10px;
    margin: 3px 2px;
    color: {p['TEXT']};
}}
QListWidget::item:selected {{
    background-color: {p['ACCENT_DIM']};
    border: 1px solid {p['ACCENT_DIM_BORDER']};
    color: {p['TEXT_STRONG']};
}}
QListWidget::item:hover {{ background-color: {p['HOVER']}; }}
QListView::drop-indicator {{
    background: {p['ACCENT']};
    height: 2px;
    border-radius: 1px;
}}
QListWidget::indicator {{
    width: 15px; height: 15px;
    border-radius: 4px;
    border: 1px solid {p['SCROLL_HOVER']};
    background: {p['SURFACE']};
}}
QListWidget::indicator:checked {{
    background: {p['ACCENT']};
    border: 1px solid {p['ACCENT']};
    image: none;
}}

/* ---------- Chat ---------- */
QTextBrowser#chatView {{
    background-color: transparent;
    border: none;
    color: {p['CHAT_TEXT']};
}}

/* ---------- Barra de entrada ---------- */
QFrame#inputBar {{
    background-color: {p['SURFACE_2']};
    border: 1px solid {p['INPUT_BORDER']};
    border-radius: 24px;
}}
QFrame#inputBar:focus-within {{ border: 1px solid {p['ACCENT']}; }}
QPlainTextEdit#chatInput {{
    background-color: transparent;
    border: none;
    color: {p['TEXT_STRONG']};
    font-size: 14px;
}}
QPushButton#sendCircle {{
    background-color: {p['ACCENT']};
    border: none;
    border-radius: 17px;
    color: {p['SEND_FG']};
    font-size: 16px;
    font-weight: 700;
}}
QPushButton#sendCircle:hover {{ background-color: {p['ACCENT_HOVER']}; }}
QPushButton#sendCircle:disabled {{ background-color: {p['SURFACE_2']}; color: {p['FAINT']}; }}

/* ---------- Botones ---------- */
QPushButton {{
    background-color: {p['SURFACE_2']};
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
    padding: 8px 13px;
    color: {p['TEXT']};
}}
QPushButton:hover {{ background-color: {p['HOVER']}; border-color: {p['SCROLL_HOVER']}; }}
QPushButton:pressed {{ background-color: {p['PRESSED']}; }}
QPushButton:disabled {{ color: {p['FAINT']}; background-color: {p['SURFACE']}; border-color: {p['BORDER_SOFT']}; }}
QPushButton#primary {{
    background-color: {p['ACCENT_DIM']};
    border: 1px solid {p['ACCENT_DIM_BORDER']};
    color: {p['ACCENT_TEXT']};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: {p['ACCENT_DIM_BORDER']}; }}
QPushButton#ghost {{
    background-color: transparent;
    border: 1px solid {p['BORDER']};
    color: {p['TEXT']};
}}
QPushButton#ghost:hover {{ background-color: {p['SURFACE_2']}; }}
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
QPushButton#iconGhost:hover {{ background: {p['SURFACE_2']}; }}
QPushButton#iconGhost:checked {{
    background: {p['SURFACE_2']};
}}

/* ---------- Controles de ventana ---------- */
QPushButton#winBtn, QPushButton#winBtnClose {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0;
}}
QPushButton#winBtn:hover {{ background: {p['SURFACE_2']}; }}
QPushButton#winBtn:pressed {{ background: {p['BORDER']}; }}
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
    color: {p['MUTED']};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#viewTab:hover {{
    color: {p['TEXT']};
    background: {p['SURFACE_2']};
}}
QPushButton#viewTab:checked {{
    background: {p['SURFACE_2']};
    color: {p['TEXT_STRONG']};
}}

/* ---------- Lienzo de Espacios ---------- */
QGraphicsView#canvas {{
    background: transparent;
    border: 1px solid {p['BORDER_SOFT']};
    border-radius: 16px;
}}
QPushButton#danger:hover {{
    background-color: #3a2226;
    border-color: #5c3038;
    color: #f0b7bd;
}}

/* ---------- Tarjetas de Studio ---------- */
QPushButton#studioCard {{
    background-color: {p['SURFACE_2']};
    border: 1px solid {p['BORDER_SOFT']};
    border-radius: 12px;
    padding: 13px 12px;
    color: {p['TEXT']};
    text-align: left;
    font-weight: 500;
}}
QPushButton#studioCard:hover {{
    background-color: {p['HOVER']};
    border: 1px solid {p['ACCENT_DIM_BORDER']};
}}

/* ---------- Pestañas (Studio / Notas / Tareas y Ajustes) ---------- */
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent;
    color: {p['MUTED']};
    border: none;
    border-radius: 9px;
    padding: 7px 10px;
    margin-right: 3px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {p['SURFACE_2']};
    color: {p['TEXT_STRONG']};
}}
QTabBar::tab:hover:!selected {{ color: {p['TEXT']}; }}

/* ---------- Campos de formulario ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {p['SURFACE_2']};
    border: 1px solid {p['BORDER']};
    border-radius: 9px;
    padding: 7px 10px;
    color: {p['TEXT_STRONG']};
    selection-background-color: {p['ACCENT_DIM_BORDER']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {p['ACCENT']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {p['SURFACE_2']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
    selection-background-color: {p['ACCENT_DIM']};
}}
QCheckBox {{ spacing: 8px; color: {p['TEXT']}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: 5px;
    border: 1px solid {p['SCROLL_HOVER']};
    background: {p['SURFACE_2']};
}}
QCheckBox::indicator:hover {{ border-color: {p['ACCENT']}; }}
QCheckBox::indicator:checked {{
    background: {p['ACCENT']};
    border: 1px solid {p['ACCENT']};
}}
QSlider::groove:horizontal {{
    height: 5px;
    background: {p['SURFACE_2']};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {p['ACCENT_DIM']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 15px; height: 15px;
    margin: -5px 0;
    border-radius: 7px;
    background: {p['ACCENT']};
}}
QSlider::handle:horizontal:hover {{ background: {p['ACCENT_HOVER']}; }}
QProgressBar {{
    background-color: {p['SURFACE_2']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
    text-align: center;
    color: {p['ACCENT_TEXT']};
    height: 22px;
}}
QProgressBar::chunk {{
    background-color: {p['ACCENT_DIM_BORDER']};
    border-radius: 7px;
}}

/* ---------- Banner de configuración ---------- */
QFrame#setupBanner {{
    background-color: {p['ACCENT_DIM']};
    border: 1px solid {p['ACCENT_DIM_BORDER']};
    border-radius: 12px;
}}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p['SCROLL']}; border-radius: 4px; min-height: 26px; }}
QScrollBar::handle:vertical:hover {{ background: {p['SCROLL_HOVER']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}

QStatusBar {{ color: {p['MUTED']}; background: {p['BG']}; border-top: 1px solid {p['BORDER_SOFT']}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{
    background-color: {p['SURFACE_2']}; color: {p['TEXT']};
    border: 1px solid {p['BORDER']}; border-radius: 6px; padding: 4px 6px;
}}
QMenu {{
    background-color: {p['SURFACE_2']};
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
    padding: 5px;
}}
QMenu::item {{ padding: 7px 20px; border-radius: 7px; }}
QMenu::item:selected {{ background-color: {p['ACCENT_DIM']}; }}
"""


def apply_theme(app, name: str) -> None:
    """Activa un tema («dark»/«light») y aplica la hoja de estilos en vivo."""
    palette = PALETTES.get(name, PALETTES["dark"])
    CURRENT.clear()
    CURRENT.update(palette)
    app.setStyleSheet(build_style(CURRENT))


# Hoja de estilos por defecto (tema oscuro), por compatibilidad.
STYLE = build_style(PALETTES["dark"])
