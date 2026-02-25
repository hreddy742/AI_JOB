#!/usr/bin/env bash
set -euo pipefail

# Ubuntu/Debian host bootstrap for production deployment.

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This script currently supports apt-based systems (Ubuntu/Debian)."
  exit 1
fi

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

if ! command -v docker >/dev/null 2>&1; then
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

sudo usermod -aG docker "$USER" || true
echo "Prerequisites installed. Re-login may be required for docker group changes."
