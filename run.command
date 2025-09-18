#!/bin/bash
set -e



# Récupère le chemin absolu du script run.sh
DIR="$(cd "$(dirname "$0")" && pwd)"
cd $DIR

# Lancement du main.py depuis le même dossier
./venv/bin/python main.py