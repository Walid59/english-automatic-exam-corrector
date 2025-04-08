import os
import sys
from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QIcon
from os.path import isdir, join
from fileDialog import UploadFile

class App(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("English Exam Corrector")
        self.setFixedSize(700, 500)

        self.PATH = "projects"
        self.projects = ["New project"] + [f for f in os.listdir(self.PATH) if isdir(join(self.PATH, f))]

        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.content_widget = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.content_widget)
        self.grid_layout.setSpacing(10)

        self.scroll_area.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll_area)

        self.load_projects()

    def load_projects(self):
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        for index, project_name in enumerate(self.projects):
            container = QtWidgets.QWidget()
            vbox = QtWidgets.QVBoxLayout(container)
            vbox.setAlignment(QtCore.Qt.AlignCenter)

            btn = QtWidgets.QPushButton()
            btn.setFixedSize(120, 120) 
            btn.setIcon(QIcon("resources/icons/folder.svg"))
            btn.setIconSize(QtCore.QSize(100, 100))
            btn.clicked.connect(lambda _, name=project_name: self.open_project(name))

            label = QtWidgets.QLabel(project_name)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setFixedSize(120, 20)

            vbox.addWidget(btn)
            vbox.addWidget(label)
            container.setLayout(vbox)

            row, col = divmod(index, 4)
            self.grid_layout.addWidget(container, row, col)

    def open_project(self, project_name):
        if project_name == "New project":
            self.create_new_project()
        else:
            QtWidgets.QMessageBox.information(self, "Project Open", f"Opening {project_name}")

    def create_new_project(self):
        self.dialog_window = UploadFile()
        self.dialog_window.show()
        # new_name, ok = QtWidgets.QInputDialog.getText(self, "New Project", "Enter project name:")
        # if ok and new_name:
        #     os.makedirs(join(self.PATH, new_name), exist_ok=False)
        #     self.projects.append(new_name)
        #     self.load_projects()
    
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    widget = App()
    widget.show()
    sys.exit(app.exec())
