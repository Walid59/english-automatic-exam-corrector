# fichier constants (constants.py)
import os

DIR_PATH = "projects"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FOLDER_ICON = os.path.join(BASE_DIR,"resources/icons/folder.svg")
ADD_ICON = os.path.join(BASE_DIR,"resources/icons/add-button.svg")

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
