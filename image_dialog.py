from PySide6 import QtWidgets, QtGui
from PySide6.QtWidgets import QDialog


class ImageViewerDialog(QDialog):
    def __init__(self, pixmap, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.view = QtWidgets.QGraphicsView()
        self.scene = QtWidgets.QGraphicsScene(self)
        self.view.setScene(self.scene)
        self.view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.view.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)

        self.pixmap_item = QtWidgets.QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.view)
        self.setLayout(layout)
        self.resize(800, 600)

        self.scale_factor = 1.0

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        zoom_in = angle > 0
        factor = 1.25 if zoom_in else 0.8
        self.scale_factor *= factor
        self.view.scale(factor, factor)
