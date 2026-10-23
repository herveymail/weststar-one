#!/bin/bash
#
# Weststar ONE — Interactive Server Setup Wizard
# Created by Casey Hervey — El Paso, Texas
# Supports: Ubuntu 22.04 / 24.04 / 26.04 LTS, Debian 12 / 13
#
# On a fresh server:
#   git clone https://github.com/herveymail/weststar-one.git /opt/weststar-one
#   sudo bash /opt/weststar-one/install.sh
#
set -uo pipefail

# ── Colors & formatting (same look as the old Weststar One installer) ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'
BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

print_banner() {
    clear
    echo -e "${CYAN}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║                                          ║"
    echo "  ║     ⚡  Weststar ONE Setup Wizard  ⚡      ║"
    echo "  ║       IT Management Platform             ║"
    echo "  ║                                          ║"
    echo "  ║   Created by Casey Hervey                ║"
    echo "  ║   El Paso, Texas                         ║"
    echo "  ║                                          ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}
TOTAL=7
step()    { echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; echo -e "${BOLD}  STEP $1/${TOTAL}: $2${NC}"; echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"; }
info()    { echo -e "  ${CYAN}ℹ${NC}  $1"; }
success() { echo -e "  ${GREEN}✔${NC}  $1"; }
warn()    { echo -e "  ${YELLOW}⚠${NC}  $1"; }
fail()    { echo -e "  ${RED}✖${NC}  $1"; }
die()     { fail "$1"; echo -e "  ${DIM}Nothing else was changed. Fix the problem and run the wizard again.${NC}"; exit 1; }

# ask "Prompt" "default" VAR
ask() {
    local input
    if [ -n "$2" ]; then echo -ne "  ${BOLD}$1${NC} ${DIM}[$2]${NC}: "; else echo -ne "  ${BOLD}$1${NC}: "; fi
    read -r input
    printf -v "$3" '%s' "${input:-$2}"
}
# ask_secret "Prompt" VAR   (hidden; Enter = leave blank)
ask_secret() {
    local input
    echo -ne "  ${BOLD}$1${NC}: "; read -rs input; echo ""
    printf -v "$2" '%s' "$input"
}
# ask_yesno "Prompt" "y|n" VAR
ask_yesno() {
    local input
    echo -ne "  ${BOLD}$1${NC} ${DIM}[$2]${NC}: "; read -r input
    input="${input:-$2}"
    if [[ "$input" =~ ^[Yy] ]]; then printf -v "$3" yes; else printf -v "$3" no; fi
}
rand_hex() { head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'; }
rand_b64key() { head -c 32 /dev/urandom | base64 | tr -d '\n'; }
json_escape() { python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'; }
set_env() {  # set_env KEY VALUE  — add or replace one line in .env (single-quoted: taken literally)
    local tmp; tmp=$(mktemp)
    case "$2" in *"'"*) die "The value for $1 can't contain a ' (single quote)." ;; esac
    grep -v "^$1=" .env > "$tmp" 2>/dev/null || true
    printf "%s='%s'\n" "$1" "$2" >> "$tmp"
    cat "$tmp" > .env; rm -f "$tmp"
}

# ── Pre-flight checks ──
print_banner
[ "${EUID:-$(id -u)}" -eq 0 ] || { fail "This installer must be run as root."; echo -e "  Run: ${BOLD}sudo bash install.sh${NC}"; exit 1; }
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR" || exit 1
[ -f docker-compose.yml ] || die "Run this from the Weststar ONE folder (docker-compose.yml not found)."
. /etc/os-release 2>/dev/null || die "Can't tell which Linux this is."
case "${ID}:${VERSION_ID:-}" in
    ubuntu:22.04|ubuntu:24.04|ubuntu:26.04|debian:12|debian:13) success "Supported system: ${PRETTY_NAME}" ;;
    *) warn "${PRETTY_NAME:-This system} isn't tested. Ubuntu 24.04/26.04 LTS or Debian 12/13 are recommended."
       ask_yesno "Continue anyway?" "n" GO; [ "$GO" = yes ] || exit 1 ;;
esac
command -v python3 >/dev/null || { apt-get update -qq && apt-get install -y -qq python3 >/dev/null; }

PROGRESS=$(cat .install-progress 2>/dev/null || echo 0)
if [ -f .env ] && [ ! -f .installed ] && grep -q '^DB_PASSWORD=.\+' .env; then
    warn "A previous setup didn't finish (it got past step ${PROGRESS} of ${TOTAL}). Picking up where it stopped:"
    info "you'll answer the questions again; the database that was already created is reused."
    RESUME=yes
elif [ -f .installed ]; then
    warn "Weststar ONE is already set up in ${APP_DIR}."
    echo -e "    ${BOLD}1${NC}) Update to the latest version (keeps all data)  ${DIM}— same as ./update.sh${NC}"
    echo -e "    ${BOLD}2${NC}) Import / re-import from the old Weststar One"
    echo -e "    ${BOLD}3${NC}) Cancel"
    ask "Choose" "1" CHOICE
    case "$CHOICE" in
        1) exec bash ./update.sh ;;
        2) RERUN_IMPORT=yes ;;
        *) exit 0 ;;
    esac
fi
RERUN_IMPORT="${RERUN_IMPORT:-no}"
RESUME="${RESUME:-no}"
mark() { echo "$1" > .install-progress; }

# ════════════════════════════════════════════
if [ "$RERUN_IMPORT" = no ]; then
step 1 "Configuration"
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
info "Point your domain's DNS (an A record) at this server (${SERVER_IP:-its public IP}) before step 7, so HTTPS can be issued."
ask "Domain for Weststar ONE (e.g. one.weststarmsp.com)" "" DOMAIN
[[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || die "That doesn't look like a domain name."
ask "App name" "Weststar ONE" APP_NAME
ask "Company name" "Weststar MSP" COMPANY_NAME
ask "Time zone" "America/Denver" TIMEZONE
ask "Your name (first admin)" "Casey Hervey" ADMIN_NAME
ask "Your email (first admin)" "" ADMIN_EMAIL
[[ "$ADMIN_EMAIL" == *@*.* ]] || die "That doesn't look like an email address."
ADMIN_DOMAIN="${ADMIN_EMAIL##*@}"

echo ""; info "Google Workspace sign-in lets staff use their company Google login."
info "Create the OAuth client first: README › Google sign-in (redirect URL: https://${DOMAIN}/login/google/callback/)"
ask_yesno "Set up Sign in with Google now?" "y" USE_GOOGLE
if [ "$USE_GOOGLE" = yes ]; then
    ask "Google OAuth client ID" "" G_CLIENT_ID
    ask_secret "Google OAuth client secret (hidden)" G_CLIENT_SECRET
    ask "Allowed Workspace domains (comma-separated)" "${ADMIN_DOMAIN}" G_DOMAINS
    ask_yesno "Only admins may still use a password (everyone else must use Google)?" "y" G_ADMINS_ONLY
fi

echo ""; info "Email: send ticket replies and alerts through Google Workspace (Gmail)."
ask_yesno "Set up email sending now?" "n" USE_EMAIL
if [ "$USE_EMAIL" = yes ]; then
    ask "Support mailbox" "support@${ADMIN_DOMAIN}" MAIL_SUPPORT
    ask "Send-from address" "${MAIL_SUPPORT}" MAIL_FROM
    ask "SMTP username (a Workspace user)" "${MAIL_SUPPORT}" MAIL_USER
    ask_secret "Google app password for that user (hidden)" MAIL_PASS
fi

echo ""; info "Backups run every night (database + files, kept 14 days on this server)."
ask_yesno "Also copy backups off-site to Wasabi?" "n" USE_WASABI
if [ "$USE_WASABI" = yes ]; then
    ask "Wasabi region (must match your bucket)" "us-east-1" W_REGION
    ask "Wasabi bucket name" "" W_BUCKET
    ask "Wasabi access key ID" "" W_KEY
    ask_secret "Wasabi secret key (hidden)" W_SECRET
    ask "Folder prefix" "weststar-one" W_PREFIX
fi

echo ""; ask_yesno "Set up the AI assistant (ticket summaries, reply drafts)?" "n" USE_AI
if [ "$USE_AI" = yes ]; then
    ask "AI provider (anthropic / openai / gemini / ollama)" "gemini" AI_PROVIDER
    ask "AI model" "" AI_MODEL
    ask_secret "AI API key (hidden)" AI_KEY
fi

echo ""; ask "GitHub repository for updates (owner/repo)" "herveymail/weststar-one" UPDATE_REPO
ask "Branch to follow" "main" UPDATE_BRANCH

echo ""
echo -e "  ${BOLD}Summary${NC}"
echo -e "    Address:   https://${DOMAIN}"
echo -e "    Company:   ${COMPANY_NAME}   ·   Time zone: ${TIMEZONE}"
echo -e "    Admin:     ${ADMIN_NAME} <${ADMIN_EMAIL}>"
echo -e "    Google:    ${USE_GOOGLE}   ·   Email: ${USE_EMAIL}   ·   Wasabi: ${USE_WASABI}   ·   AI: ${USE_AI}"
ask_yesno "Install with these settings?" "y" GO
[ "$GO" = yes ] || exit 0

# ════════════════════════════════════════════
step 2 "Installing System Packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq || die "apt-get update failed."
apt-get install -y -qq ca-certificates curl git ufw gnupg cron >/dev/null || die "Couldn't install base packages."
success "Base packages installed."
if docker compose version >/dev/null 2>&1; then
    success "Docker is already installed ($(docker --version | cut -d, -f1))."
else
    info "Installing Docker from Docker's official repository…"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc || die "Couldn't download Docker's signing key."
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -qq && apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null || die "Docker install failed."
    systemctl enable --now docker >/dev/null 2>&1
    success "Docker installed."
fi

# Ports 80/443 must be free for HTTPS.
BUSY=$(ss -ltnp 2>/dev/null | awk '$4 ~ /:(80|443)$/ {print $NF}' | grep -v docker-proxy | sed -E 's/.*"([^"]+)".*/\1/' | sort -u | tr '\n' ' ')
if [ -n "$BUSY" ]; then
    warn "Ports 80/443 are in use by: ${BUSY}(probably the old Weststar One's web server)."
    info "The new app needs them. The old app's DATABASE is not affected — you can still import from it below."
    ask_yesno "Stop and disable that web server now?" "n" STOPWEB
    if [ "$STOPWEB" = yes ]; then
        for svc in apache2 nginx caddy lighttpd; do systemctl disable --now "$svc" >/dev/null 2>&1 && success "Stopped ${svc}."; done
    else
        die "Free ports 80 and 443 first (or use a different server), then run the wizard again."
    fi
fi

info "Firewall: allowing SSH, HTTP and HTTPS only."
ufw allow OpenSSH >/dev/null 2>&1; ufw allow 80/tcp >/dev/null 2>&1; ufw allow 443/tcp >/dev/null 2>&1
ufw --force enable >/dev/null 2>&1 && success "Firewall on (SSH, 80, 443)."

# ════════════════════════════════════════════
step 3 "Setting Up Database & Keys"
umask 077
[ -f .env ] || cp .env.example .env
chmod 600 .env
set_env DOMAIN "$DOMAIN"
set_env TIME_ZONE "$TIMEZONE"
set_env SECRET_KEY "$(rand_hex 40)"
# The database keeps the password it was created with, so a resumed setup must reuse it.
if [ "$RESUME" = yes ] && grep -q '^DB_PASSWORD=.\+' .env; then
    success "Reusing the database password from the earlier attempt."
else
    set_env DB_PASSWORD "$(rand_hex 24)"
fi
# A new encryption key is safe until data has been saved (step 5). After that, keep it.
if [ "$RESUME" = yes ] && [ "$PROGRESS" -ge 5 ]; then
    ENC_KEY=$(grep '^APP_ENCRYPTION_KEY=' .env | cut -d= -f2- | tr -d "'")
else
    ENC_KEY="$(rand_b64key)"
    set_env APP_ENCRYPTION_KEY "$ENC_KEY"
fi
set_env UPDATE_REPO "$UPDATE_REPO"
set_env UPDATE_BRANCH "$UPDATE_BRANCH"
if [ "$USE_WASABI" = yes ]; then
    set_env BACKUP_S3_BUCKET "$W_BUCKET"; set_env BACKUP_S3_KEY "$W_KEY"; set_env BACKUP_S3_SECRET "$W_SECRET"
    set_env BACKUP_S3_REGION "$W_REGION"; set_env BACKUP_S3_PREFIX "$W_PREFIX"
    set_env BACKUP_S3_ENDPOINT "https://s3.${W_REGION}.wasabisys.com"
fi
success "Generated a database password, app secret and encryption key (saved in ${APP_DIR}/.env, readable by root only)."
echo ""
echo -e "  ${YELLOW}${BOLD}SAVE THIS ENCRYPTION KEY SOMEWHERE SAFE (password manager or printed in the safe):${NC}"
echo -e "  ${BOLD}${ENC_KEY}${NC}"
echo -e "  ${DIM}It protects 2FA seeds, Wi-Fi passwords and H/R fields. Without it, those can't be read from a backup.${NC}"
SAVED=""
while [ "$SAVED" != "saved" ]; do ask "Type  saved  once you've stored it" "" SAVED; done
mark 3

# ════════════════════════════════════════════
step 4 "Building & Starting the App"
info "Building (first time takes a few minutes)…"
docker compose build -q app || die "Build failed. See the messages above."
app_health() { docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -aq app)" 2>/dev/null; }
show_app_log() {
    echo -e "\n  ${BOLD}Last lines from the app (send these to support):${NC}"
    docker compose logs app --tail 40 --no-log-prefix 2>&1 | sed 's/^/    /'
}
docker compose up -d db app || { show_app_log; die "Couldn't start the app."; }
info "Waiting for the app to be ready (first start sets up the database)…"
for _ in $(seq 1 120); do
    [ "$(app_health)" = healthy ] && break
    sleep 2
done
[ "$(app_health)" = healthy ] || { show_app_log; die "The app didn't start."; }
docker compose up -d jobs || warn "Background jobs didn't start; check: docker compose logs jobs"
success "Database and app are running."
mark 4

# ════════════════════════════════════════════
step 5 "Configuring Application"
ADMIN_OUT=$(docker compose exec -T app python manage.py create_admin --email "$ADMIN_EMAIL" --name "$ADMIN_NAME" 2>&1) || die "Couldn't create the admin: ${ADMIN_OUT}"
TEMP_PW=$(printf '%s\n' "$ADMIN_OUT" | sed -n 's/.*(shown once): //p' | head -1)
success "Admin account created for ${ADMIN_EMAIL}."
{
    printf '{'
    printf '"brand.app_name": %s, "company.name": %s' "$(printf '%s' "$APP_NAME" | json_escape)" "$(printf '%s' "$COMPANY_NAME" | json_escape)"
    if [ "$USE_GOOGLE" = yes ]; then
        printf ', "google.client_id": %s, "google.client_secret": %s, "google.domains": %s, "security.password_login": %s' \
            "$(printf '%s' "$G_CLIENT_ID" | json_escape)" "$(printf '%s' "$G_CLIENT_SECRET" | json_escape)" \
            "$(printf '%s' "$G_DOMAINS" | json_escape)" "$( [ "$G_ADMINS_ONLY" = yes ] && echo '"admins"' || echo '"everyone"')"
    fi
    if [ "$USE_EMAIL" = yes ]; then
        printf ', "email.provider": "Google Workspace", "email.smtp_host": "smtp.gmail.com", "email.smtp_port": "587"'
        printf ', "email.support_address": %s, "email.from_address": %s, "email.smtp_user": %s, "email.smtp_password": %s' \
            "$(printf '%s' "$MAIL_SUPPORT" | json_escape)" "$(printf '%s' "$MAIL_FROM" | json_escape)" \
            "$(printf '%s' "$MAIL_USER" | json_escape)" "$(printf '%s' "$MAIL_PASS" | json_escape)"
    fi
    if [ "$USE_AI" = yes ]; then
        printf ', "ai.provider": %s, "ai.model": %s, "ai.api_key": %s' "$(printf '%s' "$AI_PROVIDER" | json_escape)" \
            "$(printf '%s' "$AI_MODEL" | json_escape)" "$(printf '%s' "$AI_KEY" | json_escape)"
    fi
    printf '}'
} | docker compose exec -T app python manage.py configure >/dev/null || warn "Some settings didn't save — set them in Settings after signing in."
success "Settings saved (secrets are stored encrypted)."
mark 5
fi  # end of first-time setup

# ════════════════════════════════════════════
step 6 "Import from the Old Weststar One"
. ./.env
ask_yesno "Bring over tickets, clients, billing and everything else from the old Weststar One?" "y" DO_IMPORT
if [ "$DO_IMPORT" = yes ]; then
    DUMP=""; UPLOADS=""
    ask "Where is the old app? (folder on THIS server, or leave blank to use a dump file)" "/var/www/myflow" OLD_DIR
    if [ -n "$OLD_DIR" ] && [ -f "$OLD_DIR/config/config.php" ]; then
        # Read the old settings straight from config.php — nothing to copy by hand.
        eval "$(python3 - "$OLD_DIR/config/config.php" <<'PY'
import re, shlex, sys
php = open(sys.argv[1], encoding="utf-8", errors="replace").read()
for m in re.finditer(r"define\(\s*['\"]([A-Z_]+)['\"]\s*,\s*(['\"])((?:\\.|(?!\2).)*)\2\s*\)", php):
    k, v = m.group(1), re.sub(r"\\(['\"\\])", r"\1", m.group(3))
    if k in ("DB_HOST", "DB_USER", "DB_PASS", "DB_NAME", "APP_KEY", "ENCRYPTION_KEY"):
        print(f"OLD_{k}={shlex.quote(v)}")
PY
)"
        success "Read the old settings from ${OLD_DIR}/config/config.php."
        set_env OLD_APP_KEY "${OLD_APP_KEY:-}"; set_env OLD_ENCRYPTION_KEY "${OLD_ENCRYPTION_KEY:-}"
        DUMP="/root/weststar-old-$(date +%Y%m%d_%H%M).sql.gz"
        DUMPER=$(command -v mariadb-dump || command -v mysqldump || true)
        [ -n "$DUMPER" ] || die "mariadb-dump / mysqldump not found on this server."
        info "Making a copy of the old database (read-only)…"
        MYSQL_PWD="$OLD_DB_PASS" "$DUMPER" --single-transaction --quick --skip-lock-tables -h "${OLD_DB_HOST:-localhost}" -u "$OLD_DB_USER" "$OLD_DB_NAME" | gzip > "$DUMP" \
            || die "Couldn't copy the old database."
        chmod 600 "$DUMP"
        success "Old database copied to ${DUMP}."
        [ -d "$OLD_DIR/uploads" ] && UPLOADS="$OLD_DIR/uploads"
    else
        ask "Path to the old database dump (.sql or .sql.gz)" "" DUMP
        [ -f "$DUMP" ] || die "File not found: ${DUMP}"
        ask "Path to the old uploads folder (blank to skip files for now)" "" UPLOADS
        [ -z "$UPLOADS" ] || [ -d "$UPLOADS" ] || die "Folder not found: ${UPLOADS}"
        info "The old APP_KEY and ENCRYPTION_KEY (from the old config/config.php) unlock 2FA, Wi-Fi and H/R fields."
        ask_secret "Old APP_KEY (hidden, blank to skip)" K1
        ask_secret "Old ENCRYPTION_KEY (hidden, blank to skip)" K2
        set_env OLD_APP_KEY "$K1"; set_env OLD_ENCRYPTION_KEY "$K2"
    fi
    info "Practice run first (nothing is saved)…"
    if ./deploy/import-old.sh "$DUMP" ${UPLOADS:+"$UPLOADS"} --dry-run; then
        ask_yesno "Practice run finished. Do the real import now?" "y" REAL
        if [ "$REAL" = yes ]; then
            ./deploy/import-old.sh "$DUMP" ${UPLOADS:+"$UPLOADS"} && success "Import finished. Details: Settings › Import." || warn "The import stopped with an error (shown above). Nothing half-done was saved; you can run it again."
        fi
    else
        warn "The practice run hit a problem (shown above). You can retry later with: ./deploy/import-old.sh ${DUMP} ${UPLOADS}"
    fi
else
    info "Skipped. Later: sudo bash install.sh → option 2, or ./deploy/import-old.sh"
fi
[ "$RERUN_IMPORT" = yes ] && exit 0

# ════════════════════════════════════════════
step 7 "Setting Up HTTPS & Finishing"
docker compose up -d caddy || die "Couldn't start the web server."
info "Getting the HTTPS certificate for ${DOMAIN} (needs DNS pointing here)…"
OK=no
for _ in $(seq 1 60); do
    if curl -fsS --max-time 5 "https://${DOMAIN}/health/" >/dev/null 2>&1; then OK=yes; break; fi
    sleep 3
done
if [ "$OK" = yes ]; then success "HTTPS is working: https://${DOMAIN}"
else warn "HTTPS isn't answering yet. Check DNS for ${DOMAIN} points to this server; Caddy keeps retrying by itself."; fi

CRON_LINE="30 2 * * * cd ${APP_DIR} && ./deploy/backup.sh >> /var/log/weststar-backup.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'deploy/backup.sh'; echo "$CRON_LINE" ) | crontab -
success "Nightly backup scheduled (2:30 AM) → ${APP_DIR}/backups$( [ "$USE_WASABI" = yes ] && echo " + Wasabi")"
docker image prune -f >/dev/null 2>&1

echo ""
date > .installed; rm -f .install-progress
echo -e "${GREEN}  ╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}  ║        Weststar ONE is installed! 🎉       ║${NC}"
echo -e "${GREEN}  ╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Open:            ${BOLD}https://${DOMAIN}${NC}"
echo -e "  Admin email:     ${BOLD}${ADMIN_EMAIL}${NC}"
[ -n "${TEMP_PW:-}" ] && echo -e "  Temp password:   ${BOLD}${TEMP_PW}${NC}   ${DIM}(you'll choose your own, then set up 2FA)${NC}"
[ "$USE_GOOGLE" = yes ] && echo -e "  Staff sign in with ${BOLD}Sign in with Google${NC} — add them first in Settings › Staff users."
echo -e "  Update later:    ${BOLD}sudo ./update.sh${NC}"
echo -e "  Backups:         ${BOLD}${APP_DIR}/backups${NC}  ${DIM}(restore: ./deploy/restore.sh)${NC}"
echo -e "  Settings file:   ${BOLD}${APP_DIR}/.env${NC}  ${DIM}(keep a copy of APP_ENCRYPTION_KEY off this server)${NC}"
echo ""
