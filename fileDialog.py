import sys
import os
from os.path import join, basename
import constants as cons
from PySide6 import QtWidgets as w
from PySide6 import QtCore
from shutil import copy

class UploadFile(w.QDialog):
    def __init__(self, parent=None):
        self.app_instance = parent
        self.selected_files = None
        self.project_name = ""
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Create project")
        self.setFixedSize(700, 500)

        main_layout = w.QVBoxLayout(self)

        self.outer_stack = w.QStackedWidget()
        main_layout.addWidget(self.outer_stack)

        self.page_0_handler()
        self.page_1_handler()

        self.outer_stack.setCurrentIndex(0)

    def page_0_handler(self):
        self.page_0 = w.QWidget()
        layout = w.QVBoxLayout(self.page_0)

        name_layout = w.QHBoxLayout()
        self.name_label = w.QLabel("Project name:")
        self.name_input = w.QLineEdit()
        name_layout.addWidget(self.name_label)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        self.mode_group = w.QButtonGroup(self)
        self.radio_import = w.QRadioButton("Import a corrected file (PDF or image file)")
        self.radio_manual = w.QRadioButton("Create correction manually")
        self.radio_import.setChecked(True)

        self.mode_group.addButton(self.radio_import)
        self.mode_group.addButton(self.radio_manual)

        layout.addWidget(self.radio_import)
        layout.addWidget(self.radio_manual)

        self.manual_options_container = w.QWidget()
        manual_layout = w.QVBoxLayout(self.manual_options_container)
        manual_layout.setContentsMargins(20, 0, 0, 0)

        self.manual_options_group = w.QButtonGroup(self)
        self.radio_manual_toeic = w.QRadioButton("TOEIC")
        self.radio_manual_custom = w.QRadioButton("Custom correction")
        self.radio_manual_toeic.setChecked(True)

        self.manual_options_group.addButton(self.radio_manual_toeic)
        self.manual_options_group.addButton(self.radio_manual_custom)

        manual_layout.addWidget(w.QLabel("Exam type (for manual creation):"))
        manual_layout.addWidget(self.radio_manual_toeic)
        manual_layout.addWidget(self.radio_manual_custom)

        layout.addWidget(self.manual_options_container)

        self.radio_import.toggled.connect(self.toggle_manual_options)
        self.toggle_manual_options()

        self.next_button = w.QPushButton("Next")
        self.next_button.clicked.connect(self.goto_page_1)
        layout.addWidget(self.next_button, alignment=QtCore.Qt.AlignRight)

        self.outer_stack.addWidget(self.page_0)

    def toggle_manual_options(self):
        visible = self.radio_manual.isChecked()
        self.manual_options_container.setVisible(visible)

    def page_1_handler(self):
        self.page_1 = w.QWidget()
        layout = w.QVBoxLayout(self.page_1)

        self.dynamic_area = w.QStackedWidget()

        self.import_widget = w.QWidget()
        import_layout = w.QVBoxLayout(self.import_widget)
        self.import_open_button = w.QPushButton("Choose File")
        self.import_open_button.clicked.connect(self.open_file_dialog)
        self.file_name_input = w.QLabel()
        import_layout.addWidget(self.import_open_button)
        import_layout.addWidget(self.file_name_input)

        self.exam_widget = w.QScrollArea()
        scroll_content = w.QWidget()
        scroll_layout = w.QVBoxLayout(scroll_content)
        self.toeic_buttons = []

        for i in range(1, 11):
            group_box = w.QGroupBox(f"Question {i}")
            hbox = w.QHBoxLayout(group_box)
            button_group = w.QButtonGroup(self)
            row_buttons = []
            for choice in ["A", "B", "C", "D"]:
                btn = w.QRadioButton(choice)
                button_group.addButton(btn)
                hbox.addWidget(btn)
                row_buttons.append(btn)
            self.toeic_buttons.append(button_group)
            scroll_layout.addWidget(group_box)

        scroll_content.setLayout(scroll_layout)
        self.exam_widget.setWidget(scroll_content)
        self.exam_widget.setWidgetResizable(True)

        self.custom_widget = w.QLabel("TODO : Custom correction interface here")
        self.custom_widget.setAlignment(QtCore.Qt.AlignCenter)

        self.dynamic_area.addWidget(self.import_widget)
        self.dynamic_area.addWidget(self.exam_widget)
        self.dynamic_area.addWidget(self.custom_widget)

        layout.addWidget(self.dynamic_area)

        buttons_layout = w.QHBoxLayout()
        self.back_button = w.QPushButton("Back")
        self.back_button.clicked.connect(lambda: self.outer_stack.setCurrentIndex(0))
        self.confirm_button = w.QPushButton("Confirm")
        self.confirm_button.clicked.connect(self.create_project)

        buttons_layout.addWidget(self.back_button)
        buttons_layout.addWidget(self.confirm_button)

        layout.addLayout(buttons_layout)
        self.outer_stack.addWidget(self.page_1)

    def goto_page_1(self):
        self.project_name = self.name_input.text().strip()
        if not self.project_name:
            w.QMessageBox.warning(self, "Missing Fields", "Please enter a project name.")
            return
        elif self.project_name in self.app_instance.list_projects():
            w.QMessageBox.warning(self, "Name already exists", "Please change project name.")
            return

        if self.radio_import.isChecked():
            self.dynamic_area.setCurrentWidget(self.import_widget)
        elif self.radio_manual.isChecked():
            if self.radio_manual_toeic.isChecked():
                self.dynamic_area.setCurrentWidget(self.exam_widget)
            else:
                self.dynamic_area.setCurrentWidget(self.custom_widget)

        self.outer_stack.setCurrentIndex(1)

    def create_project(self):
        if self.radio_manual.isChecked() and self.radio_manual_toeic.isChecked():
            corrections = []
            for i, group in enumerate(self.toeic_buttons, 1):
                selected = group.checkedButton()
                if not selected:
                    w.QMessageBox.warning(self, "Incomplete", f"Please answer Question {i}.")
                    return
                corrections.append(f"{i},{selected.text()}")

        project_path = join(cons.DIR_PATH, self.project_name)
        try:
            os.makedirs(project_path, exist_ok=False)

            if self.radio_import.isChecked():
                if not self.selected_files:
                    w.QMessageBox.warning(self, "Missing File", "Please select a file to import.")
                    return
                copy(self.selected_files[0], project_path)

            elif self.radio_manual.isChecked():
                if self.radio_manual_toeic.isChecked():
                    with open(join(project_path, "toeic_correction.csv"), "w") as f:
                        f.write("\n".join(corrections))
                else:
                    with open(join(project_path, "custom_correction.csv"), "w") as f:
                        f.write("Custom correction to be filled.")

            self.accept()
        except FileExistsError:
            w.QMessageBox.warning(self, "Error", "A project with this name already exists.")
        except OSError as e:
            w.QMessageBox.critical(self, "System Error", f"Failed to create the project:\n{e}")

    def open_file_dialog(self):
        file_dialog = w.QFileDialog(self)
        file_dialog.setWindowTitle("Open File")
        file_dialog.setNameFilter("PDF or Images (*.png *.jpg *.jpeg *.pdf)")
        file_dialog.setFileMode(w.QFileDialog.FileMode.ExistingFile)
        file_dialog.setViewMode(w.QFileDialog.ViewMode.Detail)

        if file_dialog.exec():
            self.selected_files = file_dialog.selectedFiles()
            text = "Selected File: " + self.selected_files[0]
            self.file_name_input.setText(text)
            print(text)

