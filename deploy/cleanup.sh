#!/bin/bash
# Weststar ONE — what is using the server's disk, and a safe clean-up.
#
#   cd /opt/weststar-one && sudo ./deploy/cleanup.sh            show what's using space (changes nothing)
#   sudo ./deploy/cleanup.sh clean                               free space (asks first; add --yes to skip the question)
#
# "clean" removes only things that are safe to lose: leftovers from old updates (Docker build cache and unused
# images), oversized container logs, system logs older than 14 days, and the package download cache.
# It never touches the database, uploaded files or backups. Each run also sends the numbers to
# Settings › System support, so they show on that screen.
set -uo pipefail
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✔${NC}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
die()  { echo -e "  ${RED}✖${NC}  $1"; exit 1; }
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[ "$(id -u)" -eq 0 ] || die "Run it with sudo."
[ -f .env ] || die "Run this from the Weststar ONE folder (where .env is)."
MODE="${1:-report}"; YES=no; QUIET=no
for a in "$@"; do [ "$a" = "--yes" ] && YES=yes; [ "$a" = "--quiet" ] && QUIET=yes; done

kb()    { du -sk "$@" 2>/dev/null | awk '{s+=$1} END {print s+0}'; }                 # size in KB (0 if missing)
human() { awk -v k="${1:-0}" 'BEGIN { split("KB MB GB TB", u); i=1; while (k>=1024 && i<4) { k/=1024; i++ } printf (i==1 ? "%d %s" : "%.1f %s"), k, u[i] }'; }
vol()   { docker volume inspect -f '{{.Mountpoint}}' "$(docker compose config --volumes 2>/dev/null | grep -qx "$1" && docker volume ls -q | grep -E "_$1\$" | head -1)" 2>/dev/null; }
free_kb() { df -k --output=avail / | tail -1 | tr -dc '0-9'; }
dfline() { docker system df --format '{{.Type}}|{{.Size}}|{{.Reclaimable}}' 2>/dev/null | grep "^$1|" | head -1; }

ROWS=()   # label|size|can be freed|note
add() { ROWS+=("$1|$2|$3|$4"); }
collect() {
    ROWS=()
    local l
    l=$(dfline Images);        add "Docker images (the app, database and web server programs)" "$(echo "$l" | cut -d'|' -f2)" "$(echo "$l" | cut -d'|' -f3)" "Old copies pile up with every update"
    l=$(dfline "Build Cache"); add "Docker build leftovers" "$(echo "$l" | cut -d'|' -f2)" "$(echo "$l" | cut -d'|' -f3)" "Left behind by updates; safe to remove"
    local logs_kb; logs_kb=$(kb /var/lib/docker/containers/*/*-json.log*)
    add "Container logs" "$(human "$logs_kb")" "$( [ "$logs_kb" -gt 102400 ] && echo "most of it" || echo "—" )" "Now capped at 50 MB per service"
    local v
    v=$(vol dbdata);     [ -n "$v" ] && add "Database files" "$(human "$(kb "$v")")" "—" "Your data. See the table list above; Rebuild can shrink it"
    v=$(vol media);      [ -n "$v" ] && add "Uploaded files" "$(human "$(kb "$v")")" "—" "Ticket attachments, logos, documents"
    v=$(vol appbackups); [ -n "$v" ] && add "Backups made from Settings › Backups" "$(human "$(kb "$v")")" "—" "Kept for the number of days set in Settings"
    add "Backups made by the nightly server script (backups/)" "$(human "$(kb backups)")" "—" "Kept ${BACKUP_KEEP_DAYS:-14} days"
    local j; j=$(journalctl --disk-usage 2>/dev/null | grep -oE '[0-9.]+[KMGT]' | tail -1)
    add "System logs (journal)" "${j:-?}B" "older than 14 days" ""
    add "Other logs (/var/log)" "$(human "$(kb /var/log)")" "—" ""
    add "Package downloads (apt cache)" "$(human "$(kb /var/cache/apt/archives)")" "all of it" ""
}

show() {
    echo
    df -h / | awk 'NR==2 {printf "  Disk: %s used of %s — %s free (%s full)\n\n", $3, $2, $4, $5}'
    printf "  ${BOLD}%-58s %12s   %s${NC}\n" "What" "Size" "Can be freed"
    for r in "${ROWS[@]}"; do IFS='|' read -r a b c _ <<< "$r"; printf "  %-58s %12s   %s\n" "$a" "$b" "$c"; done
    echo
}

send() {   # hand the numbers to the app (Settings › System support). Never fails the script.
    command -v python3 >/dev/null || return 0
    local json
    json=$(printf '%s\n' "${ROWS[@]}" | DISK="$(df -k --output=size,used,avail / | tail -1)" LAST="${1:-}" python3 -c '
import json, os, sys, datetime
size, used, avail = (int(x) * 1024 for x in os.environ["DISK"].split())
rows = [dict(zip(("label", "size", "freeable", "note"), ln.rstrip("\n").split("|", 3))) for ln in sys.stdin if ln.strip()]
print(json.dumps({"when": datetime.datetime.now(datetime.timezone.utc).isoformat(), "disk_total": size, "disk_used": used, "disk_free": avail,
                  "rows": rows, "last_clean": os.environ.get("LAST", "")}))' 2>/dev/null) || return 0
    [ -n "$json" ] && echo "$json" | docker compose exec -T app sh -c 'cat > /data/backups/.server-report.json' >/dev/null 2>&1 || true
}

collect
if [ "$MODE" != clean ]; then
    [ "$QUIET" = yes ] || { show; echo "  To free space:  sudo ./deploy/cleanup.sh clean"; echo; }
    send ""
    exit 0
fi

show
if [ "$YES" != yes ]; then
    echo "  This removes: Docker leftovers from old updates, container logs over 50 MB, system logs older than 14 days,"
    echo "  and the package download cache. It does NOT touch the database, uploaded files or backups."
    read -r -p "  Go ahead? [y/N] " GO
    [[ "${GO,,}" == y* ]] || { echo "  Nothing was changed."; exit 0; }
fi
BEFORE=$(free_kb)
docker builder prune -f >/dev/null 2>&1 && ok "Docker build leftovers removed."
docker image prune -f >/dev/null 2>&1 && ok "Unused Docker images removed."
N=0
for f in /var/lib/docker/containers/*/*-json.log; do
    [ -f "$f" ] && [ "$(du -k "$f" | cut -f1)" -gt 51200 ] && : > "$f" && N=$((N + 1))
done
[ "$N" -gt 0 ] && ok "Emptied $N oversized container log(s)." || ok "Container logs are already small."
journalctl --vacuum-time=14d >/dev/null 2>&1 && ok "System logs older than 14 days removed."
apt-get clean >/dev/null 2>&1 && ok "Package download cache emptied."
find /var/log -type f \( -name '*.gz' -o -name '*.1' -o -name '*.old' \) -mtime +30 -delete 2>/dev/null && ok "Rotated log files older than 30 days removed."
AFTER=$(free_kb)
FREED=$(( AFTER - BEFORE )); [ "$FREED" -lt 0 ] && FREED=0
echo
ok "Freed $(human "$FREED"). Disk now has $(human "$AFTER") free."
collect
send "Freed $(human "$FREED") on $(date '+%b %-d, %Y %-I:%M %p')"
echo
