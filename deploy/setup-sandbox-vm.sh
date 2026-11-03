#!/usr/bin/env bash
# One-time setup for the sandbox VM (VM-2), Ubuntu 24.04. Run as a sudo user.
set -euo pipefail

echo "== Docker =="
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"

echo "== gVisor (runsc) =="
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
curl -fsSL https://gvisor.dev/archive.key | sudo gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" \
  | sudo tee /etc/apt/sources.list.d/gvisor.list >/dev/null
sudo apt-get update && sudo apt-get install -y runsc
sudo runsc install
sudo systemctl restart docker
echo "== verifying runsc =="
sudo docker run --rm --runtime=runsc hello-world | grep -q Hello && echo "runsc OK"

echo "== firewall: only SSH (team) + runner (VM-1 over VPC) =="
sudo apt-get install -y ufw
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw allow 22/tcp
# Replace with VM-1's private IP:
: "${VM1_PRIVATE_IP:?set VM1_PRIVATE_IP}"
sudo ufw allow from "$VM1_PRIVATE_IP" to any port 8700 proto tcp
sudo ufw --force enable

echo "Next: fill deploy/.env.sandbox, build+push sandbox images, then: docker compose -f deploy/docker-compose.sandbox.yml up -d --build"
