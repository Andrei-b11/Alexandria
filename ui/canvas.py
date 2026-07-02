"""Lienzo 2D estilo Obsidian Canvas: tarjetas arrastrables sobre una rejilla.

- Arrastra una tarjeta para moverla (la posición se guarda sola).
- Arrastra el fondo para desplazarte; rueda del ratón para hacer zoom.
- Doble clic para abrir/editar; clic derecho para el menú; Supr para quitar.
"""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsObject, QGraphicsScene, QGraphicsView

from ui.icons import pixmap as icon_pixmap

CARD_W = 200.0
PAD = 12.0
CHECK = 15.0  # lado de la casilla de las tareas

KIND_STYLE = {
    # tipo: (icono, color de acento de la tarjeta)
    "note": ("pen", "#8ea7ff"),
    "doc": ("file-text", "#5fc6b8"),
    "task": ("list-checks", "#7ed49a"),
    "text": ("align-left", "#e8c47c"),
}

BG = QColor("#0d0f13")
DOT = QColor("#23262e")
CARD_BG = QColor("#171a20")
CARD_BG_HOVER = QColor("#1b1f27")
CARD_BORDER = QColor("#262b35")
TITLE_COLOR = QColor("#e8eaee")
BODY_COLOR = QColor("#9aa0ab")
DONE_COLOR = QColor("#5f646e")
SELECT_COLOR = QColor("#8ea7ff")


class CardItem(QGraphicsObject):
    """Tarjeta pintada a mano: título + cuerpo, casilla si es tarea."""

    moved = pyqtSignal()
    double_clicked = pyqtSignal(str)          # item_id
    context_requested = pyqtSignal(str, object)  # item_id, screen_pos
    check_toggled = pyqtSignal(str, bool)     # item_id, checked

    def __init__(self, item_id: str, kind: str, title: str, body: str = "",
                 checked: bool | None = None):
        super().__init__()
        self.item_id = item_id
        self.kind = kind
        self.title = title
        self.body = (body or "").strip()
        if len(self.body) > 420:
            self.body = self.body[:420].rstrip() + "…"
        self.checked = checked
        self._hover = False

        self.setFlags(
            QGraphicsObject.GraphicsItemFlag.ItemIsMovable
            | QGraphicsObject.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        self._title_font = QFont()
        self._title_font.setPointSizeF(9.5)
        self._title_font.setWeight(QFont.Weight.DemiBold)
        self._body_font = QFont()
        self._body_font.setPointSizeF(8.5)
        self._height = self._compute_height()

    # ----------------------------------------------------------- medidas
    def _text_width(self) -> float:
        w = CARD_W - 2 * PAD
        if self.kind == "task":
            w -= CHECK + 8
        return w

    def _compute_height(self) -> float:
        fm_t = QFontMetricsF(self._title_font)
        title_rect = fm_t.boundingRect(
            QRectF(0, 0, self._text_width() - 24, 1000),
            Qt.TextFlag.TextWordWrap.value, self.title,
        )
        h = PAD + max(20.0, min(title_rect.height(), 42.0))
        if self.body:
            fm_b = QFontMetricsF(self._body_font)
            body_rect = fm_b.boundingRect(
                QRectF(0, 0, self._text_width(), 1000),
                Qt.TextFlag.TextWordWrap.value, self.body,
            )
            h += 6 + min(body_rect.height(), 150.0)
        return h + PAD

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, CARD_W, self._height)

    # ------------------------------------------------------------ pintura
    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.boundingRect().adjusted(0.5, 0.5, -0.5, -0.5)
        _icon, accent = KIND_STYLE.get(self.kind, KIND_STYLE["text"])

        painter.setBrush(CARD_BG_HOVER if self._hover else CARD_BG)
        border = QPen(SELECT_COLOR if self.isSelected() else CARD_BORDER,
                      1.6 if self.isSelected() else 1.0)
        painter.setPen(border)
        painter.drawRoundedRect(rect, 11, 11)

        # Barra de acento a la izquierda.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(accent))
        painter.drawRoundedRect(QRectF(rect.left() + 1, rect.top() + 10, 3, rect.height() - 20), 1.5, 1.5)

        x = PAD + 4
        y = PAD

        if self.kind == "task":
            box = self._check_rect()
            painter.setPen(QPen(QColor(accent) if self.checked else CARD_BORDER, 1.3))
            painter.setBrush(QColor(accent) if self.checked else Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box, 4, 4)
            if self.checked:
                painter.setPen(QPen(QColor("#0d0f13"), 1.8))
                painter.drawLine(QPointF(box.left() + 3.2, box.center().y() + 0.5),
                                 QPointF(box.center().x() - 0.5, box.bottom() - 3.5))
                painter.drawLine(QPointF(box.center().x() - 0.5, box.bottom() - 3.5),
                                 QPointF(box.right() - 3.0, box.top() + 3.5))
            x = box.right() + 8
        else:
            pm = icon_pixmap(_icon, accent, 14)
            painter.drawPixmap(QRectF(x, y + 2, 14, 14), pm, QRectF(pm.rect()))
            x += 20

        # Título
        painter.setFont(self._title_font)
        done = self.kind == "task" and self.checked
        painter.setPen(DONE_COLOR if done else TITLE_COLOR)
        title_font = QFont(self._title_font)
        title_font.setStrikeOut(bool(done))
        painter.setFont(title_font)
        title_rect = QRectF(x, y, CARD_W - x - PAD, 44)
        painter.drawText(title_rect, Qt.TextFlag.TextWordWrap.value, self.title)

        # Cuerpo
        if self.body:
            fm_t = QFontMetricsF(self._title_font)
            used = min(fm_t.boundingRect(title_rect, Qt.TextFlag.TextWordWrap.value,
                                         self.title).height(), 42.0)
            painter.setFont(self._body_font)
            painter.setPen(BODY_COLOR)
            body_rect = QRectF(PAD + 4, y + max(20.0, used) + 6,
                               self._text_width(), 150)
            painter.drawText(body_rect, Qt.TextFlag.TextWordWrap.value, self.body)

    def _check_rect(self) -> QRectF:
        return QRectF(PAD + 2, PAD + 2, CHECK, CHECK)

    # ------------------------------------------------------------ eventos
    def hoverEnterEvent(self, event):
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        if (self.kind == "task"
                and event.button() == Qt.MouseButton.LeftButton
                and self._check_rect().contains(event.pos())):
            self.checked = not self.checked
            self.update()
            self.check_toggled.emit(self.item_id, bool(self.checked))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.item_id)
        event.accept()

    def contextMenuEvent(self, event):
        self.context_requested.emit(self.item_id, event.screenPos())
        event.accept()

    def itemChange(self, change, value):
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionHasChanged:
            self.moved.emit()
        return super().itemChange(change, value)


class SpaceCanvas(QGraphicsView):
    """Vista del lienzo: zoom con rueda, paneo arrastrando el fondo."""

    positions_changed = pyqtSignal()        # tras mover tarjetas (con retardo)
    card_double_clicked = pyqtSignal(str)
    card_context = pyqtSignal(str, object)
    card_check_toggled = pyqtSignal(str, bool)
    canvas_context = pyqtSignal(object, object)  # scene_pos, screen_pos
    delete_requested = pyqtSignal(list)     # ids seleccionados (tecla Supr)

    def __init__(self):
        super().__init__()
        self.setObjectName("canvas")
        self._scene = QGraphicsScene(-8000, -8000, 16000, 16000, self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._panning = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self.positions_changed.emit)

    # ------------------------------------------------------------ fondo
    def drawBackground(self, painter: QPainter, rect: QRectF):
        # 1. Dibujar el degradado vertical de fondo fijado al Viewport
        painter.save()
        painter.resetTransform()
        viewport_rect = self.viewport().rect()
        
        from PyQt6.QtGui import QLinearGradient
        grad = QLinearGradient(0, viewport_rect.height(), 0, 0)
        grad.setColorAt(0.0, QColor("#131519"))
        grad.setColorAt(1.0, QColor("#22252c"))
        painter.fillRect(viewport_rect, grad)
        painter.restore()
        
        # 2. Dibujar los puntos del semitono (halftone) en coordenadas de la escena
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        step = 26
        x0 = int(rect.left()) - int(rect.left()) % step
        y0 = int(rect.top()) - int(rect.top()) % step
        
        dot_color = QColor("#2a2f3a")
        dot_color.setAlphaF(0.85)
        painter.setBrush(dot_color)
        painter.setPen(Qt.PenStyle.NoPen)
        
        v_height = float(self.viewport().height()) or 600.0
        transform = self.transform()
        scale_y = transform.m22()
        translate_y = transform.dy()
        
        x = x0
        while x < rect.right():
            y = y0
            while y < rect.bottom():
                # Calcular la Y de la pantalla usando la matriz de transformación
                screen_y = y * scale_y + translate_y
                
                # Factor vertical de abajo (1.0) hacia arriba (0.0)
                factor = screen_y / v_height
                factor = max(0.0, min(1.0, factor))
                
                # Radio de los puntos (entre 0.8px y 6.0px)
                r = 0.8 + (6.0 - 0.8) * factor
                
                if r > 0.8:
                    painter.drawEllipse(QPointF(x, y), r, r)
                    
                y += step
            x += step

    # ---------------------------------------------------------- tarjetas
    def clear_cards(self):
        self._scene.clear()

    def add_card(self, item_id: str, kind: str, title: str, body: str,
                 x: float, y: float, checked: bool | None = None) -> CardItem:
        card = CardItem(item_id, kind, title, body, checked)
        card.setPos(x, y)
        card.moved.connect(self._save_timer.start)
        card.double_clicked.connect(self.card_double_clicked.emit)
        card.context_requested.connect(self.card_context.emit)
        card.check_toggled.connect(self.card_check_toggled.emit)
        self._scene.addItem(card)
        return card

    def positions(self) -> dict[str, tuple]:
        return {
            it.item_id: (it.pos().x(), it.pos().y())
            for it in self._scene.items() if isinstance(it, CardItem)
        }

    def selected_ids(self) -> list[str]:
        return [it.item_id for it in self._scene.selectedItems()
                if isinstance(it, CardItem)]

    def center_content(self):
        items = [it for it in self._scene.items() if isinstance(it, CardItem)]
        if not items:
            self.resetTransform()
            self.centerOn(0, 0)
            return
        rect = items[0].sceneBoundingRect()
        for it in items[1:]:
            rect = rect.united(it.sceneBoundingRect())
        self.fitInView(rect.adjusted(-60, -60, 60, 60),
                       Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11() > 1.2:  # no acercar de más
            self.resetTransform()
            self.centerOn(rect.center())

    def free_position(self) -> QPointF:
        """Un punto libre cerca del centro de la vista para tarjetas nuevas."""
        center = self.mapToScene(self.viewport().rect().center())
        taken = [it.pos() for it in self._scene.items() if isinstance(it, CardItem)]
        pos = QPointF(center.x() - CARD_W / 2, center.y() - 40)
        step = 28
        for _ in range(60):
            if all((abs(pos.x() - t.x()) > 24 or abs(pos.y() - t.y()) > 24) for t in taken):
                return pos
            pos = QPointF(pos.x() + step, pos.y() + step)
        return pos

    # ------------------------------------------------------------ eventos
    def wheelEvent(self, event):
        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        current = self.transform().m11()
        if 0.22 <= current * factor <= 2.6:
            self.scale(factor, factor)

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self.itemAt(event.pos()) is None):
            self._panning = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._panning:
            self._panning = False
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def contextMenuEvent(self, event):
        if self.itemAt(event.pos()) is None:
            self.canvas_context.emit(
                self.mapToScene(event.pos()), event.globalPos()
            )
            event.accept()
            return
        super().contextMenuEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            ids = self.selected_ids()
            if ids:
                self.delete_requested.emit(ids)
                return
        super().keyPressEvent(event)
