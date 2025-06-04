import cv2
import numpy as np
from sklearn.cluster import DBSCAN, KMeans


def detect_and_align_circles(img: np.ndarray,
                             *,
                             blur_kernel=(5, 5),
                             dp=1.0,
                             min_dist=20,
                             param1=100,
                             param2=15,
                             min_radius=12,
                             max_radius=14,
                             eps_x: int = 10,
                             eps_y: int = 10,
                             min_samples: int = 3,
                             debug: bool = False) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, blur_kernel, 0)

    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=dp, minDist=min_dist,
        param1=param1, param2=param2,
        minRadius=min_radius, maxRadius=max_radius
    )

    if circles is None:
        raise ValueError("Aucun cercle détecté.")

    detected = np.round(circles[0, :]).astype(int)
    centers = detected[:, :2]  # (x, y)

    col_x = extract_columns_from_circle_x(centers, eps=eps_x, min_samples=min_samples, debug=debug)
    row_y = extract_lines_from_circle_y(centers, eps=eps_y, min_samples=min_samples, debug=debug)

    #  (x, y) trié
    grid = [(int(x), int(y)) for y in row_y for x in col_x]

    if debug:
        vis = img.copy()
        for x, y in grid:
            cv2.circle(vis, (x, y), 10, (0, 255, 0), 2)
        cv2.imwrite("outputs/debug_aligned_circles.jpg", vis)

    return np.array(grid, dtype=int)


def trace_circles(img, centers, filled, output_path, douteux_centers=None, modified_questions=None, hide_douteux=False):
    douteux_centers = douteux_centers or []
    modified_questions = modified_questions or set()
    output = img.copy()

    for i, (x, y) in enumerate(centers):
        try:
            x, y = int(x), int(y)
            q_num = (i // 4) + 1
            pt = (x, y)

            #  Cercle douteux toujours tracé en jaune
            if pt in douteux_centers and not hide_douteux:
                cv2.circle(output, pt, 12, (0, 255, 255), 2)  # jaune

            #  Cercle marqué comme rempli → vert ou bleu
            if filled[i]:
                color = (255, 0, 0) if q_num in modified_questions else (0, 255, 0)
                cv2.circle(output, pt, 12, color, 2)

        except Exception as e:
            print(f"[TRACE ERROR] cercle {i} ignoré : {e}")

    cv2.imwrite(output_path, output)


# Binarisation de cercle rempli/pas rempli de façon générale : NON FONCTIONNEL
def classify_filled_circles(img: np.ndarray, centers: np.ndarray) -> list[bool]:
    """
    Pour chaque cercle, extrait un patch et estime s'il est rempli (True) ou vide (False),
    avec un seuil adaptatif calculé par clustering.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=15,
        C=5
    )
    fill_ratios = []

    for x, y in centers:
        patch = binary[y - 10:y + 10, x - 10:x + 10]
        if patch.shape != (20, 20):
            fill_ratios.append(0.0)
            continue
        ratio = np.mean(patch == 255)  # % de pixels sombres
        fill_ratios.append(ratio)

    # Convertir en array numpy pour clustering
    fill_array = np.array(fill_ratios).reshape(-1, 1)

    # Clustering en 2 groupes : rempli / vide
    kmeans = KMeans(n_clusters=2, n_init=10, random_state=42)
    labels = kmeans.fit_predict(fill_array)

    # Identifier le cluster "rempli" (le plus sombre)
    means = [np.mean(fill_array[labels == i]) for i in range(2)]
    filled_cluster = np.argmax(means)

    return [label == filled_cluster for label in labels]




def classify_filled_circles_name(img: np.ndarray, centers: np.ndarray,
                                 patch_size: int = 20,
                                 brightness_cap: float = 180.0,
                                 debug: bool = False) -> list[bool]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    half = patch_size // 2
    fill_ratios = []
    valid_indices = []

    for idx, (x, y) in enumerate(centers):
        if y - half < 0 or y + half > gray.shape[0] or x - half < 0 or x + half > gray.shape[1]:
            fill_ratios.append(255.0)
            continue

        patch = gray[y - half:y + half, x - half:x + half]
        mean_val = np.mean(patch)
        fill_ratios.append(mean_val)
        valid_indices.append(idx)

    if not valid_indices:
        return [False] * len(centers)

    valid_vals = np.array([fill_ratios[i] for i in valid_indices]).reshape(-1, 1)
    kmeans = KMeans(n_clusters=2, n_init=10, random_state=42)
    labels = kmeans.fit_predict(valid_vals)

    # Le cluster le plus sombre est considéré comme "rempli"
    means = [np.mean(valid_vals[labels == i]) for i in range(2)]
    filled_cluster = np.argmin(means)

    results = [False] * len(centers)
    for idx, k_idx in zip(valid_indices, range(len(valid_indices))):
        mean_val = fill_ratios[idx]
        is_filled = labels[k_idx] == filled_cluster

        if mean_val > brightness_cap:
            is_filled = False

        results[idx] = is_filled

        if debug:
            print(f"[DEBUG] idx={idx:3} | mean={mean_val:.1f} | cluster={labels[k_idx]} "
                  f"| rempli={results[idx]}")

    return results


def get_expected_background_for_question(index: int) -> str:
    if index < 100:
        return "gray" if (index // 5) % 2 == 0 else "white"
    else:
        return "white" if (index // 5) % 2 == 0 else "gray"


def classify_filled_circles_questions(img: np.ndarray, centers: np.ndarray) -> list[bool]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    fill_ratios = []

    if len(centers) != 800:
        raise ValueError(f"Erreur : attendus 800 cercles, trouvés {len(centers)}")

    for idx, (x, y) in enumerate(centers):
        patch = gray[y - 10:y + 10, x - 10:x + 10]
        if patch.shape != (20, 20):
            fill_ratios.append(0.0)
            continue

        bg = get_expected_background_for_question(idx)
        threshold = 210
        ratio = np.mean(patch < threshold)
        fill_ratios.append(ratio)

    fill_array = np.array(fill_ratios).reshape(-1, 1)
    kmeans = KMeans(n_clusters=2, n_init=10, random_state=42)
    labels = kmeans.fit_predict(fill_array)

    means = [np.mean(fill_array[labels == i]) for i in range(2)]
    filled_cluster = np.argmax(means)

    return [label == filled_cluster for label in labels]


def is_gray_background(gray_img, x, y, radius=12, margin=5):
    patch = gray_img[y - radius - margin: y + radius + margin,
            x - radius - margin: x + radius + margin]
    if patch.shape[0] == 0 or patch.shape[1] == 0:
        return False
    mean_intensity = np.mean(patch)
    return mean_intensity > 120 and mean_intensity < 200


def extract_columns_from_circle_x(centers: np.ndarray,
                                  eps: int = 10,
                                  min_samples: int = 2,
                                  debug: bool = True) -> list[int]:
    if len(centers) == 0:
        return []

    xs = centers[:, 0].reshape(-1, 1)

    clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(xs)
    labels = clustering.labels_

    col_x = []
    for label in sorted(set(labels)):
        if label == -1:
            continue  # bruit
        group = xs[labels == label]
        mean_x = int(np.mean(group))
        col_x.append(mean_x)

    if debug:
        print(f"[INFO] {len(col_x)} colonnes extraites des cercles")
    return sorted(col_x)


def extract_lines_from_circle_y(centers: np.ndarray,
                                eps: int = 10,
                                min_samples: int = 3,
                                debug: bool = True) -> list[int]:
    if len(centers) == 0:
        return []

    ys = centers[:, 1].reshape(-1, 1)

    # Clustering des Y proches
    clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(ys)
    labels = clustering.labels_

    # Pour chaque cluster, prendre la moyenne des Y
    lines_y = []
    for label in sorted(set(labels)):
        if label == -1:
            continue  # -1 = bruit
        group_y = ys[labels == label]
        mean_y = int(np.mean(group_y))
        lines_y.append(mean_y)

    if debug:
        print(f"[INFO] {len(lines_y)} lignes horizontales extraites des cercles")
    return sorted(lines_y)


def recentre_colonnes_nom_prenom(centers, debug=False):
    centers = np.array(centers)

    # Recentrage des colonnes (x) par clustering
    db_x = DBSCAN(eps=10, min_samples=2)
    labels_x = db_x.fit_predict(centers[:, 0].reshape(-1, 1))
    col_x = []
    for label in sorted(set(labels_x)):
        if label == -1:
            continue
        x_vals = centers[labels_x == label, 0]
        col_x.append(int(np.median(x_vals)))
    col_x = sorted(col_x)

    # Recentrage des lignes (y)
    db_y = DBSCAN(eps=8, min_samples=2)
    labels_y = db_y.fit_predict(centers[:, 1].reshape(-1, 1))
    y_lines = []
    for label in sorted(set(labels_y)):
        if label == -1:
            continue
        y_vals = centers[labels_y == label, 1]
        y_lines.append(int(np.median(y_vals)))
    y_lines = sorted(y_lines)

    if debug:
        print(f"[DEBUG] recentre_colonnes_nom_prenom → {len(col_x)} colonnes, {len(y_lines)} lignes")

    return col_x, y_lines