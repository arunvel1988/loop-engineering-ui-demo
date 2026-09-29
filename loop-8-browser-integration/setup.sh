#!/bin/bash

set -e

echo "==========================================="
echo "Installing Python prerequisites..."
echo "==========================================="
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

echo ""
echo "==========================================="
echo "Starting Docker Compose..."
echo "==========================================="
docker-compose up -d

echo ""
echo "Waiting for Ollama to start..."
sleep 15

echo ""
echo "==========================================="
echo "Pulling Qwen3 8B model..."
echo "==========================================="
docker exec -it ollama ollama pull qwen3:8b

echo ""
echo "==========================================="
echo "Available Ollama Models"
echo "==========================================="
curl http://localhost:11434/api/tags

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
pip install flask requests

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
docker --version
docker-compose --version
python3 --version
pip --version

echo ""
echo "==========================================="
echo "Setup Completed Successfully!"
echo "==========================================="
