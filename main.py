import os
import sys
import constants as cons
from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QIcon
from os.path import isdir, join
from fileDialog import UploadFile
from project_dialog import ProjectDialog

class App(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("English Exam Corrector")
        self.setFixedSize(700, 500)

        os.makedirs(cons.DIR_PATH, exist_ok=True)
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.content_widget = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.content_widget)
        self.grid_layout.setSpacing(10)

        self.change_dir_button = QtWidgets.QPushButton("Changer le chemin des projets")
        self.change_dir_button.clicked.connect(self.change_project_dir)
        self.main_layout.addWidget(self.change_dir_button)

        self.scroll_area.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll_area)

        self.project_dir = self.load_project_dir()
        os.makedirs(self.project_dir, exist_ok=True)
        self.setup_dirs()



    def load_project_dir(self):
        config_path = "config.txt"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return f.read().strip()
        else:
            return os.path.abspath("projects")

    def save_project_dir(self, new_path):
        full_path = os.path.join(new_path, "projects")
        os.makedirs(full_path, exist_ok=True)
        with open("config.txt", "w") as f:
            f.write(full_path)
        self.project_dir = full_path
        self.setup_dirs()

    def change_project_dir(self):
        new_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Choisir un nouveau dossier de projets")
        if new_dir:
            self.save_project_dir(new_dir)


    def list_projects(self) -> list[str]:
        return sorted(
            f for f in os.listdir(self.project_dir)
            if isdir(join(self.project_dir, f))
        )

    def setup_dirs(self):
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        self.load_projects()
        
    def load_projects(self):
        self.create_project_UI("New project", is_project=False)
        for index, project_name in enumerate(self.list_projects()):
            if project_name == "__temp__":
                continue
            self.create_project_UI(project_name, index + 1)
            
    def create_project_UI(self, project_name, index=None, is_project=True):
            container = QtWidgets.QWidget()
            vbox = QtWidgets.QVBoxLayout(container)
            vbox.setAlignment(QtCore.Qt.AlignCenter)

            btn = QtWidgets.QPushButton()      
            btn.setFixedSize(120, 120) 
            btn.setIcon(QIcon(cons.FOLDER_ICON if is_project else cons.ADD_ICON))

            btn.setIconSize(QtCore.QSize(100, 100))
            if is_project:
                btn.clicked.connect(lambda _, name=project_name: self.open_project(name))
                
            else:    
                btn.clicked.connect(lambda: self.create_new_project())

            label = QtWidgets.QLabel(project_name)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setFixedSize(120, 20)

            vbox.addWidget(btn)
            vbox.addWidget(label)
            container.setLayout(vbox)
            
            if(index is None):
                row, col = divmod(0, 4)
            else:
                row, col = divmod(index, 4)
            self.grid_layout.addWidget(container, row, col)
            
    def open_project(self, project_name):
        project_path = join(self.project_dir, project_name)
        dialog = ProjectDialog(project_name, project_path, self)
        dialog.exec()
        
    def create_new_project(self):
        dialog = UploadFile(self, project_dir=self.project_dir)
        dialog.setModal(True) # block parent window
        if dialog.exec():
            self.setup_dirs()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    widget = App()
    widget.show()
    sys.exit(app.exec())