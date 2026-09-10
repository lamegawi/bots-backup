#!/usr/bin/env bash
# refrescar_y_evaluar_ultima_oportunidad.sh — fuerza actualización de
# mercado_activo.json y luego evalúa últimas oportunidades
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/refrescar_ult_op_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== REFRESCAR MERCADO Y EVALUAR ÚLTIMAS OPORTUNIDADES — $TS UTC ==="
echo
echo "== 1. REFRESCAR mercado_activo.json =="
python3 mercado_polymarket.py 2>&1 | head -30
echo
echo "== 2. Ver mercados cargados =="
python3 -c "
import json
d = json.load(open('mercado_activo.json'))
ms = d.get('mercados', [])
print(f'total: {len(ms)}')
elon = [m for m in ms if not m.get('cerrado') and 'elon' in m.get('titulo','').lower()]
print(f'elon activos: {len(elon)}')
for m in elon:
    print(f'  - {m.get(\"titulo\",\"?\")[:80]}')
    print(f'    fin: {m.get(\"fin\", \"?\")} tipo: {m.get(\"tipo\",\"?\")}')
"
echo
echo "== 3. MERCADO ÚLTIMAS OPORTUNIDADES =="
python3 mercado_ultima_oportunidad.py --user elonmusk --bankroll 303.55
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
