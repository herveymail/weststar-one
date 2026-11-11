#!/bin/bash
# Weststar ONE — upgrade the server's operating system to Ubuntu 26.04.1 LTS, safely.
#
#   cd /opt/weststar-one && sudo ./deploy/upgrade-os.sh
#
# What it does:
#   1. Checks the server (Ubuntu 24.04, disk space, the app is healthy).
#   2. Makes a backup of Weststar ONE and a copy of .env (your encryption key) in backups/.
#   3. Installs every 24.04 update first (Ubuntu requires that).
#   4. Runs Ubuntu's own upgrade (do-release-upgrade) to 26.04.1, which ends with a restart.
#   5. After the restart it finishes by itself: turns Docker's package source back on for 26.04,
#      updates Docker, starts Weststar ONE and checks it's healthy. Log: /var/log/weststar-os-upgrade.log
#
# Your data lives in Docker volumes and isn't touched by the upgrade. Take a snapshot of the VM first
# (Proxmox / Hyper-V / DigitalOcean …) — it's the quickest way back if anything goes wrong.
#
#   --after       run the "after the restart" steps by hand (normally automatic)
#   --unattended  answer Ubuntu's questions automatically (keeps your current config files)
set -uo pipefail
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✔${NC}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
die()  { echo -e "  ${RED}✖${NC}  $1"; exit 1; }
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
APP_DIR=$(pwd)
TARGET="26.04"
LOG=/var/log/weststar-os-upgrade.log
UNIT=/etc/systemd/system/weststar-after-os-upgrade.service

[ "$(id -u)" -eq 0 ] || die "Run it with sudo:  sudo ./deploy/upgrade-os.sh"
[ -f .env ] || die "Run this from the Weststar ONE folder (where .env is), e.g. /opt/weststar-one"
. /etc/os-release
[ "${ID:-}" = ubuntu ] || die "This server runs ${PRETTY_NAME:-something other than Ubuntu}. This script upgrades Ubuntu only."

app_healthy() {
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q app 2>/dev/null)" 2>/dev/null)" = healthy ]
}

# Point Docker's apt source at this Ubuntu version (the upgrade switches third-party sources off).
fix_docker_source() {
    local arch; arch=$(dpkg --print-architecture)
    install -m 0755 -d /etc/apt/keyrings
    if [ ! -s /etc/apt/keyrings/docker.asc ]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && chmod a+r /etc/apt/keyrings/docker.asc
    fi
    rm -f /etc/apt/sources.list.d/docker.list.distUpgrade /etc/apt/sources.list.d/docker.sources.distUpgrade
    echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list
}

after() {
    exec > >(tee -a "$LOG") 2>&1
    echo -e "\n  ${BOLD}Weststar ONE — finishing the move to Ubuntu ${VERSION_ID} ($(date))${NC}\n"
    if [ "${VERSION_ID}" != "$TARGET" ]; then
        warn "This server is on Ubuntu ${VERSION_ID}, not ${TARGET} — the upgrade didn't finish. Weststar ONE keeps running as before."
        warn "Run  sudo ./deploy/upgrade-os.sh  again, or look at /var/log/dist-upgrade/main.log"
    else
        ok "Ubuntu ${PRETTY_NAME}."
    fi
    export DEBIAN_FRONTEND=noninteractive
    fix_docker_source
    if apt-get update -qq && apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null; then
        ok "Docker updated for ${VERSION_CODENAME} ($(docker --version | cut -d, -f1))."
    else
        warn "Couldn't update Docker from Docker's site — the copy you already have keeps working. Try again later with:  sudo apt-get update && sudo apt-get upgrade"
    fi
    systemctl enable --now docker >/dev/null 2>&1
    docker compose up -d db app jobs caddy >/dev/null 2>&1 || warn "Couldn't start Weststar ONE. Check: docker compose logs app"
    for _ in $(seq 1 120); do app_healthy && break; sleep 2; done
    if app_healthy; then ok "Weststar ONE is running and healthy."; else warn "Weststar ONE isn't healthy yet. Check: cd ${APP_DIR} && docker compose logs app"; fi
    ufw status 2>/dev/null | grep -q "Status: active" && ok "Firewall is on." || warn "The firewall (ufw) is off. Turn it back on:  sudo ufw enable"
    crontab -l 2>/dev/null | grep -q deploy/backup.sh && ok "Nightly server backup is still scheduled." || warn "The nightly backup isn't in cron any more — run  sudo bash install.sh  to put it back."
    systemctl disable weststar-after-os-upgrade.service >/dev/null 2>&1
    rm -f "$UNIT"; systemctl daemon-reload
    echo -e "\n  Done. Log: ${LOG}\n"
}

if [ "${1:-}" = "--after" ]; then after; exit 0; fi

echo -e "\n  ${BOLD}Upgrade this server to Ubuntu ${TARGET}.1 LTS${NC}\n"
case "${VERSION_ID}" in
    "$TARGET") ok "Already on ${PRETTY_NAME}. Checking Docker and Weststar ONE…"; after; exit 0 ;;
    24.04) ok "Now on ${PRETTY_NAME}." ;;
    22.04) die "This server is on 22.04. Ubuntu goes one LTS at a time: this script will take it to 24.04 first if you run  sudo do-release-upgrade  — then run this script again for 26.04." ;;
    *) die "Ubuntu ${VERSION_ID} isn't an LTS this script knows how to upgrade." ;;
esac

FREE_GB=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
[ "${FREE_GB:-0}" -ge 5 ] || die "Only ${FREE_GB} GB free on the disk. The upgrade needs at least 5 GB. Free some space (e.g. docker image prune -a) and try again."
ok "${FREE_GB} GB free on the disk."
if app_healthy; then ok "Weststar ONE is healthy."; else warn "Weststar ONE isn't healthy right now — fix that first, or you won't know if the upgrade broke anything."; fi

echo
echo -e "  ${BOLD}Before you go on:${NC} take a snapshot of this VM (Proxmox, Hyper-V, DigitalOcean …)."
echo    "  The upgrade takes 15–40 minutes and ends with a restart; Weststar ONE is offline for part of it."
read -r -p "  Have you taken a VM snapshot, and is now a good time? [y/N] " GO
[[ "${GO,,}" == y* ]] || { echo "  Nothing was changed."; exit 0; }

mkdir -p backups && chmod 700 backups
./deploy/backup.sh >/dev/null && ok "Weststar ONE backup made (backups/)." || die "Backup failed, so nothing was changed."
cp -p .env "backups/env_before_ubuntu_${TARGET}_$(date +%Y-%m-%d_%H%M).env" && chmod 600 backups/env_before_ubuntu_* && ok "Copy of .env (with your encryption key) saved in backups/."

export DEBIAN_FRONTEND=noninteractive
echo "  Installing every 24.04 update first…"
apt-get update -qq && apt-get -y -qq -o Dpkg::Options::=--force-confold full-upgrade >/dev/null || die "Installing 24.04 updates failed. Nothing else was changed."
apt-get install -y -qq update-manager-core >/dev/null
ok "24.04 is fully up to date."
if [ -f /var/run/reboot-required ]; then
    warn "Ubuntu wants a restart before the upgrade. Restart now (sudo reboot), then run this script again."
    exit 0
fi
sed -i 's/^Prompt=.*/Prompt=lts/' /etc/update-manager/release-upgrades 2>/dev/null

# Finish automatically after the restart at the end of the upgrade.
cat > "$UNIT" <<EOF
[Unit]
Description=Weststar ONE: finish after the Ubuntu upgrade
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${APP_DIR}
ExecStart=/bin/bash ${APP_DIR}/deploy/upgrade-os.sh --after
TimeoutStartSec=900

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable weststar-after-os-upgrade.service >/dev/null 2>&1
ok "Weststar ONE will finish setting itself up after the restart."

echo
echo -e "  ${BOLD}Starting Ubuntu's upgrade.${NC}"
if [ "${1:-}" = "--unattended" ]; then
    do-release-upgrade -f DistUpgradeViewNonInteractive
else
    echo "  Ubuntu will ask a few questions. Good answers:"
    echo "    • Continue / start the upgrade: y"
    echo "    • A config file was changed (\"keep the local version\" or \"install the package maintainer's\")? Keep the local version (N / default)."
    echo "    • Remove obsolete packages: y"
    echo "    • Restart now: y"
    echo "  If you're connected over SSH, Ubuntu opens a spare SSH on port 1022 in case the connection drops."
    echo
    do-release-upgrade
fi
RC=$?
. /etc/os-release
if [ "$RC" -ne 0 ] || [ "${VERSION_ID}" != "$TARGET" ]; then
    warn "Ubuntu's upgrade didn't complete (code ${RC}). Weststar ONE keeps running on ${PRETTY_NAME}."
    warn "If Ubuntu says the upgrade isn't offered yet, wait a day and try again. Details: /var/log/dist-upgrade/main.log"
    systemctl disable weststar-after-os-upgrade.service >/dev/null 2>&1; rm -f "$UNIT"; systemctl daemon-reload
    fix_docker_source; apt-get update -qq >/dev/null 2>&1
    exit 1
fi
# Upgrade finished but the person chose not to restart yet: finish now (it also runs once after the next restart).
after
