#!/bin/bash
# Weststar ONE — only allow SSH (remote admin login) to this server from the addresses you name.
#
#   cd /opt/weststar-one && sudo ./deploy/ssh-lock.sh 162.235.208.133
#   sudo ./deploy/ssh-lock.sh 162.235.208.133 203.0.113.7      (several addresses)
#   sudo ./deploy/ssh-lock.sh --status                          (show the current rule)
#   sudo ./deploy/ssh-lock.sh --open                            (undo: SSH from anywhere again)
#
# Safe by design: after the change you have 5 minutes to confirm you can still connect. If you don't confirm
# (for example because you locked yourself out), SSH is opened to everyone again automatically.
# The website (ports 80/443) is not affected. If your office's internet address ever changes, use your hosting
# provider's console to sign in and run this again with the new address.
set -uo pipefail
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✔${NC}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
die()  { echo -e "  ${RED}✖${NC}  $1"; exit 1; }
SAVED=/etc/weststar-ssh-allow        # install.sh reads this so re-running setup never re-opens SSH
UNIT=weststar-ssh-reopen
TAG="Weststar SSH lock"

[ "$(id -u)" -eq 0 ] || die "Run it with sudo."
command -v ufw >/dev/null || die "The firewall (ufw) isn't installed. Run  sudo bash install.sh  first."
PORT=$(sshd -T 2>/dev/null | awk '$1=="port"{print $2; exit}'); PORT=${PORT:-22}

open_rules() {  # remove every "SSH from anywhere" rule
    ufw delete allow OpenSSH >/dev/null 2>&1; ufw delete limit OpenSSH >/dev/null 2>&1
    for p in "$PORT" 22; do
        ufw delete allow "$p/tcp" >/dev/null 2>&1; ufw delete allow "$p" >/dev/null 2>&1; ufw delete limit "$p/tcp" >/dev/null 2>&1
    done
}
locked_rules() { ufw status | grep -F "$TAG" || true; }
remove_locked() {
    # delete our own rules, highest number first so the numbering doesn't shift under us
    ufw status numbered | grep -F "$TAG" | sed -E 's/^\[ *([0-9]+)\].*/\1/' | sort -rn | while read -r n; do ufw --force delete "$n" >/dev/null 2>&1; done
}
reopen() { ufw allow "$PORT/tcp" >/dev/null 2>&1; remove_locked; rm -f "$SAVED"; }

case "${1:-}" in
    ""|-h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --status)
        if [ -n "$(locked_rules)" ]; then ok "SSH (port $PORT) is only allowed from:"; locked_rules | sed 's/^/      /'
        else warn "SSH (port $PORT) is open to any address."; fi
        exit 0 ;;
    --open)
        reopen; ok "SSH (port $PORT) is open to any address again."; exit 0 ;;
    --reopen-timer)  # called by the safety timer
        reopen; logger -t weststar "SSH lock was not confirmed in time — SSH re-opened to any address"; exit 0 ;;
esac

ADDRS=()
for a in "$@"; do
    [[ "$a" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}(/([0-9]|[12][0-9]|3[0-2]))?$ ]] || die "\"$a\" doesn't look like an IPv4 address (example: 162.235.208.133)."
    IFS=./ read -r o1 o2 o3 o4 _ <<< "$a"
    for o in "$o1" "$o2" "$o3" "$o4"; do [ "$o" -le 255 ] || die "\"$a\" isn't a valid address."; done
    ADDRS+=("$a")
done

echo -e "\n  ${BOLD}Only allow SSH (port $PORT) from: ${ADDRS[*]}${NC}\n"
ME=$(echo "${SSH_CLIENT:-${SSH_CONNECTION:-}}" | awk '{print $1}')
[ -z "$ME" ] && [ -n "${SUDO_USER:-}" ] && ME=$(who -m 2>/dev/null | sed -n 's/.*(\(.*\)).*/\1/p')
if [ -n "$ME" ]; then
    MATCH=no
    for a in "${ADDRS[@]}"; do [ "${a%/*}" = "$ME" ] && MATCH=yes; done
    if [ "$MATCH" = yes ]; then ok "You're connected from $ME, which is on the list."
    else
        warn "You're connected from ${BOLD}$ME${NC}, which is NOT on the list. After this change, this connection's address can't sign in."
        read -r -p "  Go ahead anyway? [y/N] " GO
        [[ "${GO,,}" == y* ]] || { echo "  Nothing was changed."; exit 0; }
    fi
else
    warn "Can't tell which address you're connected from (console session?). Double-check the address before confirming."
fi

# Safety net first: re-open SSH in 5 minutes unless confirmed.
systemctl stop "$UNIT.timer" "$UNIT.service" >/dev/null 2>&1; systemctl reset-failed "$UNIT.service" >/dev/null 2>&1
systemd-run --quiet --unit="$UNIT" --on-active=5m /bin/bash "$(readlink -f "$0")" --reopen-timer \
    || die "Couldn't set the 5-minute safety timer, so nothing was changed."

remove_locked
for a in "${ADDRS[@]}"; do
    ufw allow from "$a" to any port "$PORT" proto tcp comment "$TAG" >/dev/null || { reopen; systemctl stop "$UNIT.timer" >/dev/null 2>&1; die "The firewall refused $a. Nothing was changed."; }
done
open_rules
ufw --force enable >/dev/null 2>&1
ok "Firewall updated. Existing connections stay open."

echo
echo -e "  ${BOLD}Now test it:${NC} open a NEW terminal window and connect to this server the way you normally do."
echo    "  If it connects, come back here and type  yes .  If you do nothing, SSH re-opens to everyone in 5 minutes."
read -r -t 290 -p "  Did the new connection work? [yes/no] " ANS || ANS=""
if [[ "${ANS,,}" == yes ]]; then
    systemctl stop "$UNIT.timer" >/dev/null 2>&1
    printf '%s\n' "${ADDRS[@]}" > "$SAVED"; chmod 644 "$SAVED"
    ok "Locked in. SSH only works from: ${ADDRS[*]}"
    echo   "     Check any time:  sudo ./deploy/ssh-lock.sh --status      Undo:  sudo ./deploy/ssh-lock.sh --open"
else
    systemctl stop "$UNIT.timer" >/dev/null 2>&1
    reopen
    warn "Not confirmed, so SSH is open to any address again. Nothing else was changed."
fi
