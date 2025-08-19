from PySide6.QtCore import Signal, QObject
import os, traceback
import fitz  # PyMuPDF

class PDFConversionManager(QObject):
    image_ready = Signal(str)
    progress = Signal(int, int)
    finished = Signal(object)   # object pour éviter tout souci
    error = Signal(str)

    def __init__(self, pdf_path, output_folder, base_name):
        super().__init__()
        self.pdf_path = pdf_path
        self.output_folder = output_folder
        self.base_name = base_name

    def run(self):
        try:
            print("[PDF] run() START")
            print(f"[PDF] pdf_path={self.pdf_path}")
            os.makedirs(self.output_folder, exist_ok=True)
            print(f"[PDF] output_folder OK: {self.output_folder}")

            print("[PDF] fitz.open ...")
            doc = fitz.open(self.pdf_path)
            total = len(doc)
            print(f"[PDF] DOC OPENED, pages={total}")

            images = []
            for i, page in enumerate(doc):
                print(f"[PDF] render page {i+1}/{total}")
                pix = page.get_pixmap(matrix=fitz.Matrix(4.5, 4.5))
                img_path = os.path.join(self.output_folder, f"{self.base_name}_{i+1}.jpg")
                pix.save(img_path, "jpeg")
                print(f"[PDF] saved: {img_path}")
                images.append(img_path)

                print(f"[PDF] emit image_ready: {img_path}")
                self.image_ready.emit(img_path)
                print(f"[PDF] emit progress: {i+1}/{total}")
                self.progress.emit(i + 1, total)

            # Fermer le doc si la méthode existe (compat)
            if hasattr(doc, "close"):
                print("[PDF] doc.close() ...")
                doc.close()
                print("[PDF] doc.close() DONE")
            else:
                print("[PDF] doc.close() NOT AVAILABLE (ok)")

            print("[PDF] emit finished (about to)")
            self.finished.emit(images)
            print("[PDF] emit finished DONE")
        except Exception as e:
            tb = traceback.format_exc()
            print("[PDF][ERROR]", tb)
            self.error.emit(f"{e}\n\n{tb}")
