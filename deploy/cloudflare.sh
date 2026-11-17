#!/bin/bash
# Weststar ONE behind Cloudflare.
#
#   cd /opt/weststar-one && sudo ./deploy/cloudflare.sh status   is the site going through Cloudflare? is the lock on?
#   sudo ./deploy/cloudflare.sh lock      only accept visitors that come through Cloudflare (blocks direct hits on the server)
#   sudo ./deploy/cloudflare.sh unlock    accept direct visitors again (use this before turning Cloudflare off)
#
# Weststar ONE already understands Cloudflare: it reads each visitor's real address from Cloudflare, so the security
# log, lockouts and signatures keep showing the right address. "lock" is the last step, after the orange cloud is on.
# It checks first that your addresses really go through Cloudflare, and undoes itself if the site stops answering.
set -uo pipefail
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✔${NC}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
die()  { echo -e "  ${RED}✖${NC}  $1"; exit 1; }
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[ "$(id -u)" -eq 0 ] || die "Run it with sudo."
[ -f .env ] || die "Run this from the Weststar ONE folder (where .env is)."
val() { grep "^$1=" .env | tail -1 | cut -d= -f2- | tr -d "'\""; }
DOMAIN=$(val DOMAIN); PORTAL=$(val PORTAL_DOMAIN); MODE=$(val CLOUDFLARE_ONLY); MODE=${MODE:-off}
[ -n "$DOMAIN" ] || die "DOMAIN isn't set in .env."

set_env() {
    local tmp; tmp=$(mktemp)
    grep -v "^$1=" .env > "$tmp" 2>/dev/null || true
    printf "%s='%s'\n" "$1" "$2" >> "$tmp"
    cat "$tmp" > .env; rm -f "$tmp"
}
via_cf() { curl -sS -o /dev/null -D - --max-time 15 "https://$1/health/" 2>/dev/null | grep -qi '^cf-ray:'; }
healthy() { [ "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://$1/health/" 2>/dev/null)" = 200 ]; }
apply() { set_env CLOUDFLARE_ONLY "$1"; docker compose up -d caddy >/dev/null 2>&1 || die "Couldn't restart the web server. Check: docker compose logs caddy"; sleep 4; }

show() {
    for d in $DOMAIN $PORTAL; do
        if via_cf "$d"; then ok "$d goes through Cloudflare."; else warn "$d does NOT go through Cloudflare (grey cloud, DNS still updating, or not on Cloudflare yet)."; fi
    done
    if [ "$MODE" = on ]; then ok "Lock is ON: the server refuses visitors that don't come through Cloudflare."
    else warn "Lock is off: the server still answers visitors who go straight to its address."; fi
}

case "${1:-status}" in
    status) echo; show; echo ;;
    lock)
        echo
        for d in $DOMAIN $PORTAL; do
            via_cf "$d" || die "$d isn't going through Cloudflare yet, so locking now would take it offline. Turn on the orange cloud for it in Cloudflare › DNS, wait a few minutes, and try again."
        done
        ok "Your address$([ -n "$PORTAL" ] && echo es) go through Cloudflare."
        apply on
        for d in $DOMAIN $PORTAL; do
            if ! healthy "$d"; then
                apply off
                die "$d stopped answering with the lock on, so it was turned back off. In Cloudflare › SSL/TLS, set the mode to \"Full (strict)\" and try again."
            fi
        done
        ok "Lock is ON. Only Cloudflare can reach the web server now; the site answers normally."
        echo "     Before you ever pause or remove Cloudflare, run:  sudo ./deploy/cloudflare.sh unlock"; echo ;;
    unlock)
        apply off; echo; ok "Lock is off. The server answers direct visitors again."; echo ;;
    *) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
