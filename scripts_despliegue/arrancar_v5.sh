#!/usr/bin/env bash
# arrancar_v5.sh
set -u
mkdir -p /tmp/auto_exit_elon
for p in $(pgrep -f "auto_exit_v[0-9]"); do kill "$p" 2>/dev/null; done
sleep 2
rm -f /tmp/auto_exit_elon.lock
curl -sL -o /tmp/auto.sh https://raw.githubusercontent.com/lamegawi/bots-backup/HEAD/scripts_despliegue/auto_exit_v5.sh
chmod +x /tmp/auto.sh
HASH=$(curl -s "https://api.github.com/repos/lamegawi/bots-backup/branches/arena/01a058fe-bots-backup" | python3 -c "import json,sys; print(json.load(sys.stdin)['commit']['sha'][:8])")
curl -sL -o /tmp/auto.sh "https://raw.githubusercontent.com/lamegawi/bots-backup/${HASH}/scripts_despliegue/auto_exit_v5.sh"
chmod +x /tmp/auto.sh
echo "[download] $HASH $(wc -c </tmp/auto.sh)b"
DRY_RUN=1 INTERVALO_S=900 AUTO_BANKROLL_USD=20 \
  nohup setsid bash /tmp/auto.sh > /tmp/auto_exit_elon/main.log 2>&1 < /dev/null &
echo "PID: $!"
disown
sleep 35
echo "--- main.log ---"
head -50 /tmp/auto_exit_elon/main.log
echo "--- files ---"
ls -la /tmp/auto_exit_elon/ | tail -8
