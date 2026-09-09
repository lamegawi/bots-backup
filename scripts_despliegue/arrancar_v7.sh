#!/usr/bin/env bash
# arrancar_v7.sh — limpia lockfile, resetea posicion.json, arranca v7
set -u
mkdir -p /tmp/auto_exit_elon
for p in $(pgrep -f "auto_exit_v[0-9]"); do kill "$p" 2>/dev/null; done
sleep 2
rm -f /tmp/auto_exit_elon.lock

cat > /tmp/auto_exit_elon/posicion.json <<'JSON'
{
  "shares_yes": 230.8,
  "precio_entrada": 0.0260,
  "vendido_yes": 0,
  "shares_no_cubierta": 0,
  "ultima_accion": null,
  "triggers_disparados": []
}
JSON
echo "[reset] vendido_yes=0  triggers=[]"

# Quitar parse_jina.py corrupto si lo está
if [ -f /tmp/parse_jina.py ] && ! head -1 /tmp/parse_jina.py | grep -q "python"; then
  rm -f /tmp/parse_jina.py
fi

# Determinar HASH con fallback seguro
HASH=$(curl -s --max-time 10 "https://api.github.com/repos/lamegawi/bots-backup/branches/arena/01a058fe-bots-backup" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['commit']['sha'][:8])" 2>/dev/null || echo "")
if [ -z "$HASH" ]; then
  HASH="43521968"
fi
echo "[hash] $HASH"

curl -sL -o /tmp/auto.sh "https://raw.githubusercontent.com/lamegawi/bots-backup/${HASH}/scripts_despliegue/auto_exit_v7.sh" || {
  echo "[error] no pude descargar v7"
  exit 1
}
chmod +x /tmp/auto.sh
echo "[download] $(wc -c </tmp/auto.sh)b"

DRY_RUN=1 INTERVALO_S=900 AUTO_BANKROLL_USD=20 \
  nohup setsid bash /tmp/auto.sh > /tmp/auto_exit_elon/main.log 2>&1 < /dev/null &
echo "PID: $!"
disown
sleep 35
echo "--- main.log (primer 60) ---"
head -60 /tmp/auto_exit_elon/main.log
echo "--- files ---"
ls -la /tmp/auto_exit_elon/ | tail -10
