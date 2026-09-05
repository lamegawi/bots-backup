#!/bin/bash
# Detecta IP Tailscale del PC y configura el bot de Combos para usarla como proxy
# Tambien prueba si el proxy esta alcanzable
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/proxy_setup_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=========================================="
echo "PROXY SETUP - $(date)"
echo "=========================================="

# Cargar PAT
PAT=""
for p in /root/diag_token.txt ~/diag_token.txt /tmp/diag_token.txt; do
  if [ -f "$p" ]; then
    PAT=$(cat "$p" | tr -d '\n')
    [ -n "$PAT" ] && break
  fi
done

publicar() {
  local ruta="diag_hetzner/proxy_setup_${TS}.log"
  [ -z "$PAT" ] && return
  local contenido=$(cat "$LOG")
  local b64=$(echo -n "$contenido" | base64 -w0)
  local sha=""
  sha=$(curl -sL --max-time 20 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}?ref=diag-public" \
    -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  local payload
  if [ -n "$sha" ]; then
    payload=$(python3 -c "import json; print(json.dumps({'message':'proxy setup ${TS}','content':'$b64','branch':'diag-public','sha':'$sha'}))")
  else
    payload=$(python3 -c "import json; print(json.dumps({'message':'proxy setup ${TS}','content':'$b64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}" \
    -H "Authorization: token ${PAT}" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null 2>&1
}

echo ""
echo "=== Verificar Tailscale en Hetzner ==="
if command -v tailscale >/dev/null 2>&1; then
  tailscale status 2>&1 | head -5
  echo "Tailscale: INSTALADO"
  echo "IP Hetzner tailscale: $(tailscale ip -4 2>/dev/null)"
else
  echo "Tailscale: NO INSTALADO en Hetzner"
fi

echo ""
echo "=== Probar candidatos de IP para el proxy ==="
# IPs candidatas
CANDIDATOS=(
  "100.64.0.1"   # tipica tailscale
  "100.100.100.1" # alternativa
  "192.168.1.1"   # LAN tipica
)
# Anadir IP del gateway
GW=$(ip route 2>/dev/null | grep default | awk '{print $3}' | head -1)
[ -n "$GW" ] && CANDIDATOS+=("$GW")
# Anadir IP del resolv.conf
DNS=$(cat /etc/resolv.conf 2>/dev/null | grep nameserver | head -1 | awk '{print $2}')
[ -n "$DNS" ] && CANDIDATOS+=("$DNS")

for ip in "${CANDIDATOS[@]}"; do
  echo ""
  echo "Probando $ip:8888 ..."
  timeout 3 bash -c "echo > /dev/tcp/$ip/8888" 2>/dev/null && {
    echo "  ✅ ABIERTO en $ip:8888"
    echo "  Verificando que sea proxy HTTP..."
    resp=$(curl -sS --max-time 5 --proxy "http://$ip:8888" http://httpbin.org/ip 2>&1 | head -c 200)
    echo "  Respuesta: $resp"
  } || echo "  ❌ cerrado o no alcanzable"
done

echo ""
echo "=== Estado actual de servicios ==="
ps aux | grep -E "proxy|tailscale" | grep -v grep | head -5
echo ""
echo "=== Probar API Polymarket directo (sin proxy) ==="
curl -sS --max-time 10 "https://clob.polymarket.com/markets?next_cursor=&limit=1" 2>&1 | head -c 200
echo ""
echo ""
echo "=========================================="
echo "FIN - $(date)"
echo "=========================================="
publicar
echo "Publicado en diag_hetzner/proxy_setup_${TS}.log"
