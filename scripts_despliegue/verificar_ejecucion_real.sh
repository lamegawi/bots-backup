#!/usr/bin/env bash
# verificar_ejecucion_real.sh — comprueba si el bot realmente ejecutó la orden
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/verif_ejec_${TS}.log

{
echo "=== VERIFICAR EJECUCIÓN REAL BOT SEMANAL — $TS UTC ==="
echo
echo "== 1. Última ejecución del bot (últimas 50 líneas de journalctl) =="
journalctl -u poly-elon-semanal.service -n 50 --no-pager 2>&1 | tail -40
echo
echo "== 2. ¿Hay orden_id en real_semanal.json? =="
python3 -c "
import json
try:
    d = json.load(open('/opt/polymarket/bot-polymarket-elon-semanal/real_semanal.json'))
    print(json.dumps(d, indent=2)[:2000])
except Exception as e:
    print(f'[ERROR] {e}')
"
echo
echo "== 3. ¿Hay historial de señales? =="
python3 -c "
import json
try:
    d = json.load(open('/opt/polymarket/bot-polymarket-elon-semanal/real_semanal.json'))
    hist = d.get('historial', [])
    print(f'historial: {len(hist)} ops')
    for h in hist[-5:]:
        print(f'  {h.get(\"fecha\")} {h.get(\"mercado\",\"\")[:30]} | bin {h.get(\"bin\")} {h.get(\"lado\")} | {h.get(\"resultado\")} | benef={h.get(\"beneficio\")}')
except Exception as e:
    print(f'[ERROR] {e}')
"
echo
echo "== 4. ¿Posiciones abiertas en la wallet? =="
python3 -c "
import urllib.request, json
wallet = '0xb0E1197098E6d427c01720F1631cAD24CE740FA0'
url = f'https://data-api.polymarket.com/positions?user={wallet}'
try:
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    d = json.loads(urllib.request.urlopen(req, timeout=15).read())
    elon = [p for p in d if 'elon' in p.get('title','').lower() and 'september-8' in p.get('title','').lower() or 'september-11' in p.get('title','').lower()]
    print(f'posiciones semanales elon: {len(elon)}')
    for p in elon:
        t = p.get('title','?')[:60]
        sz = p.get('size',0)
        avg = p.get('avgPrice',0)
        cur = p.get('curPrice',0)
        pnl = p.get('pnl',0)
        print(f'  {t}')
        print(f'    size={sz} avg={avg} cur={cur} pnl={pnl}')
except Exception as e:
    print(f'[ERROR] {e}')
"
echo
echo "== 5. Servicio vivo? =="
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 6. ¿Logs del cron de monitoreo? =="
ls -lat /tmp/mon_bots_*.log 2>&1 | head -3
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/verif_ejec_*.log'))
LOG = logs[-1] if logs else '/tmp/verif_ejec.log'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': f'diag: {name}', 'branch': 'diag-public', 'content': b64}
try:
    req = urllib.request.urlopen(urllib.request.Request(
        f'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/{name}',
        data=json.dumps(p).encode(),
        headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
        method='PUT'), timeout=30)
    print('Publicado:', json.loads(req.read())['content']['path'])
except Exception as e:
    print('[ERROR publicando]', e)
PYEOF
