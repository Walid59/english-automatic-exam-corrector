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

        self.scroll_area.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll_area)

        self.setup_dirs()


    def list_projects(self) -> list[str]:
        return sorted(
            f for f in os.listdir(cons.DIR_PATH)
            if isdir(join(cons.DIR_PATH, f))
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
        project_path = join(cons.DIR_PATH, project_name)
        dialog = ProjectDialog(project_name, project_path, self)
        dialog.exec()
        
    def create_new_project(self):
        dialog = UploadFile(self)
        dialog.setModal(True) # block parent window
        if dialog.exec():
            self.load_projects()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    widget = App()
    widget.show()
    sys.exit(app.exec())