#!/bin/bash
# Verificar estado del bot de Elon
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/elon_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== VER BOT ELON - $(date) ==="
echo ""
echo "== 1. Servicios =="
for s in poly-elon poly-semanal poly-mensual poly-telegram poly-gestor; do
  status=$(systemctl is-active $s 2>&1)
  echo "  $s: $status"
done
echo ""
echo "== 2. Ultimo log del bot principal =="
for logf in /var/log/poly-elon.log /var/log/poly-semanal.log /var/log/poly-mensual.log; do
  if [ -f "$logf" ]; then
    echo ""
    echo "--- $logf (ultimas 30 lineas) ---"
    tail -30 "$logf"
  fi
done
echo ""
echo "== 3. Estado de /opt/polymarket =="
ls -la /opt/polymarket/ 2>&1 | head -15
echo ""
echo "== 4. Trades recientes (resultados_real*.csv) =="
for csv in /opt/polymarket/resultados_real*.csv /opt/polymarket/bot-polymarket-elon*/resultados_real*.csv; do
  if [ -f "$csv" ]; then
    echo ""
    echo "--- $csv ---"
    tail -10 "$csv"
  fi
done
echo ""
echo "== 5. Tailscale =="
tailscale status 2>&1 | head -5
echo ""
echo "== 6. IP via proxy =="
curl -sL --max-time 10 -x http://100.83.57.99:8888 https://api.ipify.org 2>&1
echo ""

# Publicar
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/elon_${TS}.log"
  CONTenido=$(cat "$LOG")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'elon ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'elon ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
fi
