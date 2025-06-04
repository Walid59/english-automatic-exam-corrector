# stats.py

import os
import json
import numpy as np
from os.path import join
from PySide6 import QtWidgets
import pandas as pd
from PySide6.QtWidgets import QFileDialog

part_names = [
    "part1", "part2", "part3", "part4",
    "part5", "part6", "part7"
]
part_labels = {
    "part1": "Photographs",
    "part2": "Question-Response",
    "part3": "Conversations",
    "part4": "Short Talks",
    "part5": "Incomplete Sentences",
    "part6": "Text Completion",
    "part7": "Reading Comprehension"
}

global_keys = [
    ("scaled_listening", "Listening"),
    ("scaled_reading", "Reading"),
    ("scaled_total", "Total TOEIC")
]

def compute_stats(values):
    if not values:
        return ["N/A"] * 4
    return [
        f"{np.mean(values):.2f}",
        f"{np.median(values):.2f}",
        f"{min(values)}",
        f"{max(values)}"
    ]

class StatsDialog(QtWidgets.QDialog):
    def __init__(self, project_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Statistiques globales")
        self.setMinimumSize(600, 400)
        self.layout = QtWidgets.QVBoxLayout(self)

        export_btn = QtWidgets.QPushButton("📁 Exporter vers Excel")
        export_btn.clicked.connect(lambda: export_scores_to_excel(project_path, self))
        self.layout.addWidget(export_btn)

        scores = self.load_scores(project_path)

        self.layout.addWidget(QtWidgets.QLabel("📊 Scores bruts (par sous-partie)"))
        self.layout.addWidget(self.create_table(
            headers=["Section", "Moyenne", "Médiane", "Min", "Max"],
            rows=[
                [part_labels[part]] + compute_stats([s["subparts"].get(part, 0) for s in scores])
                for part in part_names
            ]
        ))

        self.layout.addWidget(QtWidgets.QLabel("📈 Scores échelonnés (globaux)"))
        self.layout.addWidget(self.create_table(
            headers=["Section", "Moyenne", "Médiane", "Min", "Max"],
            rows=[
                [label] + compute_stats([s.get(key, 0) for s in scores])
                for key, label in global_keys
            ]
        ))

        close_btn = QtWidgets.QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        self.layout.addWidget(close_btn)

    def load_scores(self, project_path):
        scores = []
        for name in os.listdir(project_path):
            dir_path = join(project_path, name)
            meta_path = join(dir_path, "meta.json")
            if not os.path.exists(meta_path):
                continue
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                scores.append({
                    "subparts": meta.get("subparts", {}),
                    "scaled_listening": meta.get("scaled_listening", 0),
                    "scaled_reading": meta.get("scaled_reading", 0),
                    "scaled_total": meta.get("scaled_total", 0)
                })
            except Exception as e:
                print(f"[ERREUR] Lecture {meta_path} : {e}")
        return scores

    def create_table(self, headers, rows):
        table = QtWidgets.QTableWidget()
        table.setRowCount(len(rows))
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)

        for row_idx, row in enumerate(rows):
            for col_idx, val in enumerate(row):
                item = QtWidgets.QTableWidgetItem(val)
                table.setItem(row_idx, col_idx, item)

        table.resizeColumnsToContents()
        return table

def export_scores_to_excel(project_path, parent=None):
    rows = []
    for name in os.listdir(project_path):
        dir_path = join(project_path, name)
        meta_path = join(dir_path, "meta.json")
        if not os.path.exists(meta_path):
            continue
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            row = {
                "Nom": meta.get("nom", name),
                "raw_score": meta.get("raw_score", None),
                "scaled_listening": meta.get("scaled_listening", None),
                "scaled_reading": meta.get("scaled_reading", None),
                "scaled_total": meta.get("scaled_total", None)
            }
            subparts = meta.get("subparts", {})
            for k in ["part1", "part2", "part3", "part4", "part5", "part6", "part7"]:
                row[k] = subparts.get(k, None)
            rows.append(row)
        except Exception as e:
            print(f"[ERREUR] Lecture {meta_path} : {e}")

    if not rows:
        QtWidgets.QMessageBox.warning(parent, "Export", "Aucune copie valide trouvée.")
        return

    df = pd.DataFrame(rows)
    path, _ = QFileDialog.getSaveFileName(parent, "Exporter en Excel", "resultats.xlsx", "Fichiers Excel (*.xlsx)")
    if path:
        df.to_excel(path, index=False)
        QtWidgets.QMessageBox.information(parent, "Export terminé", f"Fichier exporté :\n{path}")