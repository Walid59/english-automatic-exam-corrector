import shutil
import unicodedata
import cv2
import json
import circle_manager as cm
import sys
from os import listdir, makedirs, rename
from os.path import dirname, isdir, join, splitext, basename, exists, abspath
from PySide6.QtCore import QObject, Signal
from alignment import align_using_features, extract_blocks
from meta_updater import update_score_in_meta
from train_circle_classifier import filter_relative_winner
from constants import ACCENT_COMBINATIONS, ACCENTS, LETTERS
import traceback

from joblib import load

def resource_path(relative_path: str) -> str:
    """Retourne le chemin absolu vers une ressource embarquée
    compatible dev (fichiers à côté du code) et PyInstaller (--onefile or folder)."""
    if getattr(sys, 'frozen', False):
        # quand PyInstaller gèle (--onefile et --onedir)
        base = getattr(sys, '_MEIPASS', dirname(sys.executable))
    else:
        base = abspath(dirname(__file__))
    return join(base, relative_path)

model_path = resource_path("circle_patch_classifier.joblib")
model = load(model_path)

class ImageProcessingWorker(QObject):
    progress = Signal(int, int)
    processed = Signal(dict)
    needManualReview = Signal(str, dict)
    error = Signal(str)
    
    def __init__(self, path, template, project_path):
        super().__init__()
        self.path = path
        self.template = template
        self.project_path = project_path
        self.douteux = {}

    def run(self):
        try:
            print(f"[Worker] START run() for {self.path}")
            result = self._process_image(self.path)
            self.processed.emit(result)
            if result.get("douteux"): 
                self.needManualReview.emit(result["image"], result["douteux"])
        except Exception as e:
            print("[Worker] CRASH", e)
            traceback.print_exc()
            self.error.emit(str(e))


    def _process_image(self, path: str) -> dict:
        self.douteux = {}
        # (1) Alignement / préparation
        copy_dir, aligned, base_name, ext = self._prepare_and_align_image(path)

        # (2) Extraction des blocs
        name_path, qst_path = self._extract_and_save_blocks(aligned, copy_dir, base_name, ext)

        # (3) Traitement du nom (écrit la meta si c'est ce que fait ton code)
        self._process_name_block(name_path, base_name, copy_dir)

        # (4) Traitement questions → retourne (centers, filled, douteux)
        centers, filled, douteux = self._process_question_block(qst_path, copy_dir)

        # (6) Renommer le dossier selon meta (I/O pur → OK en worker)
        new_dir = self._rename_copy_folder_from_meta(copy_dir)
        if new_dir:
            copy_dir = new_dir

        # (7) Renvoyer des **données pures** à l’UI
        return {
            "copy_dir": copy_dir,       # dossier final (évent. renommé)
            "image": qst_path,          # chemin du bloc questions
            "centers": centers,         # données pour mise à jour self.copy_data
            "filled": filled,
            "douteux": douteux,         # pour garder la trace côté UI si tu veux
        }
    
    def _prepare_and_align_image(self, path):
        """
        Align the copy with template and stores aligned image
        """
        project_dir = dirname(path)
        existing = [f for f in listdir(project_dir) if f.startswith("copy_") and isdir(join(project_dir, f))]
        index = len(existing) + 1
        copy_dir = join(project_dir, f"copy_{index}")
        makedirs(copy_dir, exist_ok=True)

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
        """
        Extract and save the name and question blocks
        :param aligned:
        :param copy_dir:
        :param base_name:
        :param ext:
        :return:
        """
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
        """
        Name detection from name block and adds it/updates to metadata

        :param name_path:
        :param base_name:
        :param copy_dir:
        :return:
        """
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

                meta_path = join(copy_dir, "meta.json")
                data = {}
                if exists(meta_path):
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
        """
        Question detection from name block and adds it/updates to metadata

        :param name_path:
        :param base_name:
        :param copy_dir:
        :return:
        """
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


            meta_path = join(dirname(qst_path), "meta.json")

            # Charger les données si le projet existe
            if exists(meta_path):
                with open(meta_path, "r") as f:
                    existing = json.load(f)
            else:
                existing = {}

            # pareil pour les questions
            existing.update({
                "image": qst_path,
                "filled": filled,
                "centers": [list(map(int, pt)) for pt in centers_sorted],
                "douteux": {}
            })

            with open(meta_path, "w") as f:
                json.dump(existing, f, indent=2)

            correction_path = join(self.project_path, "toeic_correction.csv")
            if exists(correction_path):
                update_score_in_meta(meta_path, filled, correction_path)
                print(f"[INFO] Scores mis à jour dans meta.json.")
            else:
                print(f"[WARN] Fichier toeic_correction.csv introuvable dans le projet.")
                
            
            douteux_centers = []
            if hasattr(self, "douteux") and self.douteux:
                for q in self.douteux:
                    start_idx = question_to_index.get(q)
                    if start_idx is not None:
                        douteux_centers.extend(
                            [(int(pt[0]), int(pt[1])) for pt in centers_sorted[start_idx:start_idx + 4]]
                        )
            cm.trace_circles(img_questions, centers_sorted, filled, qst_path, douteux_centers=douteux_centers)

        except Exception as e:
            print(f" Erreur détection cercles (bas) : {e}")
        
        return centers_sorted, filled, self.douteux
    
    def _rename_copy_folder_from_meta(self, copy_dir):
        """
        Rename student copy directory on creation using name in metadata
        :param copy_dir:
        :return:
        """
        meta_path = join(copy_dir, "meta.json")
        if not exists(meta_path):
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
            new_dir = join(dirname(copy_dir), nom_clean)

            if new_dir == copy_dir:
                return

            if exists(new_dir):
                print(f"[WARN] Le dossier {new_dir} existe déjà, renommage annulé.")
                return

            try:
                rename(copy_dir, new_dir)
                print(f"[INFO] Dossier renommé avec succès : {new_dir}")
            except PermissionError:
                print(f"[WARN] os.rename échoué (PermissionError). Tentative de copie...")

                shutil.copytree(copy_dir, new_dir)
                shutil.rmtree(copy_dir)
                print(f"[INFO] Dossier copié puis supprimé : {new_dir}")

            return new_dir
        except Exception as e:
            print(f"[ERREUR] Impossible de renommer le dossier : {e}")
