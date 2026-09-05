#!/bin/bash
# Publica el log cada 60 segundos durante 8 minutos
# Para que el agente pueda ver las pasadas AUTO sin pedirselo al usuario
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/auto_log_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

PAT=""
for p in /root/diag_token.txt ~/diag_token.txt; do
  [ -f "$p" ] && PAT=$(cat "$p" | tr -d '\n') && [ -n "$PAT" ] && break
done

publicar() {
  local ruta="diag_hetzner/auto_log_${TS}.log"
  [ -z "$PAT" ] && return
  local contenido=$(cat "$LOG")
  local b64=$(echo -n "$contenido" | base64 -w0)
  local sha=""
  sha=$(curl -sL --max-time 20 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}?ref=diag-public" \
    -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  local payload
  if [ -n "$sha" ]; then
    payload=$(python3 -c "import json; print(json.dumps({'message':'auto ${TS}','content':'$b64','branch':'diag-public','sha':'$sha'}))")
  else
    payload=$(python3 -c "import json; print(json.dumps({'message':'auto ${TS}','content':'$b64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}" \
    -H "Authorization: token ${PAT}" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null 2>&1
}

# Capturar timestamp inicial
INICIO=$(date +%s)

echo "=== AUTO PUBLICAR LOG - $(date) ==="
echo ""
echo "== systemctl =="
systemctl status poly-combos-bot --no-pager | head -10
echo ""

# Publicar log durante 8 minutos (480s) cada 60s
for i in 1 2 3 4 5 6 7 8; do
  echo "=== Iteración $i - $(date) ==="
  echo "--- log completo ---"
  tail -50 /var/log/poly-combos-bot.log
  echo "--- estado ---"
  cat /opt/polymarket/combos_estado.json | head -30
  publicar
  # esperar 60s (si no han pasado los 8 min)
  AHORA=$(date +%s)
  TRANSCURRIDO=$((AHORA - INICIO))
  if [ $TRANSCURRIDO -lt 480 ]; then
    RESTANTE=$((480 - TRANSCURRIDO))
    if [ $RESTANTE -gt 60 ]; then
      sleep 60
    else
      sleep $RESTANTE
    fi
  fi
done
echo "FIN - $(date)"
publicar
