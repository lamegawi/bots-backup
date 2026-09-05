#!/bin/bash
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/mercados_diag_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

PAT=""
for p in /root/diag_token.txt ~/diag_token.txt; do
  [ -f "$p" ] && PAT=$(cat "$p" | tr -d '\n') && [ -n "$PAT" ] && break
done

publicar() {
  local ruta="diag_hetzner/mercados_diag_${TS}.log"
  [ -z "$PAT" ] && return
  local contenido=$(cat "$LOG")
  local b64=$(echo -n "$contenido" | base64 -w0)
  local sha=""
  sha=$(curl -sL --max-time 20 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}?ref=diag-public" \
    -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  local payload
  if [ -n "$sha" ]; then
    payload=$(python3 -c "import json; print(json.dumps({'message':'mercados ${TS}','content':'$b64','branch':'diag-public','sha':'$sha'}))")
  else
    payload=$(python3 -c "import json; print(json.dumps({'message':'mercados ${TS}','content':'$b64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}" \
    -H "Authorization: token ${PAT}" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null 2>&1
}

echo "=== DIAGNOSTICO MERCADOS - $(date) ==="
echo ""

echo "== Llamada 1: 10 mercados activos =="
curl -sL --max-time 30 "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=10" 2>&1 | head -c 5000
echo ""
echo ""
echo "== Numero total de mercados activos (count por status) =="
python3 << 'PYEOF'
import json, urllib.request
url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=200"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        markets = json.loads(r.read())
    print(f"Total recibidos: {len(markets)}")
    # mostrar los primeros 5
    for i, m in enumerate(markets[:5]):
        q = m.get("question", "?")[:60]
        tags = m.get("tags", [])
        cat = m.get("category", "")
        vol = m.get("volume24hr", 0)
        active = m.get("active")
        closed = m.get("closed")
        print(f"{i+1}. {q}")
        print(f"   tags={tags[:3]} cat={cat} vol={vol} active={active} closed={closed}")
except Exception as e:
    print("ERROR:", e)
PYEOF

publicar
