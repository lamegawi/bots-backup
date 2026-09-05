#!/bin/bash
# Test descarga desde Hetzner
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/dl_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== TEST DESCARGA - $(date) ==="
echo ""
HASH="85ef9913"
echo "== 1. curl directo desde Hetzner =="
curl -sL --max-time 20 -o /tmp/test_dl.sh -w "HTTP: %{http_code} | size: %{size_download}\n" \
  "https://raw.githubusercontent.com/lamegawi/bots-backup/${HASH}/scripts_despliegue/actualizar_combos.sh"
echo ""
echo "== 2. Si se descargo, ejecutar =="
if [ -s /tmp/test_dl.sh ]; then
  echo "OK descargado $(wc -c < /tmp/test_dl.sh) bytes"
  bash /tmp/test_dl.sh
else
  echo "FAIL no se descargo"
fi

# Publicar
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/dl_${TS}.log"
  CONTenido=$(cat "$LOG")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'dl ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'dl ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
fi
