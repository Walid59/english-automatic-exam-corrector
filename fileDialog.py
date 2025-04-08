import sys
from PySide6 import QtWidgets as w

# example from https://www.tutorialspoint.com/pyqt/pyqt_qfiledialog_widget.htm
class UploadFile(w.QMainWindow):
   def __init__(self):
      super().__init__()

      self.initUI()

   def initUI(self):
      self.setWindowTitle("Create project")
      self.setFixedSize(700, 500)
      
      widget = w.QWidget()
      self.setCentralWidget(widget)
      
      main_layout = w.QVBoxLayout()
      widget.setLayout(main_layout)
      
      name_layout = w.QHBoxLayout()
      self.name_label = w.QLabel("Project name:")
      self.name_input = w.QLineEdit()
      name_layout.addWidget(self.name_label)
      name_layout.addWidget(self.name_input)
      
   
      self.button = w.QPushButton("Open File")
      self.button.clicked.connect(self.openFileDialog)
      
      self.file_selected = w.QLabel()
      
      main_layout.addLayout(name_layout)
      main_layout.addWidget(self.button)
      main_layout.addWidget(self.file_selected)

   def openFileDialog(self):
      file_dialog = w.QFileDialog(self)
      file_dialog.setWindowTitle("Open File")
      file_dialog.setFileMode(w.QFileDialog.FileMode.ExistingFile)
      file_dialog.setViewMode(w.QFileDialog.ViewMode.Detail)
      
      if file_dialog.exec():
         selected_files = file_dialog.selectedFiles()
         text = "Selected File: " + selected_files[0]
         self.file_selected.setText(text)
         print(text)

def main():
   app = w.QApplication(sys.argv)
   window = UploadFile()
   window.show()
   sys.exit(app.exec())

if __name__ == "__main__":
   main()