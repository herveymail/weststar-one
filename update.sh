#!/bin/bash
# Weststar ONE — update to the latest version. Backs up first; your data is kept.
#   sudo ./update.sh
set -uo pipefail
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✔${NC}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
die()  { echo -e "  ${RED}✖${NC}  $1"; exit 1; }
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
[ -f .env ] || die "Not installed yet. Run: sudo bash install.sh"
. ./.env
BRANCH="${UPDATE_BRANCH:-main}"
echo -e "\n  ${BOLD}Updating Weststar ONE (${BRANCH})${NC}\n"

./deploy/backup.sh >/dev/null && ok "Backup made first (backups/)." || die "Backup failed, so nothing was updated."
BEFORE=$(git rev-parse --short HEAD)
git fetch -q origin "$BRANCH" || die "Couldn't reach GitHub. Check the server's access to ${UPDATE_REPO:-the repo}."
if [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$BRANCH")" ]; then ok "Already up to date (${BEFORE})."; exit 0; fi
git merge -q --ff-only "origin/$BRANCH" || die "Local changes are in the way (git status shows them). Nothing was changed."
AFTER=$(git rev-parse --short HEAD)
ok "Code updated ${BEFORE} → ${AFTER}."
git log --oneline "${BEFORE}..${AFTER}" | sed 's/^/      /' | head -20

APP_VERSION="$AFTER" docker compose build -q app || { git reset -q --hard "$BEFORE"; die "Build failed; rolled the code back to ${BEFORE}. The running app was not touched."; }
docker compose up -d db app jobs caddy || die "Couldn't restart. Check: docker compose logs app"
if git diff --name-only "$BEFORE" "$AFTER" | grep -q '^deploy/Caddyfile$'; then
  docker compose restart caddy >/dev/null && ok "Web server settings reloaded."
fi
for _ in $(seq 1 90); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q app)" 2>/dev/null)" = healthy ] && break; sleep 2
done
if [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q app)" 2>/dev/null)" = healthy ]; then
  ok "Running the new version. Database changes were applied automatically."
else
  warn "The app isn't healthy yet. Check: docker compose logs app  (the backup from a minute ago is in backups/)"
fi
docker image prune -f >/dev/null 2>&1
