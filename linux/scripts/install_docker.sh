#!/usr/bin/env bash

set -Eeuo pipefail

log() {
    echo "[INFO] $1"
}

error() {
    echo "[ERROR] $1" >&2
}

trap 'error "Installation failed at line $LINENO. Command: $BASH_COMMAND"' ERR

if [[ "${EUID}" -ne 0 ]]; then
    error "This script must be run as root. Use: sudo ./install_docker.sh"
    exit 1
fi

log "Starting Docker installation for Debian..."

log "Updating package index..."
apt update

log "Installing required packages..."
apt install -y ca-certificates curl gnupg

log "Creating APT keyrings directory..."
mkdir -p /etc/apt/keyrings

log "Downloading Docker GPG key..."
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

log "Setting permissions for Docker GPG key..."
chmod a+r /etc/apt/keyrings/docker.gpg

log "Detecting system architecture..."
ARCHITECTURE="$(dpkg --print-architecture)"

log "Detecting Debian version codename..."
if [[ -r /etc/os-release ]]; then
    . /etc/os-release
else
    error "/etc/os-release not found"
    exit 1
fi

if [[ -z "${VERSION_CODENAME:-}" ]]; then
    error "VERSION_CODENAME is not defined in /etc/os-release"
    exit 1
fi

log "Adding Docker APT repository..."
cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=${ARCHITECTURE} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable
EOF

log "Updating package index with Docker repository..."
apt update

log "Installing Docker packages..."
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

log "Checking Docker service status..."
systemctl enable docker
systemctl start docker

log "Verifying Docker installation..."
docker --version
docker compose version

sudo usermod -aG docker $USER
log "Add Docker to $USER group"

log "Docker installation completed successfully."
