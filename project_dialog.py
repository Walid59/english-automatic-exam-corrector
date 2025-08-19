# projectDialog.py
import csv
import json
import os
import sys
import shutil
from os.path import join, basename, splitext, isdir, dirname, isfile, exists

import cv2
from PySide6 import QtWidgets as w, QtGui, QtCore, QtWidgets
from PySide6.QtCore import QThread

from image_dialog import ImageViewerDialog
from image_worker import ImageProcessingWorker
from pdf_manager import PDFConversionManager
from manual_review_dialog import ManualReviewDialog
from meta_updater import update_score_in_meta
import circle_manager as cm
from stats import StatsDialog


class ProjectDialog(w.QDialog):
    def __init__(self, project_name, project_path, parent=None):
        """
        Itinializes project dialog.
        :param project_name: name of the project
        :param project_path: path of the project
        :param parent: parent
        """
        self.image_jobs = {}   # {path: (thread, worker)}
        self.pdf_thread = None
        self.pdf_worker = None
        self.image_threads = []   # pour conserver des refs jusqu’au cleanup

        super().__init__(parent)
        self.template = cv2.imread("resources/templates/Answer_sheet.jpg")

        self.project_name = project_name
        self.project_path = project_path
        self.setWindowTitle(f"Exam : {project_name}")
        self.setFixedSize(600, 400)

        self.current_view_path = self.project_path
        self.copy_data = {}
        self.initUI()

    def initUI(self):
        """
        set up graphical interface
        :return:
        """
        layout = w.QVBoxLayout(self)

        self.add_file_btn = w.QPushButton("add a student copy")
        self.add_file_btn.clicked.connect(self.add_copy_to_project)

        self.global_stats_btn = w.QPushButton("Statistiques globales")
        self.global_stats_btn.clicked.connect(self.show_global_stats)

        self.file_list = w.QListWidget()
        self.file_list.itemDoubleClicked.connect(self.handle_item_double_click)

        self.progress_bar = w.QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)

        self.stats_display = QtWidgets.QTextEdit()
        self.stats_display.setReadOnly(True)
        self.stats_display.setFixedHeight(130)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        file_zone = QtWidgets.QWidget()
        file_layout = QtWidgets.QVBoxLayout(file_zone)
        file_layout.addWidget(self.add_file_btn)
        file_layout.addWidget(self.global_stats_btn)
        file_layout.addWidget(self.file_list)
        file_layout.addWidget(self.progress_bar)
        file_layout.setContentsMargins(0, 0, 0, 0)

        splitter.addWidget(file_zone)
        splitter.addWidget(self.stats_display)
        self.stats_display.setVisible(False)

        layout.addWidget(splitter)

        self.load_existing_copies()

    def open_review_dialog(self, path=None):
        """
        Open the manual review dialog for a selected student copy
        :param path:
        :return:
        """
        if path is None:
            path = self.get_selected_image_path()

        if not path or path not in self.copy_data:
            QtWidgets.QMessageBox.warning(self, "Révision manuelle", "Veuillez sélectionner une copie valide.")
            return

        data = self.copy_data[path]
        filled = data["filled"]
        centers = data["centers"]
        image_path = data["image"]

        if len(filled) != len(centers):
            print(f"[FATAL] filled = {len(filled)}, centers = {len(centers)}")
            raise ValueError("filled et centers ont des tailles différentes")

        dialog = ManualReviewDialog(image_path, filled, centers, self)
        if dialog.exec_():
            data["filled"] = dialog.final_filled
            # Recalcul des doutes restants (uniquement pour les questions non modifiées)
            douteux_centers = []
            if hasattr(self, "douteux") and self.douteux:
                question_to_index = {q: q * 4 for q in range(len(centers) // 4)}
                for q in self.douteux.copy():
                    if q in dialog.modified_questions:
                        self.douteux.pop(q, None)
                    elif q in question_to_index:
                        start_idx = question_to_index[q]
                        douteux_centers += [(int(pt[0]), int(pt[1])) for pt in centers[start_idx:start_idx + 4]]

            clean_path = image_path.replace("_questions", "_questions_clean")
            if not os.path.exists(clean_path):
                print("[WARN] Image _clean non trouvée, fallback vers originale")
                clean_path = image_path

            img_clean = cv2.imread(clean_path)
            cm.trace_circles(
                img_clean,
                centers,
                dialog.final_filled,
                image_path,
                modified_questions=dialog.modified_questions,
                douteux_centers=[]
            )

            self.copy_data[path] = data

            # Mise à jour de meta.json
            meta_path = os.path.join(os.path.dirname(path), "meta.json")
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                meta["filled"] = data["filled"]
                meta["douteux"] = self.douteux
                with open(meta_path, "w") as f:
                    json.dump(meta, f, indent=2)
                print(f"[INFO] meta.json mis à jour après révision.")

                # Mise à jour du score brut après révision manuelle
                correction_path = os.path.join(self.project_path, "toeic_correction.csv")
                if os.path.exists(correction_path):
                    update_score_in_meta(meta_path, data["filled"], correction_path)
                    print(f"[INFO] Scores détaillés mis à jour dans meta.json.")

                    # affichage dynamique
                    self.display_stats(path)
                else:
                    print(f"[WARN] Fichier toeic_correction.csv introuvable dans le projet.")

            except Exception as e:
                print(f"[ERREUR] Mise à jour meta.json : {e}")

    def get_selected_image_path(self):
        """
        Return the file path corresponding to the currently selected item in the list
        :return:
        """
        item = self.file_list.currentItem()
        if not item:
            return None
        name = item.text()
        for path in self.copy_data:
            if basename(path) == name:
                return path
        return None

    def open_image(self, item):
        """
        Open an image in a viewer dialog when a list item is double-clicked
        :param item:
        :return:
        """
        path = item.data(QtCore.Qt.UserRole)
        print(f"[DEBUG] Tentative d'ouverture : {path}")

        if not path or not isfile(path):
            print("[DEBUG] Fichier introuvable ou invalide.")
            QtWidgets.QMessageBox.warning(self, "Erreur", "Fichier introuvable.")
            return

        pixmap = QtGui.QPixmap(path)
        if pixmap.isNull():
            print("[DEBUG] QPixmap a échoué à charger l'image.")
            QtWidgets.QMessageBox.warning(self, "Erreur", "Impossible d'ouvrir l'image.")
            return

        viewer = ImageViewerDialog(pixmap, basename(path), self)
        viewer.exec()

    def load_existing_copies(self):
        """
        load and display all subdirectories
        """
        self.file_list.clear()
        self.current_view_path = self.project_path

        for name in os.listdir(self.project_path):
            dir_path = join(self.project_path, name)
            if isdir(dir_path):
                item = w.QListWidgetItem(f"[Dossier] {name}")
                item.setData(QtCore.Qt.UserRole, dir_path)
                self.file_list.addItem(item)

    def display_files_in_directory(self, item):
        """
        show all files in directory
        :param item:
        :return:
        """
        if not item.text().startswith("[Dossier] "):
            return

        folder_name = item.text().replace("[Dossier] ", "")
        folder_path = join(self.project_path, folder_name)
        self.file_list.clear()

        # Bouton retour
        back_item = w.QListWidgetItem("⬅️ Retour")
        back_item.setData(QtCore.Qt.UserRole, self.project_path)
        self.file_list.addItem(back_item)

        selected_stats_file = None  # pour afficher les stats plus bas

        for file in os.listdir(folder_path):
            if not file.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            full_path = join(folder_path, file)
            meta_path = join(folder_path, "meta.json")

            # Charger les données si "_questions" présent
            if "_questions" in file.lower() and exists(meta_path):
                selected_stats_file = full_path  # <- on garde le fichier avec stats
                try:
                    with open(meta_path, "r") as f:
                        data = json.load(f)
                    self.copy_data[full_path] = {
                        "image": full_path,
                        "filled": data["filled"],
                        "centers": data["centers"]
                    }
                    self.douteux = data.get("douteux", {})
                except Exception as e:
                    print(f"[ERREUR] Chargement meta.json : {e}")

            self.addItem(full_path)

        if selected_stats_file:
            self.display_stats(selected_stats_file)
        else:
            self.stats_display.setVisible(False)

    def refresh_file_list(self):
        """
        Refresh the list of images in project folder
        :return:
        """
        self.file_list.clear()
        for file in os.listdir(self.project_path):
            if file.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                self.file_list.addItem(file)

    def add_copy_to_project(self):
        """
        Open file dialog to import pdf or image to the project
        uses pdf conversion if necessary
        :return:
        """
        dialog = w.QFileDialog(self)
        dialog.setNameFilter("PDF or Images (*.pdf *.png *.jpg *.jpeg)")
        dialog.setFileMode(w.QFileDialog.FileMode.ExistingFile)

        if dialog.exec():
            selected_file = dialog.selectedFiles()[0]
            ext = splitext(selected_file)[1].lower()

            if ext == ".pdf":
                base_name = splitext(basename(selected_file))[0]

                self.pdf_thread = QThread(self)
                self.pdf_worker = PDFConversionManager(selected_file, self.project_path, base_name)
                self.pdf_worker.moveToThread(self.pdf_thread)

                self.pdf_worker.image_ready.connect(self.on_image_ready)
                self.pdf_worker.progress.connect(self.update_progress)
                self.pdf_worker.finished.connect(self.on_pdf_conversion_done)
                self.pdf_worker.error.connect(self.on_pdf_conversion_error)

                self.pdf_worker.finished.connect(self.pdf_thread.quit)

                self.pdf_thread.finished.connect(self.pdf_worker.deleteLater)
                self.pdf_thread.finished.connect(self.pdf_thread.deleteLater)

                self.pdf_thread.started.connect(self.pdf_worker.run)

                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(0)
                self.pdf_thread.start()

            else:
                path = join(self.project_path, basename(selected_file))
                shutil.copy(selected_file, path)
                self.process_image(path)

    def show_global_stats(self):
        """
        Open dialog window showing global statistics of students marks
        :return:
        """
        dialog = StatsDialog(self.project_path, self)
        dialog.exec()

    def start_image_processing(self, path):
        print("[PD] start_image_processing", path)
        thread = QThread(self)
        worker = ImageProcessingWorker(path, self.template, self.project_path)
        worker.moveToThread(thread)

        # Brancher les signaux AVANT de démarrer
        worker.progress.connect(self.update_progress)
        worker.processed.connect(self.on_image_processed)
        worker.needManualReview.connect(self.on_need_manual_review)
        worker.error.connect(self.on_image_error)

        thread.started.connect(worker.run)
        # Arrêt du thread sur fin OU erreur
        worker.processed.connect(thread.quit)
        worker.error.connect(thread.quit)

        # Cleanup Qt
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # ✅ Garder des références Python vivantes
        self.image_jobs[path] = (thread, worker)

        # Nettoyage de notre registre quand le thread a fini
        def _cleanup():
            self.image_jobs.pop(path, None)
        thread.finished.connect(_cleanup)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        print("[PD] thread.start() (image)")
        thread.start()

            
      
    def on_image_processed(self, result: dict):
        # Mise à jour des données
        path = result["image"]
        self.copy_data[path] = {
            "image": result["image"],
            "filled": result["filled"],
            "centers": result["centers"]
        }
        self.douteux = result["douteux"]

        # Ajout dans la liste UI
        copy_dir = result["copy_dir"]
        final_name = os.path.basename(copy_dir)
        item = QtWidgets.QListWidgetItem(f"[Dossier] {final_name}")
        item.setData(QtCore.Qt.UserRole, copy_dir)
        self.file_list.addItem(item)

        self.progress_bar.setVisible(False)

    def on_need_manual_review(self, path, douteux):
        self.douteux = douteux
        self.open_review_dialog(path)

    def on_image_error(self, msg):
        self.progress_bar.setVisible(False)
        QtWidgets.QMessageBox.critical(self, "Erreur traitement", msg)

    def process_image(self, path):
        self.start_image_processing(path)


    def addItem(self, path):
        """
        Adds an item to list display
        (only adds one element contrary to refreshfromlist who completely refresh list)
        """
        name = basename(path)
        if self.file_list.findItems(name, QtCore.Qt.MatchExactly):
            return

        item = w.QListWidgetItem(name)
        item.setData(QtCore.Qt.UserRole, path)
        self.file_list.addItem(item)

        widget = None
        layout = None

        if path in self.copy_data and "_questions" in os.path.basename(
                path).lower() and "_questions_clean" not in os.path.basename(path).lower():
            btn = QtWidgets.QPushButton("Edit...")
            btn.clicked.connect(lambda _, p=path: self.open_review_dialog(p))
            widget = w.QWidget()
            layout = w.QHBoxLayout(widget)
            layout.addWidget(w.QLabel(name))
            layout.addWidget(btn)

        # Si c’est un fichier _name (mais pas _name_clean) → bouton Corriger nom, pareil avec _questions
        if "_name" in name.lower() and "_name_clean" not in name.lower():
            if widget is None:
                widget = w.QWidget()
                layout = w.QHBoxLayout(widget)
                layout.addWidget(w.QLabel(name))

            edit_btn = QtWidgets.QPushButton("Correct full name")
            edit_btn.clicked.connect(lambda _, p=path: self.edit_student_name(p))
            layout.addWidget(edit_btn)

        if widget:
            layout.setContentsMargins(0, 0, 0, 0)
            widget.setLayout(layout)
            item.setSizeHint(widget.sizeHint())
            self.file_list.setItemWidget(item, widget)

    def edit_student_name(self, path):
        """
        Edits student's name and updates in metadata
        :param path:
        :return:
        """
        meta_path = os.path.join(os.path.dirname(path), "meta.json")
        if not os.path.exists(meta_path):
            QtWidgets.QMessageBox.warning(self, "Erreur", "Fichier meta.json introuvable.")
            return

        with open(meta_path, "r") as f:
            meta = json.load(f)
        current_name = meta.get("nom", "")

        text, ok = QtWidgets.QInputDialog.getText(self, "Corriger le nom", "Nom de l'élève :", text=current_name)
        if ok and text.strip():
            meta["nom"] = text.strip()
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
            print(f"[INFO] Nom mis à jour : {text.strip()}")
            self.display_stats(path)

    def on_image_ready(self, path):
        """
        function triggered when a converted image is ready
        Callback
        """
        print(f"[PD] on_image_ready: {path}")

        # ⚡ Lancer le même pipeline que pour une image classique
        self.process_image(path)

    def on_pdf_conversion_done(self, image_paths):
        print("[PD] on_pdf_conversion_done ENTER")
        try:
            self.progress_bar.setVisible(False)
            print(f"[PD] pages converted: {len(image_paths)}")

        finally:
            if self.pdf_thread and self.pdf_thread.isRunning():
                self.pdf_thread.quit()
                self.pdf_thread.wait()
            self.pdf_thread = None
            self.pdf_worker = None
            print("[PD] on_pdf_conversion_done EXIT")



    def on_pdf_conversion_error(self, message):
        print("[PD] on_pdf_conversion_error ENTER")
        self.progress_bar.setVisible(False)
        print("[PD] ERROR MESSAGE:", message)
        w.QMessageBox.critical(self, "Erreur de conversion", message)
        print("[PD] on_pdf_conversion_error EXIT")

    def update_progress(self, current, total):
        """
        Update progress bar during operation
        """
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def handle_item_double_click(self, item):
        """
        Double click event for list items
        :param item:
        :return:
        """
        path = item.data(QtCore.Qt.UserRole)

        if item.text().startswith("⬅️"):
            self.stats_display.setVisible(False)
            self.load_existing_copies()
            return

        # Si c’est un dossier on peut y aller
        if isdir(path):
            self.display_files_in_directory(item)
            return

        # Si c’est une image on peut la voir
        self.open_image(item)

        if "_questions" in os.path.basename(path).lower():
            self.display_stats(path)
        else:
            self.stats_display.setVisible(False)

    def display_stats(self, path):
        """
        Display statistics for a selected student based on metadata.
        :param path:
        :return:
        """
        meta_path = os.path.join(os.path.dirname(path), "meta.json")
        if not os.path.exists(meta_path):
            self.stats_display.setPlainText("Aucune donnée de score disponible.")
            return

        with open(meta_path, "r") as f:
            meta = json.load(f)

        nom = meta.get("nom", "Nom inconnu")
        listening = meta.get("listening", 0)
        reading = meta.get("reading", 0)
        s_list = meta.get("scaled_listening", 0)
        s_read = meta.get("scaled_reading", 0)
        s_total = meta.get("scaled_total", 0)
        sub = meta.get("subparts", {})

        # mapping noms catégories
        sub_names = {
            "part1": "Photographs",
            "part2": "Question-Response",
            "part3": "Conversations",
            "part4": "Short Talks",
            "part5": "Incomplete Sentences",
            "part6": "Text Completion",
            "part7": "Reading Comprehension"
        }

        text = f"""👤 Élève : {nom}

    🎧 Listening: {listening}/100  (→ {s_list}/495)
    📖 Reading: {reading}/100  (→ {s_read}/495)
    📊 Total TOEIC estimé : {s_total}/990

    📂 Détail par section :
    """
        for key in [f"part{i}" for i in range(1, 8)]:
            label = sub_names.get(key, key)
            score = sub.get(key, 0)
            text += f"   - {label}: {score}\n"

        self.stats_display.setPlainText(text)
        self.stats_display.setVisible(True)


def compute_raw_score(filled, correction_path, options=None):
    """
    Compute the raw score from filled responses using a correction file

    :param filled:
    :param correction_path:
    :param options:
    :return:
    """
    if options is None:
        options = {}

    try:
        with open(correction_path, newline='') as f:
            reader = csv.reader(f)
            corrections = [(int(row[0]), row[1].strip().upper()) for row in reader]

        total_questions = len(corrections)
        choices_per_question = options.get("choices_per_question", 4)
        letter_to_index = {chr(65 + i): i for i in range(choices_per_question)}

        expected_length = total_questions * choices_per_question
        if len(filled) != expected_length:
            print(f"[WARN] filled contient {len(filled)} cases, mais {expected_length} sont attendues.")

        score = 0
        for i, (q_num, correct_letter) in enumerate(corrections):
            start = i * choices_per_question
            end = start + choices_per_question
            response = filled[start:end]

            if len(response) != choices_per_question:
                continue  # Données incomplètes, on saute

            if response.count(True) == 1:
                selected = response.index(True)
                if selected == letter_to_index.get(correct_letter):
                    score += 1

        return score

    except Exception as e:
        print(f"[ERREUR] Lecture du fichier de correction ou calcul du score : {e}")
        return None
