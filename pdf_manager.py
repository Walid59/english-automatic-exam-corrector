from PySide6.QtCore import Signal, QObject
import os
import subprocess

class PDFConversionManager(QObject):
    image_ready = Signal(str)
    progress = Signal(int, int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, pdf_path, output_folder, base_name):
        super().__init__()
        self.pdf_path = pdf_path
        self.output_folder = output_folder
        self.base_name = base_name
        self.pdftoppm_path = os.path.join("tools", "pdftoppm.exe")

    def run(self):
        try:
            os.makedirs(self.output_folder, exist_ok=True)

            output_prefix = os.path.join(self.output_folder, self.base_name)
            cmd = [
                self.pdftoppm_path,
                "-jpeg",
                "-r", "100",
                self.pdf_path,
                output_prefix
            ]

            subprocess.run(cmd, check=True)

            images = sorted([
                os.path.join(self.output_folder, f)
                for f in os.listdir(self.output_folder)
                if f.startswith(self.base_name) and f.endswith(".jpg")
            ])

            total = len(images)
            for i, img in enumerate(images):
                self.image_ready.emit(img)
                self.progress.emit(i + 1, total)

            self.finished.emit(images)

        except Exception as e:
            self.error.emit(str(e))
