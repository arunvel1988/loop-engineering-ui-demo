#!/bin/bash

set -e

echo "======================================"
echo "Updating package list..."
echo "======================================"
sudo apt update

echo "======================================"
echo "Installing required packages..."
echo "======================================"
sudo apt install -y docker.io nano git lsof curl

echo "======================================"
echo "Starting Docker service..."
echo "======================================"
sudo systemctl enable docker
sudo systemctl start docker

echo "======================================"
echo "Installing Docker Compose v1.29.2..."
echo "======================================"
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" \
-o /usr/local/bin/docker-compose

sudo chmod +x /usr/local/bin/docker-compose

echo "======================================"
echo "Setting Docker socket permissions..."
echo "======================================"
sudo chmod 777 /var/run/docker.sock

echo "======================================"
echo "Installation Complete"
echo "======================================"

echo ""
echo "Docker Version:"
docker --version

echo ""
echo "Docker Compose Version:"
docker-compose --version

echo ""
echo "Docker Service Status:"
sudo systemctl status docker --no-pager

echo ""
echo "Done!"
