# exam_processor.py
import cv2
import os
from os.path import join
import numpy as np
import pandas as pd

## Problematiques & solution associée
# - Inclinaison : On incline toutes les images de sorte à ce qu'il soit "plat". Mais comment ? A voir.
# - Taille de l'image variable : on assigne une taille fixe pour toutes les images
# - Image plus ou moins floue : à voir


class CopyCorrector:
    def __init__(self, project_name, project_path):
        self.project_name = project_name
        self.project_path = project_path

    def process(self):
        print(f"Traitement du sujet : {self.project_name}")

        for fname in os.listdir(self.project_path):
            if fname.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                full_path = join(self.project_path, fname)
                self.clean_image(full_path)

    def clean_image(self, filepath):
        print(f"Nettoyage de {filepath}")
        image = cv2.imread(filepath)
        image = cv2.resize(image, (1000, 1500)) # on veut garder un format identique a chaque projet

        if image is None:
            print("Image non lue (peut-être un PDF ?)")
            return

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        equalized = cv2.equalizeHist(gray)
        blurred = cv2.blur(equalized, (3, 3))

        # detection de cercle
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.1,
            minDist=20,
            param1=50,
            param2=15,
            minRadius=7,
            maxRadius=13
        )

        print("l'ensemble des coordonnées des cercles: ", circles)
        circles_df = pd.DataFrame(circles[0], columns=['x', 'y','r'])
        circles_radius = circles_df["r"]
        circles_radius = circles_radius.sort_values(ascending=True)
        print(circles_radius.head(3))

        output = image.copy()

        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                center = (i[0], i[1])
                radius = i[2]
                cv2.circle(output, center, radius, (0, 255, 0), 2)
            print(f"{len(circles[0])} cercles détectés")
        else:
            print("Aucun cercle détecté")

        cleaned_path = join(self.project_path, f"cleaned_{os.path.basename(filepath)}")
        cv2.imwrite(cleaned_path, output)
        print(f"Image annotée enregistrée : {cleaned_path}")