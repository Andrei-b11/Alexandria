"""Biblioteca de Alejandría — punto de entrada.

Una app de escritorio (PyQt6) que indexa tus documentos en una base de
conocimiento local (memoria vectorial) y responde preguntas sobre ellos
usando Claude (API) u Ollama (local).
"""
import sys
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from ui.main_window import MainWindow
from ui.styles import STYLE


def main():
    # Fix taskbar icon grouping on Windows
    try:
        myappid = "alexandria.library.v1"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Alexandria")
    app.setWindowIcon(QIcon("assets/icono_png.ico"))
    app.setStyleSheet(STYLE)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())



if __name__ == "__main__":
    main()
