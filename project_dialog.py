# projectDialog.py
import os
import shutil
from os.path import join, basename
from PySide6 import QtWidgets as w
from correct_copy import CopyCorrector



class ProjectDialog(w.QDialog):
    def __init__(self, project_name, project_path, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.project_path = project_path
        self.setWindowTitle(f"Exam : {project_name}")
        self.setFixedSize(600, 400)

        self.initUI()

    def initUI(self):
        layout = w.QVBoxLayout(self)

        self.add_file_btn = w.QPushButton("add a student copy")
        self.add_file_btn.clicked.connect(self.add_copy_to_project)

        self.file_list = w.QListWidget()
        self.refresh_file_list()

        layout.addWidget(self.add_file_btn)
        layout.addWidget(self.file_list)

    def refresh_file_list(self):
        self.file_list.clear()
        for file in os.listdir(self.project_path):
            if file.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                self.file_list.addItem(file)

    def add_copy_to_project(self):
        dialog = w.QFileDialog(self)
        dialog.setNameFilter("PDF or Images (*.pdf *.png *.jpg *.jpeg)")
        dialog.setFileMode(w.QFileDialog.FileMode.ExistingFile)

        if dialog.exec():
            selected_file = dialog.selectedFiles()[0]
            dest = join(self.project_path, basename(selected_file))
            shutil.copy(selected_file, dest)

            corrector = CopyCorrector(self.project_name, self.project_path)
            corrector.clean_image(dest)
            self.refresh_file_list()
