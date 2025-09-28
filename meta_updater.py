import csv
import json
import os
import unicodedata

TOEIC_STRUCTURE = {
    "listening": {
        "range": (1, 100),
        "subparts": {
            "part1": (1, 6),
            "part2": (7, 31),
            "part3": (32, 70),
            "part4": (71, 100),
        }
    },
    "reading": {
        "range": (101, 200),
        "subparts": {
            "part5": (101, 130),
            "part6": (131, 146),
            "part7": (147, 200),
        }
    }
}

TOEIC_SCORES = None

def get_toeic_table():
    global TOEIC_SCORES
    if TOEIC_SCORES is None:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(script_dir, "toeic_scores.json")
            with open(json_path, "r", encoding="utf-8") as f:
                TOEIC_SCORES = json.load(f)
        except:
            TOEIC_SCORES = {}
    return TOEIC_SCORES


def compute_detailed_scores(filled, correction_path, choices_per_question=4):
    try:
        with open(correction_path, newline='') as f:
            reader = csv.reader(f)
            corrections = [(int(row[0]), row[1].strip().upper()) for row in reader]

        letter_to_index = {chr(65 + i): i for i in range(choices_per_question)}

        scores = {
            "raw_score": 0,
            "listening": 0,
            "reading": 0,
            "subparts": {f"part{i}": 0 for i in range(1, 8)}
        }

        for i, (q_num, correct_letter) in enumerate(corrections):
            start = (q_num - 1) * choices_per_question
            end = start + choices_per_question
            if end > len(filled):
                continue
            group = filled[start:end]

            if group.count(True) == 1 and group.index(True) == letter_to_index.get(correct_letter):
                scores["raw_score"] += 1
                for section, info in TOEIC_STRUCTURE.items():
                    if info["range"][0] <= q_num <= info["range"][1]:
                        scores[section] += 1
                        for sub, (s, e) in info["subparts"].items():
                            if s <= q_num <= e:
                                scores["subparts"][sub] += 1
                        break

        toeic_table = get_toeic_table()
        scores["scaled_listening"] = toeic_table.get(str(scores["listening"]), {"listening": 0})["listening"]
        scores["scaled_reading"] = toeic_table.get(str(scores["reading"]), {"reading": 0})["reading"]
        scores["scaled_total"] = scores["scaled_listening"] + scores["scaled_reading"]

        return scores

    except Exception as e:
        print(f"[ERREUR] Calcul score détaillé : {e}")
        return {}

def update_score_in_meta(meta_path, filled, correction_path):

    if not os.path.exists(correction_path) or not os.path.exists(meta_path):
        print(f"[WARN] Correction ou meta.json introuvable.")
        return
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
        meta.update(compute_detailed_scores(filled, correction_path))
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        print(f"[ERREUR] Mise à jour du score dans meta.json : {e}")

def rename_folder_from_meta(copy_dir):
    meta_path = os.path.join(copy_dir, "meta.json")
    if not os.path.exists(meta_path):
        return
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
        nom = meta.get("nom", "").strip()
        if not nom:
            return
        norm = unicodedata.normalize("NFKD", nom)
        ascii_nom = ''.join(c for c in norm if not unicodedata.combining(c))
        clean_nom = ascii_nom.title().replace(" ", "_")
        new_dir = os.path.join(os.path.dirname(copy_dir), clean_nom)
        if new_dir != copy_dir and not os.path.exists(new_dir):
            os.rename(copy_dir, new_dir)
            print(f"[INFO] Dossier renommé : {new_dir}")
        else:
            print(f"[WARN] Dossier déjà existant ou inchangé.")
    except Exception as e:
        print(f"[ERREUR] Renommage dossier : {e}")
