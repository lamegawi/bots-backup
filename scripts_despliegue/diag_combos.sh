#!/bin/bash
# Diagnostico: ejecuta una pasada AUTO y publica log
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/diag_combos_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

PAT=""
for p in /root/diag_token.txt ~/diag_token.txt; do
  [ -f "$p" ] && PAT=$(cat "$p" | tr -d '\n') && [ -n "$PAT" ] && break
done

publicar() {
  local ruta="diag_hetzner/diag_combos_${TS}.log"
  [ -z "$PAT" ] && return
  local contenido=$(cat "$LOG")
  local b64=$(echo -n "$contenido" | base64 -w0)
  local sha=""
  sha=$(curl -sL --max-time 20 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}?ref=diag-public" \
    -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  local payload
  if [ -n "$sha" ]; then
    payload=$(python3 -c "import json; print(json.dumps({'message':'diag ${TS}','content':'$b64','branch':'diag-public','sha':'$sha'}))")
  else
    payload=$(python3 -c "import json; print(json.dumps({'message':'diag ${TS}','content':'$b64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}" \
    -H "Authorization: token ${PAT}" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null 2>&1
}

echo "=== DIAGNOSTICO COMBOS - $(date) ==="
echo ""
echo "== Estado del servicio =="
systemctl status poly-combos-bot --no-pager | head -10

echo ""
echo "== Log reciente (ultimas 30 lineas) =="
tail -30 /var/log/poly-combos-bot.log 2>&1

echo ""
echo "== Estado guardado =="
cat /opt/polymarket/combos_estado.json 2>&1 | head -50

echo ""
echo "== Forzar una pasada y capturar =="
# Llamar al bot en modo no-AUTO para que solo diagnostique
# Pero como el bot no tiene CLI, simplemente paramos y arrancamos y miramos
systemctl stop poly-combos-bot 2>/dev/null
pkill -9 -f poly_combos_bot.py 2>/dev/null
sleep 2

# Ejecutar el bot con print statements
echo ""
echo "== Ejecutar bot en modo debug (60 segundos) =="
cd /opt/polymarket
timeout 60 python3 -u poly_combos_bot.py 2>&1 | head -80

echo ""
echo "== Reiniciar servicio =="
systemctl restart poly-combos-bot
sleep 5
systemctl status poly-combos-bot --no-pager | head -10

echo ""
echo "=== FIN ==="
publicar
