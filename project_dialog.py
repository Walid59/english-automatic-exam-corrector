# projectDialog.py
import csv
import json
import os
import shutil
from os.path import join, basename, splitext, isdir, dirname, isfile, exists

import cv2
from PySide6 import QtWidgets as w, QtGui, QtCore, QtWidgets
from PySide6.QtCore import QThread

import \
    fitz  # conversion pdf vers image (meilleur que pdf2image : + opti MAIS quand même trop lent -> chercher une solution d'opti plus tard.)

from alignment import align_using_features, extract_blocks
from image_dialog import ImageViewerDialog
from pdf_manager import PDFConversionManager
from manual_review_dialog import ManualReviewDialog
from meta_updater import update_score_in_meta
import circle_manager as cm
from train_circle_classifier import filter_relative_winner
from stats import StatsDialog

import joblib
import unicodedata

model = joblib.load("circle_patch_classifier.joblib")

ACCENTS = ["ˆ", "°", "`", "´", "”", "~", "¸"]
LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
           "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "-", ","]

ACCENT_COMBINATIONS = {
    # ˆ
    ("ˆ", "A"): "Â", ("ˆ", "E"): "Ê", ("ˆ", "I"): "Î",
    ("ˆ", "O"): "Ô", ("ˆ", "U"): "Û",

    # °
    ("°", "A"): "Å",

    # ´
    ("´", "A"): "Á", ("´", "E"): "É", ("´", "I"): "Í",
    ("´", "O"): "Ó", ("´", "U"): "Ú",

    # Tréma ..
    ("”", "A"): "Ä", ("”", "E"): "Ë", ("”", "I"): "Ï",
    ("”", "O"): "Ö", ("”", "U"): "Ü", ("”", "Y"): "Ÿ",

    # Tilde ~
    ("~", "A"): "Ã", ("~", "N"): "Ñ", ("~", "O"): "Õ",

    # Cédille ¸
    ("¸", "C"): "Ç",

    # Accent grave `
    ("`", "A"): "À",
    ("`", "E"): "È",
    ("`", "U"): "Ù",
}


class ProjectDialog(w.QDialog):
    def __init__(self, project_name, project_path, parent=None):
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
        item = self.file_list.currentItem()
        if not item:
            return None
        name = item.text()
        for path in self.copy_data:
            if basename(path) == name:
                return path
        return None

    def open_image(self, item):
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
        self.file_list.clear()
        self.current_view_path = self.project_path

        for name in os.listdir(self.project_path):
            dir_path = join(self.project_path, name)
            if isdir(dir_path):
                item = w.QListWidgetItem(f"[Dossier] {name}")
                item.setData(QtCore.Qt.UserRole, dir_path)
                self.file_list.addItem(item)

    def display_files_in_directory(self, item):
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
            ext = splitext(selected_file)[1].lower()

            if ext == ".pdf":
                base_name = splitext(basename(selected_file))[0]

                self.thread = QThread()
                self.worker = PDFConversionManager(selected_file, self.project_path, base_name)
                self.worker.moveToThread(self.thread)

                self.worker.image_ready.connect(self.on_image_ready)
                self.worker.progress.connect(self.update_progress)
                self.worker.finished.connect(self.on_pdf_conversion_done)
                self.worker.error.connect(self.on_pdf_conversion_error)

                self.thread.started.connect(self.worker.run)
                self.worker.finished.connect(self.thread.quit)
                self.worker.finished.connect(self.worker.deleteLater)
                self.thread.finished.connect(self.thread.deleteLater)

                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(0)

                self.thread.start()
            else:
                path = join(self.project_path, basename(selected_file))
                shutil.copy(selected_file, path)
                self.process_image(path)

    def show_global_stats(self):
        dialog = StatsDialog(self.project_path, self)
        dialog.exec()

    def process_image(self, path):
        self.douteux = {}
        print("-----------------------------------------------------------------------------")
        print("DEBUT DU TRAITEMENT D'IMAGE")
        print("fichier: " + path)

        copy_dir, aligned, base_name, ext = self._prepare_and_align_image(path)
        name_path, qst_path = self._extract_and_save_blocks(aligned, copy_dir, base_name, ext)

        self._process_name_block(name_path, base_name, copy_dir)
        self._process_question_block(qst_path, copy_dir)

        if hasattr(self, "douteux") and self.douteux:
            print(f"[INFO] Questions douteuses détectées : ouverture automatique de la révision")
            self.open_review_dialog(qst_path)

        new_dir = self._rename_copy_folder_from_meta(copy_dir)
        if new_dir:
            copy_dir = new_dir
        final_name = os.path.basename(copy_dir)
        item = QtWidgets.QListWidgetItem(f"[Dossier] {final_name}")
        item.setData(QtCore.Qt.UserRole, copy_dir)
        self.file_list.addItem(item)
        print("FIN DU TRAITEMENT D'IMAGE")
        print("-----------------------------------------------------------------------------")

    def _prepare_and_align_image(self, path):
        project_dir = dirname(path)
        existing = [f for f in os.listdir(project_dir) if f.startswith("copy_") and isdir(join(project_dir, f))]
        index = len(existing) + 1
        copy_dir = join(project_dir, f"copy_{index}")
        os.makedirs(copy_dir, exist_ok=True)

        base, ext = splitext(path)
        base_name = basename(base)

        img = cv2.imread(path)
        template = self.template

        aligned, ok = align_using_features(img, template)
        if not ok:
            print("[INFO] Alignement échoué, image laissée telle quelle")
            aligned = img

        new_path = join(copy_dir, basename(path))
        cv2.imwrite(new_path, aligned)
        print("[INFO] Alignement réussi")

        return copy_dir, aligned, base_name, ext

    def _extract_and_save_blocks(self, aligned, copy_dir, base_name, ext):
        img_name, img_questions = extract_blocks(aligned)

        name_path = join(copy_dir, base_name + "_name" + ext)
        qst_path = join(copy_dir, base_name + "_questions" + ext)

        clean_name_path = join(copy_dir, base_name + "_name_clean" + ext)
        clean_qst_path = join(copy_dir, base_name + "_questions_clean" + ext)

        cv2.imwrite(name_path, img_name)
        cv2.imwrite(qst_path, img_questions)
        cv2.imwrite(clean_name_path, img_name)
        cv2.imwrite(clean_qst_path, img_questions)

        print("Separation des 2 blocs OK")
        return name_path, qst_path

    def _process_name_block(self, name_path, base_name, copy_dir):
        try:
            img_name = cv2.imread(name_path)
            centers = cm.detect_and_align_circles(img_name)
            gray_name = cv2.cvtColor(img_name, cv2.COLOR_BGR2GRAY)

            filled = []
            for (x, y) in centers:
                patch = gray_name[y - 15:y + 15, x - 15:x + 15]
                filled.append(
                    model.predict_proba(patch.reshape(1, -1))[0, 1] > 0.5 if patch.shape == (30, 30) else False)

            try:
                col_x, y_lines = cm.recentre_colonnes_nom_prenom(centers)
                filled_triplets = [(x, y, int(f)) for (x, y), f in zip(centers, filled)]
                nom = ""

                for x_ref in col_x:
                    col_circles = [(x, y) for (x, y, v) in filled_triplets if v and abs(x - x_ref) < 10]
                    if not col_circles:
                        nom += " "
                        continue

                    acc_idx = next((j for j in range(7) if
                                    j < len(y_lines) and any(abs(yc - y_lines[j]) < 5 for _, yc in col_circles)), -1)
                    let_idx = next((j - 7 for j in range(7, 35) if
                                    j < len(y_lines) and any(abs(yc - y_lines[j]) < 5 for _, yc in col_circles)), -1)

                    if let_idx != -1:
                        char = LETTERS[let_idx]
                        accent = ACCENTS[acc_idx] if acc_idx != -1 else ""
                        nom += ACCENT_COMBINATIONS.get((accent, char), accent + char)
                    else:
                        nom += " "

                nom = " ".join(nom.strip().split())
                print(f"[INFO] Nom détecté : « {nom} »")

                meta_path = os.path.join(copy_dir, "meta.json")
                data = {}
                if os.path.exists(meta_path):
                    with open(meta_path, "r") as f:
                        data = json.load(f)
                data["nom"] = nom
                with open(meta_path, "w") as f:
                    json.dump(data, f, indent=2)

            except Exception as e:
                print(f"[ERREUR] détection nom/prénom : {e}")

            cm.trace_circles(img_name, centers, filled, name_path, douteux_centers=[])

        except Exception as e:
            print(f" Erreur détection cercles (haut) : {e}")

    def _process_question_block(self, qst_path, copy_dir):
        try:
            img_questions = cv2.imread(qst_path)
            centers = cm.detect_and_align_circles(img_questions)
            gray_questions = cv2.cvtColor(img_questions, cv2.COLOR_BGR2GRAY)

            probas = []
            for (x, y) in centers:
                patch = gray_questions[y - 15:y + 15, x - 15:x + 15]
                probas.append(model.predict_proba(patch.reshape(1, -1))[0, 1] if patch.shape == (30, 30) else 0.0)

            # Construction grille
            nb_rows, nb_cols = 25, 8
            grid_scores = [[[] for _ in range(nb_cols)] for _ in range(nb_rows)]
            grid_centers = [[[] for _ in range(nb_cols)] for _ in range(nb_rows)]
            for i in range(0, len(probas), 4):
                row, col = (i // 4) // nb_cols, (i // 4) % nb_cols
                grid_scores[row][col] = probas[i:i + 4]
                grid_centers[row][col] = centers[i:i + 4]

            centers_sorted, filled, question_to_index = [], [], {}
            for col in range(nb_cols):
                for row in range(nb_rows):
                    question_number = col * nb_rows + row + 1
                    scores = grid_scores[row][col]
                    cts = grid_centers[row][col]
                    if len(scores) != 4 or len(cts) != 4:
                        print(f"[WARN] Q{question_number} ignorée (groupe incomplet)")
                        continue
                    result = filter_relative_winner(scores, margin=0.2, question_number=question_number, parent=self)
                    question_to_index[question_number] = len(centers_sorted)
                    filled += result if sum(result) else [False] * 4
                    centers_sorted.extend(cts)

            if len(filled) != len(centers_sorted):
                raise ValueError("probleme entre le nombre de cercles et les scores")

            print(f"[INFO] Cercles détectés : {len(centers_sorted)} — remplis : {sum(filled)}")

            douteux_centers = []
            if hasattr(self, "douteux") and self.douteux:
                for q in self.douteux:
                    start_idx = question_to_index.get(q)
                    if start_idx is not None:
                        douteux_centers.extend(
                            [(int(pt[0]), int(pt[1])) for pt in centers_sorted[start_idx:start_idx + 4]])

            meta_path = os.path.join(dirname(qst_path), "meta.json")

            # Charger les données si le projet existe
            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    existing = json.load(f)
            else:
                existing = {}

            # pareil pour les questions
            existing.update({
                "image": qst_path,
                "filled": filled,
                "centers": [list(map(int, pt)) for pt in centers_sorted],
                "douteux": self.douteux if hasattr(self, "douteux") else {}
            })

            with open(meta_path, "w") as f:
                json.dump(existing, f, indent=2)

            correction_path = os.path.join(self.project_path, "toeic_correction.csv")
            if os.path.exists(correction_path):
                update_score_in_meta(meta_path, filled, correction_path)
                print(f"[INFO] Scores mis à jour dans meta.json.")
            else:
                print(f"[WARN] Fichier toeic_correction.csv introuvable dans le projet.")

            cm.trace_circles(img_questions, centers_sorted, filled, qst_path, douteux_centers=douteux_centers)

            self.last_questions_image = qst_path
            self.last_centers = centers_sorted
            self.last_filled = filled
            self.copy_data[qst_path] = {
                "image": qst_path,
                "centers": centers_sorted,
                "filled": filled
            }

        except Exception as e:
            print(f" Erreur détection cercles (bas) : {e}")

    def _rename_copy_folder_from_meta(self, copy_dir):
        meta_path = os.path.join(copy_dir, "meta.json")
        if not os.path.exists(meta_path):
            return

        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            nom = meta.get("nom", "").strip()
            if not nom:
                return

            # Normalisation du nom
            nom_norm = unicodedata.normalize("NFKD", nom)
            nom_ascii = ''.join(c for c in nom_norm if not unicodedata.combining(c))
            nom_clean = nom_ascii.title().replace(" ", "_")

            # renommage
            new_dir = os.path.join(os.path.dirname(copy_dir), nom_clean)

            if new_dir == copy_dir:
                return

            if os.path.exists(new_dir):
                print(f"[WARN] Le dossier {new_dir} existe déjà, renommage annulé.")
                return

            try:
                os.rename(copy_dir, new_dir)
                print(f"[INFO] Dossier renommé avec succès : {new_dir}")
            except PermissionError:
                print(f"[WARN] os.rename échoué (PermissionError). Tentative de copie...")

                shutil.copytree(copy_dir, new_dir)
                shutil.rmtree(copy_dir)
                print(f"[INFO] Dossier copié puis supprimé : {new_dir}")

            return new_dir
        except Exception as e:
            print(f"[ERREUR] Impossible de renommer le dossier : {e}")

    def addItem(self, path):
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
        self.process_image(path)

    def on_pdf_conversion_done(self, image_paths):
        self.progress_bar.setVisible(False)
        print(f"PDF converti : {len(image_paths)} pages → images")
        self.refresh_file_list()

    def on_pdf_conversion_error(self, message):
        self.progress_bar.setVisible(False)
        w.QMessageBox.critical(self, "Erreur de conversion", message)

    def update_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def handle_item_double_click(self, item):
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


def convert_pdf_to_images(pdf_path, output_folder, base_name="page"):
    doc = fitz.open(pdf_path)
    image_paths = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # résolution 2x
        output_path = join(output_folder, f"{base_name}_{i + 1}.png")
        pix.save(output_path)
        image_paths.append(output_path)
    return image_paths