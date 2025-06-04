from PySide6.QtCore import Signal, QObject
import fitz
import os

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

    def run(self):
        try:
            doc = fitz.open(self.pdf_path)
            total = len(doc)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                out_path = os.path.join(self.output_folder, f"{self.base_name}_{i + 1}.png")
                pix.save(out_path)

                self.image_ready.emit(out_path)
                self.progress.emit(i + 1, total)

            self.finished.emit([])
        except Exception as e:
            self.error.emit(str(e))