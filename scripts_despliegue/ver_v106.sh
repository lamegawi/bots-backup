#!/bin/bash
# Ver log en vivo
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/ver_v106_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== VER V10.6 - $(date) ==="
echo ""
echo "== Status =="
systemctl status poly-combos-bot --no-pager 2>&1 | head -8
echo ""
echo "== Ultimas 30 lineas =="
tail -30 /var/log/poly-combos-bot.log 2>&1

PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/ver_v106_${TS}.log"
  CONTenido=$(cat "$LOG")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'ver ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'ver ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
fi
