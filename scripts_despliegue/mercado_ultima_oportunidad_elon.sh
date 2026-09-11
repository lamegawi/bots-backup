#!/usr/bin/env bash
# mercado_ultima_oportunidad_elon.sh — busca apuestas en ventanas a punto de cerrar
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/mercado_ultima_oportunidad_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

# descargar el script
BRANCH="arena/01a058fe-bots-backup"
TS_NOW=$(date +%s%N)
curl -sL -o mercado_ultima_oportunidad.py "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/poly/codigo/bot-polymarket-elon/mercado_ultima_oportunidad.py?bust=${TS_NOW}"
chmod +x mercado_ultima_oportunidad.py
echo "  descargado: $(wc -c < mercado_ultima_oportunidad.py) bytes"

{
echo "=== MERCADO ÚLTIMAS OPORTUNIDADES — $TS UTC ==="
python3 mercado_ultima_oportunidad.py --user elonmusk
echo
echo "== Bancroll info =="
ls -la real.json 2>/dev/null
[ -f real.json ] && python3 -c "
import json
d = json.load(open('real.json'))
print(f'  saldo: {d.get(\"saldo\", \"?\")}')
print(f'  paso: {d.get(\"paso\", \"?\")}')
print(f'  historial: {len(d.get(\"historial\", []))} ops')
print(f'  activa: {d.get(\"activa\", \"ninguna\")}')
"
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
