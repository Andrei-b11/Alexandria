"""Animación de «pensando»: geometría dinámica de figuras rellenas.

Port a QPainter de la animación GeometryThinking (Tkinter): 6 figuras
(triángulos, rombos, círculos sólidos y barras) que orbitan, pulsan y
mutan en 5 modos que rotan cada 5 segundos, con color HSV en ciclo
continuo que se acelera.

Cuando la IA termina de pensar, `snapshot()` congela el último fotograma
en un QPixmap transparente, que se queda como icono estático del
asistente.
"""
import hashlib
import math
import random
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPixmap, QPolygonF
from PyQt6.QtWidgets import QApplication, QWidget

BASE = 320.0        # espacio de diseño original; se escala al tamaño del widget
SHAPES = 6          # figuras simultáneas en escena
MODES = 5           # patrones geométricos distintos
MODE_SECONDS = 5.0  # cada cuánto cambia de patrón


class GeometryState:
    """Estado lógico de la animación (fase, modo, color). Separado del widget
    para poder renderizar fotogramas sueltos (icono estático, congelado)."""

    def __init__(self, randomize: bool = False):
        self.phase = 0.0
        self.hue = 0.08          # arranca en naranja (~#FF9500)
        self.color_speed = 0.002
        self.max_color_speed = 0.02
        self.mode = 0
        self._mode_t0 = time.monotonic()
        if randomize:
            # Cada «pensando» arranca en uno de los patrones predefinidos al
            # azar, con fase y color aleatorios: ninguna animación empieza igual.
            self.mode = random.randrange(MODES)
            self.phase = random.uniform(0.0, 2 * math.pi)
            self.hue = random.random()

    def params(self) -> dict:
        """Parámetros serializables del fotograma actual (icono por mensaje)."""
        return {"mode": self.mode, "phase": round(self.phase, 4),
                "hue": round(self.hue, 4)}

    def advance(self):
        self.phase += 0.03
        if self.color_speed < self.max_color_speed:
            self.color_speed += 0.000005
        self.hue = (self.hue + self.color_speed) % 1.0
        now = time.monotonic()
        if now - self._mode_t0 >= MODE_SECONDS:
            self.mode = (self.mode + 1) % MODES
            self._mode_t0 = now

    # ------------------------------------------------------------- dibujo
    def paint(self, p: QPainter, size: float):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.save()
        p.scale(size / BASE, size / BASE)
        center = BASE / 2
        total = SHAPES
        p.setPen(Qt.PenStyle.NoPen)

        for index in range(total):
            cx = cy = center
            shape_size = 20.0
            shape_angle = self.phase
            shape = "triangle"

            # MODO 0: triángulos en órbita giratoria con rotación propia
            if self.mode == 0:
                orbit_angle = (index * 2 * math.pi / total) + self.phase * 0.5
                orbit_radius = 60 + math.sin(self.phase + index) * 15
                cx = center + orbit_radius * math.cos(orbit_angle)
                cy = center + orbit_radius * math.sin(orbit_angle)
                shape_size = 22 + math.sin(self.phase * 2 + index) * 5
                shape_angle = orbit_angle * 2

            # MODO 1: rombos cruzados en órbita inversa
            elif self.mode == 1:
                shape = "diamond"
                orbit_angle = (index * 2 * math.pi / total) - self.phase * 0.3
                orbit_radius = 45 + math.sin(self.phase) * 20
                cx = center + orbit_radius * math.cos(orbit_angle)
                cy = center + orbit_radius * math.sin(orbit_angle)
                shape_size = 18
                shape_angle = -self.phase * 1.5

            # MODO 2: pulsación de círculos concéntricos sólidos
            # (del más grande al más pequeño, con matices alternados)
            elif self.mode == 2:
                shape = "solid_circle"
                shape_size = (total - index) * 20 + math.sin(self.phase * 3) * 10
                shape_angle = 0

            # MODO 3: molinete mecánico de barras sólidas
            elif self.mode == 3:
                shape = "bar"
                base_angle = index * 2 * math.pi / total
                cx = center + 50 * math.cos(base_angle + self.phase * 0.2)
                cy = center + 50 * math.sin(base_angle + self.phase * 0.2)
                shape_size = 25
                shape_angle = base_angle + self.phase * 2

            # MODO 4: caleidoscopio de mutación total (caos en expansión)
            elif self.mode == 4:
                shape = ("triangle", "diamond", "solid_circle", "bar")[index % 4]
                orbit_angle = (index * 2 * math.pi / total) + self.phase
                expand = 70 * (math.sin(self.phase * 0.8) + 1.2) / 2
                cx = center + expand * math.cos(orbit_angle)
                cy = center + expand * math.sin(orbit_angle)
                shape_size = 15 + index * 3
                shape_angle = self.phase * 3

            # Matiz individual por figura sobre el color dinámico global
            local_hue = (self.hue + index * 0.04) % 1.0
            p.setBrush(QColor.fromHsvF(local_hue, 0.85, 0.95))

            p.save()
            p.translate(cx, cy)
            p.rotate(math.degrees(shape_angle))
            if shape == "triangle":
                p.drawPolygon(QPolygonF([
                    QPointF(shape_size * math.cos(i * 2 * math.pi / 3),
                            shape_size * math.sin(i * 2 * math.pi / 3))
                    for i in range(3)
                ]))
            elif shape == "diamond":
                p.drawPolygon(QPolygonF([
                    QPointF(0, -1.3 * shape_size),
                    QPointF(0.8 * shape_size, 0),
                    QPointF(0, 1.3 * shape_size),
                    QPointF(-0.8 * shape_size, 0),
                ]))
            elif shape == "solid_circle":
                p.drawEllipse(QPointF(0, 0), shape_size, shape_size)
            elif shape == "bar":
                p.drawRect(QRectF(-1.5 * shape_size, -0.4 * shape_size,
                                  3.0 * shape_size, 0.8 * shape_size))
            p.restore()
        p.restore()


def render_pixmap(state: GeometryState, size: int) -> QPixmap:
    """Renderiza un fotograma del estado dado a un QPixmap transparente y nítido."""
    screen = QApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    state.paint(p, size)
    p.end()
    return pm


_ICON_CACHE: dict[tuple, QPixmap] = {}


def geometry_icon_pixmap(params: dict, size: int) -> QPixmap:
    """Icono a partir de parámetros guardados {mode, phase, hue} (cacheado)."""
    key = (params.get("mode", 0), params.get("phase", 0.0),
           params.get("hue", 0.08), size)
    cached = _ICON_CACHE.get(key)
    if cached is None:
        state = GeometryState()
        state.mode = int(params.get("mode", 0)) % MODES
        state.phase = float(params.get("phase", 0.0))
        state.hue = float(params.get("hue", 0.08)) % 1.0
        cached = render_pixmap(state, size)
        _ICON_CACHE[key] = cached
    return cached


def geometry_hash_params(text: str) -> dict:
    """Parámetros deterministas derivados de un texto: cada respuesta antigua
    (sin fotograma guardado) obtiene igualmente un icono único y estable."""
    h = hashlib.md5(text.encode("utf-8", errors="replace")).digest()
    return {
        "mode": h[0] % MODES,
        "phase": round(int.from_bytes(h[1:3], "big") / 65535 * 2 * math.pi, 4),
        "hue": round(int.from_bytes(h[3:5], "big") / 65535, 4),
    }


def geometry_static_pixmap(size: int) -> QPixmap:
    """Fotograma estático por defecto (mensaje aún sin icono propio)."""
    return geometry_icon_pixmap({"mode": 0, "phase": 2.4, "hue": 0.08}, size)


class GeometryThinkingWidget(QWidget):
    """Widget animado (~60 fps) con fondo transparente."""

    def __init__(self, size: int = 30, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.state = GeometryState(randomize=True)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self.state.advance()
        self.update()

    def showEvent(self, event):
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def snapshot(self) -> QPixmap:
        """Congela el fotograma actual (para dejarlo como icono estático)."""
        return render_pixmap(self.state, self.width())

    def paintEvent(self, event):
        p = QPainter(self)
        self.state.paint(p, min(self.width(), self.height()))
        p.end()
