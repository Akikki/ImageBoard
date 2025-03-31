# This code utilises VsCode Better Comments

import sys
from PyQt5.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QMainWindow
)
from PyQt5.QtGui import (
    QPixmap, QDragEnterEvent, QDropEvent, QKeyEvent, QKeySequence, QPainter, QPainterPath
)
from PyQt5.QtCore import(
     Qt, QPointF, QRectF
)
from pathlib import Path
import os

class ResizablePixmapItem(QGraphicsPixmapItem):
    HANDLE_SIZE = 10  # Size of the resize handle square in pixels

    def __init__(self, pixmap: QPixmap):
        super().__init__(pixmap)
        # Enable moving and selecting.
        self.setFlags(
            QGraphicsPixmapItem.ItemIsMovable |
            QGraphicsPixmapItem.ItemIsSelectable
        )
        # Store the original pixmap for quality when scaling.
        self.original_pixmap = pixmap
        self.resizing = False
        self.resize_start_pos = QPointF()
        self.start_pixmap_size = pixmap.size()

    def shape(self):
        path = QPainterPath()
        # Return the full bounding rectangle for hit testing,
        # regardless of the image's transparency.
        path.addRect(self.boundingRect())
        return path


    def paint(self, painter: QPainter, option, widget):
        # Draw the pixmap normally.
        super().paint(painter, option, widget)
        # Draw a resize handle in the bottom-right corner.
        rect = self.boundingRect()
        handle_rect = QRectF(
            rect.right() - self.HANDLE_SIZE,
            rect.bottom() - self.HANDLE_SIZE,
            self.HANDLE_SIZE,
            self.HANDLE_SIZE
        )
        painter.setPen(Qt.black)
        painter.drawRect(handle_rect)

    def mousePressEvent(self, event):
        rect = self.boundingRect()
        handle_rect = QRectF(
            rect.right() - self.HANDLE_SIZE,
            rect.bottom() - self.HANDLE_SIZE,
            self.HANDLE_SIZE,
            self.HANDLE_SIZE
        )
        if handle_rect.contains(event.pos()):
            self.resizing = True
            # Disable moving to prevent conflicts with resizing.
            self.setFlag(QGraphicsPixmapItem.ItemIsMovable, False)
            # Use scene coordinates so the starting point remains constant.
            self.resize_start_scene_pos = event.scenePos()
            # Record the current pixmap size.
            self.start_pixmap_size = self.pixmap().size()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            # Compute delta using scene coordinates.
            delta = event.scenePos() - self.resize_start_scene_pos
            if event.modifiers() & Qt.ShiftModifier:
                # Constrain to original aspect ratio.
                ratio = self.start_pixmap_size.width() / self.start_pixmap_size.height()
                if abs(delta.x()) > abs(delta.y()):
                    new_width = int(max(self.start_pixmap_size.width() + delta.x(), 20))
                    new_height = int(new_width / ratio)
                else:
                    new_height = int(max(self.start_pixmap_size.height() + delta.y(), 20))
                    new_width = int(new_height * ratio)
            else:
                new_width = int(max(self.start_pixmap_size.width() + delta.x(), 20))
                new_height = int(max(self.start_pixmap_size.height() + delta.y(), 20))
            new_pixmap = self.original_pixmap.scaled(
                new_width,
                new_height,
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            )
            self.setPixmap(new_pixmap)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resizing:
            self.resizing = False
            # Re-enable moving once resizing is done.
            self.setFlag(QGraphicsPixmapItem.ItemIsMovable, True)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def refreshSize(self):
        self.resizing = True
        new_pixmap = self.original_pixmap.scaled(
            self.start_pixmap_size.width(),
            self.start_pixmap_size.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
    )
        self.setPixmap(new_pixmap)
        self.resizing = False


class BoardView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, 800, 600)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragEnterEvent):
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                item = ResizablePixmapItem(pixmap)
                pos = self.mapToScene(event.pos())
                # Center the image at the drop location.
                item.setPos(pos - QPointF(pixmap.width()/2, pixmap.height()/2))
                self.scene().addItem(item)
        event.acceptProposedAction()

    def keyPressEvent(self, event: QKeyEvent):
        # * Handle copy (Ctrl+C)
        if event.matches(QKeySequence.Copy):
            selected_items = self.scene().selectedItems()
            if selected_items:
                # Copy the first selected image.
                image_item = selected_items[0]
                if isinstance(image_item, QGraphicsPixmapItem):
                    pixmap = image_item.pixmap()
                    QApplication.clipboard().setImage(pixmap.toImage())
            else:
                super().keyPressEvent(event)

        # * Handle paste (Ctrl+V)
        elif event.matches(QKeySequence.Paste):
            clipboard = QApplication.clipboard()
            # Ensure the clipboard contains an image.
            image = clipboard.image()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                item = ResizablePixmapItem(pixmap)
                # Place pasted image at the center of the view.
                pos = self.mapToScene(self.viewport().rect().center())
                item.setPos(pos - QPointF(pixmap.width()/2, pixmap.height()/2))
                self.scene().addItem(item)
            else:
                super().keyPressEvent(event)

        # * Delete key removes selected items.
        elif event.key() == Qt.Key_Delete:
            for item in self.scene().selectedItems():
                self.scene().removeItem(item)
            else:
                super().keyPressEvent(event)

        # * Return element to original size (R)
        elif event.key() == Qt.Key.Key_R:
            for item in self.scene().selectedItems():
                if isinstance(item, ResizablePixmapItem): # Checks is the element is instance of (always is)
                    item.start_pixmap_size = item.original_pixmap.size()
                    item.refreshSize()
        else:
            super().keyPressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Board")
        self.board_view = BoardView()
        self.setCentralWidget(self.board_view)
        self.resize(1920, 1080)

if __name__ == '__main__':
    appdata_path = Path(os.environ['APPDATA'])
    print("AppData (Roaming):", appdata_path)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
