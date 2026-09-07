#!/bin/bash

set -e

echo "==========================================="
echo "Installing Python prerequisites..."
echo "==========================================="

sudo apt update
sudo apt install -y python3 python3-pip python3-venv

echo ""
echo "==========================================="
echo "Creating Python Virtual Environment..."
echo "==========================================="

python3 -m venv venv

echo ""
echo "==========================================="
echo "Activating Virtual Environment..."
echo "==========================================="

source venv/bin/activate

echo ""
echo "==========================================="
echo "Upgrading pip..."
echo "==========================================="

pip install --upgrade pip

echo ""
echo "==========================================="
echo "Installing Python Packages..."
echo "==========================================="

pip install flask requests groq

echo ""
echo "==========================================="
echo "Generating requirements.txt..."
echo "==========================================="

pip freeze > requirements.txt

echo ""
echo "==========================================="
echo "Installed Packages"
echo "==========================================="

cat requirements.txt

echo ""
echo "==========================================="
echo "Versions"
echo "==========================================="

python3 --version
pip --version

echo ""
echo "==========================================="
echo "Setup Completed Successfully!"
echo "==========================================="

echo ""
echo "To activate the virtual environment later:"
echo "source venv/bin/activate"
echo ""
