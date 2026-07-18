#!/usr/bin/env bash
# Failover helper for the venue laptop (see RESTORE.md). Detects the LAN IP,
# opens the firewall for the port if ufw/firewalld is active, prints the URL
# to share with scorekeepers (as a QR code too, if qrencode is installed),
# then starts the Django server.
#
#   scripts/failover_serve.sh            full flow
#   scripts/failover_serve.sh --url-only just print the URL/QR and exit
set -uo pipefail

PORT=8000

# The interface with the default route is the one on the hotspot; fall back
# to the first global IPv4 if there's no route out (hotspot without internet).
IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oE 'src [0-9.]+' | cut -d' ' -f2)
if [ -z "${IP}" ]; then
    IP=$(ip -4 -o addr show scope global | head -1 | awk '{print $4}' | cut -d/ -f1)
fi
if [ -z "${IP}" ]; then
    echo "ERROR: no network address found — is the laptop on the hotspot Wi-Fi?" >&2
    exit 1
fi

URL="http://${IP}:${PORT}"
echo
echo "  Share this with scorekeepers:  ${URL}"
echo
if command -v qrencode >/dev/null; then
    qrencode -t ansiutf8 "${URL}"
else
    echo "  (install 'qrencode' to also get a scannable QR code here)"
fi
echo

if [ "${1:-}" = "--url-only" ]; then
    exit 0
fi

# Open the firewall if one of the common ones is active. firewalld change is
# runtime-only (gone after reboot); remove the ufw rule afterwards with:
# sudo ufw delete allow ${PORT}/tcp
if command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then
    echo "firewalld is active — opening port ${PORT} (needs sudo)"
    sudo firewall-cmd --add-port="${PORT}/tcp"
elif command -v ufw >/dev/null && sudo ufw status 2>/dev/null | grep -q "Status: active"; then
    echo "ufw is active — opening port ${PORT} (needs sudo)"
    sudo ufw allow "${PORT}/tcp"
else
    echo "No active ufw/firewalld found — assuming nothing blocks port ${PORT}."
fi

cd "$(dirname "$0")/.."
source venv/bin/activate
python manage.py runserver 0.0.0.0:"${PORT}" &
SERVER_PID=$!

sleep 3
STATUS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${URL}/" || true)
case "${STATUS}" in
    2*|3*) echo "Sanity check: server answers on ${URL} (HTTP ${STATUS})." ;;
    *)     echo "WARNING: no answer on ${URL} (got '${STATUS}') — check the output above." ;;
esac
echo "Now confirm from a phone on the hotspot — that's the test that matters."

wait "${SERVER_PID}"
