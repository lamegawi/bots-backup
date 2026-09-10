#!/bin/bash
# Buscar donde Elon tiene las credenciales
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/buscar_creds_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== BUSCAR CREDS ELON - $(date) ==="
echo ""
echo "== 1. Servicio poly-elon: EnvironmentFile y ExecStart =="
systemctl cat poly-elon 2>&1 | head -30
echo ""
echo "== 2. Servicio poly-semanal =="
systemctl cat poly-semanal 2>&1 | head -30
echo ""
echo "== 3. Servicio poly-mensual =="
systemctl cat poly-mensual 2>&1 | head -30
echo ""
echo "== 4. Buscar archivos .env o config_real en /opt/polymarket =="
find /opt/polymarket -name "config_real*" -o -name ".env" -o -name "*.env" 2>/dev/null | head -20
echo ""
echo "== 5. Variables POLY_ en el proceso de poly-elon =="
PID=$(systemctl show poly-elon -p MainPID --value 2>/dev/null)
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
  echo "PID poly-elon: $PID"
  cat /proc/$PID/environ 2>/dev/null | tr '\0' '\n' | grep -E "POLY_" | while read l; do
    k=$(echo "$l" | cut -d= -f1)
    v=$(echo "$l" | cut -d= -f2-)
    echo "  $k: <len=${#v}>"
  done
fi
echo ""
echo "== 6. Variables POLY_ en el proceso de poly-combos-bot =="
PID=$(systemctl show poly-combos-bot -p MainPID --value 2>/dev/null)
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
  echo "PID poly-combos-bot: $PID"
  cat /proc/$PID/environ 2>/dev/null | tr '\0' '\n' | grep -E "POLY_" | while read l; do
    k=$(echo "$l" | cut -d= -f1)
    v=$(echo "$l" | cut -d= -f2-)
    echo "  $k: <len=${#v}>"
  done
else
  echo "poly-combos-bot no esta corriendo"
fi
echo ""
echo "== 7. /etc/polymarket.env =="
ls -la /etc/polymarket.env 2>&1
echo ""
if [ -f /etc/polymarket.env ]; then
  echo "Contenido (vars encontradas):"
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

# Publicar
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/buscar_creds_${TS}.log"
  CONTenido=$(cat "$LOG")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'buscar ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'buscar ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
fi
