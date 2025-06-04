from PySide6 import QtWidgets, QtCore, QtGui

class ManualReviewDialog(QtWidgets.QDialog):
    def __init__(self, image_path, filled, centers, parent=None):
        super().__init__(parent)
        self.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setWindowTitle("Manual review of responses")
        self.resize(1200, 800)

        self.image_path = image_path
        self.filled_init = filled
        self.centers = centers
        self.checkboxes = {}
        self.modified_questions = set()

        layout = QtWidgets.QHBoxLayout(self)

        # Partie gauche
        self.scene = QtWidgets.QGraphicsScene()

        QtGui.QPixmapCache.clear()
        QtCore.QCoreApplication.processEvents()
        self.pixmap = QtGui.QPixmap(self.image_path)

        self.scene.addPixmap(self.pixmap)

        self.view = QtWidgets.QGraphicsView()
        self.view.setScene(self.scene)
        self.view.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        layout.addWidget(self.view, stretch=3)

        # Partie droite : checkbox 200 questions
        scroll = QtWidgets.QScrollArea()
        scroll_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(scroll_widget)

        for q_num in range(1, 201):
            hbox = QtWidgets.QHBoxLayout()
            cb_list = []
            base_idx = (q_num - 1) * 4
            for i, letter in enumerate("ABCD"):
                cb = QtWidgets.QCheckBox(letter)
                if self.filled_init[base_idx + i]:
                    cb.setChecked(True)
                cb_list.append(cb)
                hbox.addWidget(cb)
            form_layout.addRow(f"Q{q_num}", hbox)
            self.checkboxes[q_num] = cb_list

        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll, stretch=2)

        # validation et cancel
        btn_box = QtWidgets.QVBoxLayout()
        validate_btn = QtWidgets.QPushButton("Confirm")
        validate_btn.clicked.connect(self.on_validate)
        btn_box.addWidget(validate_btn)
        layout.addLayout(btn_box)

        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)



    def get_user_filled(self):
        filled = []
        for q_num in range(1, 201):
            cb_list = self.checkboxes[q_num]
            filled += [cb.isChecked() for cb in cb_list]
        return filled

    def on_validate(self):
        self.final_filled = self.get_user_filled()

        for q_num in range(1, 201):
            base_idx = (q_num - 1) * 4
            old_vals = self.filled_init[base_idx:base_idx + 4]
            new_vals = self.final_filled[base_idx:base_idx + 4]
            if old_vals != new_vals:
                self.modified_questions.add(q_num)

        self.accept()