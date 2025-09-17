#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing project dependencies..."

# Check if Python 3.11 is installed
if ! command -v python3.11 &> /dev/null
then
    echo "ERROR: Python 3.11 not found on the system."
    echo "Please install it using the official .pkg from
https://www.python.org/downloads/mac-osx/"
    exit 1
fi

# Create a local virtual environment if it doesn't exist
if [ ! -d "$DIR/venv" ]; then
    echo "Creating virtual environment with Python 3.11..."
    python3.11 -m venv "$DIR/venv"
else
    echo "Virtual environment already exists."
fi

# Activate the virtual environment
source "$DIR/venv/bin/activate"

# Upgrade pip and install required packages
echo "Upgrading pip and installing libraries..."
python3.11 -m pip install --upgrade pip
python3.11 -m pip install -r "$DIR/deps.txt"

echo "Installation complete. You can now run the project using run.command"