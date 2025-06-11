import random
from collections import defaultdict

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.utils import resample
import joblib

import os
import cv2
import pytesseract
from tqdm import tqdm


# === EXTRACTION DES CASES (patch) ===
def save_patch(img, center, label, output_dir='dataset_patches', size=30):
    x, y = center
    r = size // 2
    patch = img[y - r:y + r, x - r:x + r]
    if patch.shape != (size, size):
        return
    label_dir = 'filled' if label else 'empty'
    out_dir = os.path.join(output_dir, label_dir)
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{label_dir}_{x}_{y}.png"
    cv2.imwrite(os.path.join(out_dir, filename), patch)


def extract_patches_from_image(img_gray, centers, labels, output_dir):
    for (x, y), is_filled in zip(centers, labels):
        save_patch(img_gray, (x, y), is_filled, output_dir=output_dir)


# === CHARGEMENT + ÉQUILIBRAGE DU DATASET ===

def load_balanced_dataset(base_path='dataset_patches', size=(30, 30), empty_multiplier=3):
    X_filled, y_filled = [], []
    X_empty, y_empty = [], []

    for fname in os.listdir(os.path.join(base_path, 'filled')):
        path = os.path.join(base_path, 'filled', fname)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None and img.shape == size:
            X_filled.append(img.flatten())
            y_filled.append(1)

    for fname in os.listdir(os.path.join(base_path, 'empty')):
        path = os.path.join(base_path, 'empty', fname)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None and img.shape == size:
            X_empty.append(img.flatten())
            y_empty.append(0)

    filled_count = len(X_filled)
    empty_count = min(len(X_empty), filled_count * empty_multiplier)

    X_empty_sampled, y_empty_sampled = resample(
        X_empty, y_empty,
        replace=False,
        n_samples=empty_count,
        random_state=42
    )

    # Fusionner les deux classes équilibrées
    X_all = np.array(X_filled + X_empty_sampled)
    y_all = np.array(y_filled + y_empty_sampled)

    print(f"[INFO] Dataset équilibré : {len(X_filled)} remplis, {len(X_empty_sampled)} vides")
    return train_test_split(X_all, y_all, test_size=0.2, random_state=42)


def predict_filled_patch(patch_30x30, model):
    """
    Prend un patch numpy (30x30, en niveaux de gris) et prédit s'il est rempli.
    Retourne un booléen : True = rempli, False = vide
    """
    if patch_30x30.shape != (30, 30):
        raise ValueError("Le patch doit être en 30x30 pixels")
    flat = patch_30x30.flatten().reshape(1, -1)
    return model.predict(flat)[0] == 1


# === ENTRAÎNEMENT ===

def train_random_forest(X_train, y_train, X_test, y_test, output_model='circle_patch_classifier.joblib'):
    model = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    print("\n=== Évaluation ===")
    print(classification_report(y_test, y_pred, digits=3))
    joblib.dump(model, output_model)
    print(f"[✔] Modèle sauvegardé dans : {output_model}")


def filter_empty_patches_by_ocr(input_dir='dataset_patches/empty',
                                output_dir='dataset_patches/empty_with_text',
                                patch_size=(30, 30),
                                lang='fra'):
    """
    Filtre les patchs `empty/` contenant un caractère détecté (lettre, symbole, accent, etc.)
    grâce à Tesseract OCR avec la langue `fra`.
    Copie les patchs détectés dans `output_dir`.
    """
    os.makedirs(output_dir, exist_ok=True)

    files = [f for f in os.listdir(input_dir) if f.lower().endswith(".png")]
    kept = 0

    for fname in tqdm(files, desc="OCR filtering"):
        path = os.path.join(input_dir, fname)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

        if img is None or img.shape != patch_size:
            continue

        # Config OCR : mode caractère unique, langue française (accents, symboles...)
        config = '--psm 10'
        try:
            text = pytesseract.image_to_string(img, config=config, lang=lang).strip()
        except pytesseract.TesseractError as e:
            print(f"[ERROR] OCR failed on {fname} : {e}")
            continue

        if text:  # au moins un caractère reconnu
            cv2.imwrite(os.path.join(output_dir, fname), img)
            kept += 1

    print(f"[INFO] {kept} patchs conservés sur {len(files)} (avec au moins un caractère OCR détecté)")


def balance_patch_by_ocr_char(input_dir='dataset_patches/empty',
                              output_dir='dataset_patches/empty_balanced_chars',
                              patch_size=(30, 30),
                              lang='fra',
                              max_chars=35):
    """
    Équilibre les patchs OCR par caractère détecté : autant de W que de Ç, etc.
    Conserve les noms de fichiers originaux (pour compatibilité Windows).
    """
    os.makedirs(output_dir, exist_ok=True)
    char_to_patches = defaultdict(list)

    files = [f for f in os.listdir(input_dir) if f.lower().endswith(".png")]

    for fname in tqdm(files, desc="OCR character grouping"):
        path = os.path.join(input_dir, fname)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None or img.shape != patch_size:
            continue

        config = '--psm 10'
        try:
            text = pytesseract.image_to_string(img, config=config, lang=lang).strip()
        except pytesseract.TesseractError:
            continue

        if len(text) == 1:
            char = text.upper()
            char_to_patches[char].append((fname, img))

    # Nombre cible par caractère
    total_available_chars = len(char_to_patches)
    total_patches = sum(len(v) for v in char_to_patches.values())
    patches_per_char = total_patches // total_available_chars

    kept_total = 0
    for char, samples in char_to_patches.items():
        if len(samples) >= patches_per_char:
            selected = random.sample(samples, patches_per_char)
        else:
            selected = samples  # trop peu, on garde tout
        for fname, img in selected:
            #  Ne plus inclure le caractère dans le nom
            save_path = os.path.join(output_dir, fname)
            cv2.imwrite(save_path, img)
            kept_total += 1

    print(f"[INFO] {kept_total} patchs équilibrés sauvegardés dans {output_dir}")
    print(f"[INFO] ≈ {patches_per_char} patchs par caractère sur {len(char_to_patches)} caractères")


def load_strict_dataset(base_path='dataset_patches',
                        filled_subfolder='filled',
                        empty_subfolder='empty_balanced_chars',
                        size=(30, 30),
                        test_size=0.2,
                        random_state=42):
    """
    Charge tous les patchs `filled` et tous les patchs `empty_balanced_chars`.
    Pas de sampling. Le dataset est équilibré par construction via OCR.
    """

    X, y = [], []

    for label, folder in [(1, filled_subfolder), (0, empty_subfolder)]:
        folder_path = os.path.join(base_path, folder)
        if not os.path.exists(folder_path):
            print(f"[WARNING] Dossier non trouvé : {folder_path}")
            continue

        for fname in os.listdir(folder_path):
            path = os.path.join(folder_path, fname)
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is not None and img.shape == size:
                X.append(img.flatten())
                y.append(label)

    X = np.array(X)
    y = np.array(y)

    print(f"[INFO] Chargement terminé : {np.sum(y == 1)} remplis — {np.sum(y == 0)} vides")
    return train_test_split(X, y, test_size=test_size, random_state=random_state)


def classify_question_by_difference(proba_list, min_margin=0.20):
    """
    proba_list : liste de 4 scores de proba (une question)
    min_margin : seuil minimum entre la meilleure proba et les autres
    Retourne une liste booléenne de 4 éléments, avec un seul True si validé.
    """
    if len(proba_list) != 4:
        raise ValueError("Chaque question doit avoir exactement 4 scores")

    max_idx = int(np.argmax(proba_list))
    max_val = proba_list[max_idx]
    others = [proba_list[i] for i in range(4) if i != max_idx]

    if all((max_val - v) > min_margin for v in others):
        return [i == max_idx for i in range(4)]  # une seule case True
    else:
        return [False] * 4  # aucun choix, trop serré


def filter_relative_winner(scores, margin=0.2, question_number=None, parent=None):
    if len(scores) != 4:
        raise ValueError("Chaque question doit avoir exactement 4 scores")

    max_idx = int(np.argmax(scores))
    max_val = scores[max_idx]
    others = [s for i, s in enumerate(scores) if i != max_idx]

    if all(max_val - o > margin for o in others):
        return [i == max_idx for i in range(4)]

    # si doute → on stocke
    if parent is not None and question_number is not None:
        parent.douteux[question_number] = scores
    return [False] * 4

# === MAIN ===

if __name__ == '__main__':
    X_train, X_test, y_train, y_test = load_strict_dataset(
        base_path='dataset_patches',
        filled_subfolder='filled',
        empty_subfolder='empty_balanced_chars',
        size=(30, 30)
    )

    # balance_patch_by_ocr_char()

    # X_train, X_test, y_train, y_test = load_balanced_dataset()

    print(f"[INFO] Nombre total d’échantillons (entraînement + test) : {len(X_train) + len(X_test)}")
    train_random_forest(X_train, y_train, X_test, y_test)
