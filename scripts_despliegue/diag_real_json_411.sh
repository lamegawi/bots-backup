#!/usr/bin/env bash
# diag_real_json_411.sh — leer real.json completo y comparar con Excel
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_real_json_411_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== DIAG real.json COMPLETO — $TS UTC ==="
echo
echo "== 1. TODAS las entradas del historial =="
python3 -c "
import json
d = json.load(open('real.json'))
hist = d.get('historial', [])
print(f'total ops: {len(hist)}')
print(f'saldo: {d.get(\"saldo\")}')
print(f'paso: {d.get(\"paso\")}')
print()
print('--- TODAS LAS OPS ---')
for i, op in enumerate(hist):
    print(f'\\n=== OP #{i+1} ===')
    for k, v in op.items():
        if isinstance(v, str) and len(v) > 200:
            v = v[:200] + '...'
        print(f'  {k}: {v}')
"
echo
echo "== 2. Posición actual (si hay alguna) =="
python3 -c "
import json
d = json.load(open('real.json'))
print(f'activa: {d.get(\"activa\")}')
print(f'abierta: {d.get(\"abierta\")}')
# Mostrar claves del top-level
print(f'claves top-level: {list(d.keys())}')
"
echo
echo "== 3. ¿Hay otras posiciones en otras ventanas? =="
grep -rE "4-11|september-4|elon-musk-of-tweets-sep" *.json *.txt 2>/dev/null | head -20
echo
echo "== 4. ¿Hay logs en /opt/polymarket/logs/? =="
ls -la /opt/polymarket/logs/ 2>&1 | head -20
ls -la /opt/polymarket/bot-polymarket-elon/*.log 2>&1 | head -10
echo
echo "== 5. ¿Servicio systemd tiene logs de la operación 4-11? =="
journalctl -u poly-elon --since '2026-09-04' --until '2026-09-12' 2>/dev/null | grep -iE "4-11|september-4|FIXWIN|cerrada|cerrar_anticipado|resuelt" | head -30
} > "$LOG" 2>&1

cat "$LOG"

python3 -c "
import base64, json, urllib.request
tok = open('/opt/polymarket/.gh_token').read().strip()
with open('$LOG','rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = '$(basename $LOG)'
p = {'message':f'diag: {name}','branch':'diag-public','content':b64}
req = urllib.request.urlopen(urllib.request.Request(
    f'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/{name}',
    data=json.dumps(p).encode(),
    headers={'Authorization':f'token {tok}','Content-Type':'application/json','Accept':'application/vnd.github.v3+json'},
    method='PUT'), timeout=30)
print('Publicado:', json.loads(req.read())['content']['path'])
"
