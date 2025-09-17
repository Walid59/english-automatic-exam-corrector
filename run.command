#!/bin/bash
set -e



# Récupère le chemin absolu du script run.sh
DIR="$(cd "$(dirname "$0")" && pwd)"

source "$DIR/venv/bin/activate"

# Lancement du main.py depuis le même dossier
python3.11 "$DIR/main.py"