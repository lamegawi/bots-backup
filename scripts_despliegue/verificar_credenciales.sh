#!/bin/bash
# Verificar credenciales
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/cred_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== VERIFICAR CREDENCIALES - $(date) ==="
echo ""
echo "== 1. Existe /etc/polymarket.env? =="
ls -la /etc/polymarket.env 2>&1
echo ""
echo "== 2. Contenido (sin secretos) =="
if [ -f /etc/polymarket.env ]; then
  grep -E "^[A-Z_]+=" /etc/polymarket.env | sed 's/=.*/=<set>/' | head -20
  echo ""
  echo "Cantidad de vars:"
  grep -cE "^[A-Z_]+=" /etc/polymarket.env
fi
echo ""
echo "== 3. Existe /root/poly_combos_token.txt? =="
ls -la /root/poly_combos_token.txt 2>&1
echo ""
echo "== 4. systemd lee env? =="
grep -A 1 "EnvironmentFile" /etc/systemd/system/poly-combos-bot.service 2>&1
echo ""
echo "== 5. Probar cargar env desde python =="
python3 << 'PYEOF'
import os, sys
sys.path.insert(0, "/opt/polymarket")
# Cargar env manualmente
env_vars = {}
if os.path.exists("/etc/polymarket.env"):
    with open("/etc/polymarket.env") as f:
        for l in f:
            l = l.strip()
            if not l or l.startswith("#") or "=" not in l: continue
            k, v = l.split("=", 1)
            env_vars[k.strip()] = v.strip().strip('"').strip("'")
print("Vars cargadas del archivo:")
for k in sorted(env_vars.keys()):
    if k.startswith("POLY_"):
        val = env_vars[k]
        print(f"  {k}: {'<set len=' + str(len(val)) + '>' if val else '<EMPTY>'}")
    else:
        print(f"  {k}: {env_vars[k]}")
PYEOF

# Publicar
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/cred_${TS}.log"
  CONTenido=$(cat "$LOG")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'cred ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'cred ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
fi
