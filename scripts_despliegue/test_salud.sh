#!/bin/bash
# Test: verificar IP de salida via proxy
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/salud_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== TEST SALUD PROXY - $(date) ==="
echo ""
echo "== 1. IP via proxy =="
curl -sL --max-time 15 -x http://100.83.57.99:8888 https://api.ipify.org
echo ""
echo ""
echo "== 2. IP directa (sin proxy) =="
curl -sL --max-time 15 https://api.ipify.org
echo ""
echo ""
echo "== 3. CLOB via proxy =="
curl -sL --max-time 15 -x http://100.83.57.99:8888 -o /dev/null -w "HTTP: %{http_code}\n" https://clob.polymarket.com/
echo ""
echo "== 4. CLOB sin proxy (directo) =="
curl -sL --max-time 15 -o /dev/null -w "HTTP: %{http_code}\n" https://clob.polymarket.com/

# Publicar
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/salud_${TS}.log"
  CONTenido=$(cat "$LOG")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'salud ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'salud ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo ""
  echo "Publicado en $RUTA"
fi
