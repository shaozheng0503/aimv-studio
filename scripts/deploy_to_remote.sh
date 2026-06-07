#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-81.70.48.6}"
REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_DIR="${REMOTE_DIR:-/home/ubuntu/aimv}"
PUBLIC_HOST="${PUBLIC_HOST:-81.70.48.6}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_NAME="aimv-deploy-$(date +%s)"
LOCAL_ARCHIVE="/tmp/${TMP_NAME}.tar.gz"
REMOTE_ARCHIVE="/tmp/${TMP_NAME}.tar.gz"

if [[ ! -f "${ROOT_DIR}/docker-compose.server.yml" ]]; then
  echo "Missing docker-compose.server.yml"
  exit 1
fi

if [[ ! -f "${ROOT_DIR}/backend/.env.server" ]]; then
  echo "Missing backend/.env.server"
  echo "Copy backend/.env.server.example to backend/.env.server and fill in required keys first."
  exit 1
fi

echo "Preparing deployment archive..."
tar \
  --exclude=".git" \
  --exclude=".DS_Store" \
  --exclude="frontend/node_modules" \
  --exclude="frontend/dist" \
  --exclude="backend/.venv" \
  --exclude="backend/__pycache__" \
  --exclude="backend/app/local_storage" \
  --exclude="backend/local_storage" \
  --exclude="docs" \
  --exclude="assets" \
  --exclude="xiaoyunque" \
  --exclude="test_*.py" \
  --exclude="*/__pycache__" \
  -C "${ROOT_DIR}" \
  -czf "${LOCAL_ARCHIVE}" .

echo "Uploading archive to ${REMOTE_USER}@${REMOTE_HOST}..."
scp "${LOCAL_ARCHIVE}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_ARCHIVE}"

echo "Deploying on remote host..."
ssh "${REMOTE_USER}@${REMOTE_HOST}" "PUBLIC_HOST='${PUBLIC_HOST}' REMOTE_DIR='${REMOTE_DIR}' REMOTE_ARCHIVE='${REMOTE_ARCHIVE}' bash -s" <<'EOF'
set -euo pipefail

mkdir -p "${REMOTE_DIR}"
tar -xzf "${REMOTE_ARCHIVE}" -C "${REMOTE_DIR}"
rm -f "${REMOTE_ARCHIVE}"

cd "${REMOTE_DIR}"

if command -v python3 >/dev/null 2>&1; then
  python3 - <<PY
from pathlib import Path
env_path = Path("backend/.env.server")
text = env_path.read_text()
text = text.replace("http://81.70.48.6:15173", f"http://${PUBLIC_HOST}:15173")
text = text.replace("http://81.70.48.6:18080", f"http://${PUBLIC_HOST}:18080")
env_path.write_text(text)
PY
fi

docker compose -f docker-compose.server.yml up -d --build
docker compose -f docker-compose.server.yml ps
EOF

rm -f "${LOCAL_ARCHIVE}"
echo "Deployment command finished."
