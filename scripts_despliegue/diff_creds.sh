#!/bin/bash
# Diff credenciales: como Elon vs como Combos
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/diff_creds_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== DIFF CREDENCIALES - $(date) ==="
echo ""
echo "== 1. config_real.json de Elon =="
ls -la /opt/polymarket/bot-polymarket-elon/config_real.json 2>&1
echo ""
if [ -f /opt/polymarket/bot-polymarket-elon/config_real.json ]; then
  echo "Contenido (sin secretos):"
  python3 -c "
import json
with open('/opt/polymarket/bot-polymarket-elon/config_real.json') as f:
    d = json.load(f)
for k, v in d.items():
    if isinstance(v, str) and len(v) > 20:
        print(f'  {k}: <len={len(v)}>')
    else:
        print(f'  {k}: {v}')
"
fi
echo ""
echo "== 2. /etc/polymarket.env (que usa mi bot) =="
ls -la /etc/polymarket.env 2>&1
echo ""
if [ -f /etc/polymarket.env ]; then
  echo "Contenido (sin secretos):"
  grep -E "^[A-Z_]+=" /etc/polymarket.env | while read l; do
    k=$(echo "$l" | cut -d= -f1)
    v=$(echo "$l" | cut -d= -f2-)
    if [ -n "$v" ]; then
      echo "  $k: <len=${#v}>"
    else
      echo "  $k: <EMPTY>"
    fi
  done
fi
echo ""
echo "== 3. Que env esta cargado para el bot de Combos =="
PID=$(systemctl show poly-combos-bot -p MainPID --value 2>/dev/null)
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
  echo "PID: $PID"
  cat /proc/$PID/environ 2>/dev/null | tr '\0' '\n' | grep -E "POLY_" | while read l; do
    k=$(echo "$l" | cut -d= -f1)
    v=$(echo "$l" | cut -d= -f2-)
    echo "  $k: <len=${#v}>"
  done
fi
echo ""
echo "== 4. Comparar: el bot de Elon usa config_real.json, no env vars =="
echo "  → Mi bot de Combos lee /etc/polymarket.env"
echo "  → Si el archivo no existe o no tiene las vars, da sin_credenciales"
echo ""
echo "== 5. Solución: crear /etc/polymarket.env desde config_real.json de Elon =="
if [ -f /opt/polymarket/bot-polymarket-elon/config_real.json ]; then
  echo "Hay config_real.json de Elon, podemos crear /etc/polymarket.env desde ahí"
  python3 -c "
import json
with open('/opt/polymarket/bot-polymarket-elon/config_real.json') as f:
    d = json.load(f)
# Mapear campos de config_real.json a env vars
mapping = {
    'wallet_private_key': 'POLY_PRIVATE_KEY',
    'api_key': 'POLY_API_KEY',
    'api_secret': 'POLY_API_SECRET',
    'api_passphrase': 'POLY_API_PASSPHRASE',
    'wallet_address': 'POLY_WALLET_ADDRESS',
}
for k_src, k_dst in mapping.items():
    if k_src in d:
        v = d[k_src]
        print(f'  export {k_dst}={v[:20]}... (len={len(v)})')
    else:
        print(f'  {k_dst}: NO ENCONTRADO en config_real.json')
"
fi

# Publicar
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/diff_creds_${TS}.log"
  CONTenido=$(cat "$LOG")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'diff ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'diff ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
fi
