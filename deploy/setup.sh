#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu VM. Run as root: bash deploy/setup.sh <git-repo-url>
# Then: edit /opt/medora/.env, edit the domain in /etc/caddy/Caddyfile, run scripts/seed.sh, start services.
set -euo pipefail
[ $# -eq 1 ] || { echo "Usage: $0 <git-repo-url>"; exit 1; }
apt-get update && apt-get install -y git curl caddy
id medora >/dev/null 2>&1 || useradd -m -s /bin/bash medora
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
[ -d /opt/medora ] || git clone "$1" /opt/medora
cd /opt/medora
[ -f .env ] || cp .env.example .env
chown -R medora:medora /opt/medora
chmod 600 .env
sudo -u medora bash -c 'cd /opt/medora/api && uv sync --no-dev --python 3.12 --extra messy --extra pii --extra graph'
cp deploy/medora-*.service /etc/systemd/system/
cp deploy/Caddyfile /etc/caddy/Caddyfile
systemctl daemon-reload
echo "Next: edit .env and /etc/caddy/Caddyfile, then:"
echo "  sudo -u medora scripts/seed.sh \"Dr. Name\""
echo "  systemctl enable --now medora-api medora-worker && systemctl restart caddy"
