#!/usr/bin/env bash
# diag_saldo_real_onchain.sh — verificar el saldo REAL on-chain y comparar entre bots
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_saldo_real_${TS}.log

{
echo "=== DIAG SALDO REAL ON-CHAIN — $TS UTC ==="
echo
echo "== 1. Saldo on-chain vía data-api (mismo método) =="
python3 -c "
import urllib.request, json
wallet = '0xb0E148FEb4bE59fD617c8Ad6ce5Cf2b5f0BB2Ae1'
url = f'https://data-api.polymarket.com/value?user={wallet}'
try:
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    d = json.loads(urllib.request.urlopen(req, timeout=20).read())
    print(f'wallet: {wallet}')
    print(f'valor total: \${d}')
except Exception as e:
    print(f'[ERROR] {e}')
"
echo
echo "== 2. Saldo CLOB vía clob.polymarket.com =="
python3 -c "
import urllib.request, json
wallet = '0xb0E148FEb4bE59fD617c8Ad6ce5Cf2b5f0BB2Ae1'
# balance endpoint del CLOB
for endpoint in ['/balance', '/positions', '/trades']:
    url = f'https://clob.polymarket.com{endpoint}?user={wallet}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        d = json.loads(urllib.request.urlopen(req, timeout=15).read())
        print(f'{endpoint}: {str(d)[:300]}')
    except Exception as e:
        print(f'{endpoint}: [ERROR] {e}')
"
echo
echo "== 3. Saldo que reporta CADA bot =="
echo "--- bot Elon ---"
ls /opt/polymarket/bot-polymarket-elon/real.json 2>&1
python3 -c "
import json
try:
    d = json.load(open('/opt/polymarket/bot-polymarket-elon/real.json'))
    print(f'  saldo: \${d.get(\"saldo\")}  paso: {d.get(\"paso\")}  activa: {d.get(\"activa\")}')
    print(f'  bankroll_inicial_real: \${d.get(\"_bankroll_inicial_real\")}')
    print(f'  pnl_historico_acumulado: \${d.get(\"_pnl_historico_acumulado\")}')
except Exception as e:
    print(f'  [ERROR] {e}')
"
echo
echo "--- bot Zelenskyy ---"
ls /opt/polymarket/bot-polymarket-zelenskyy/real.json 2>&1
python3 -c "
import json
try:
    d = json.load(open('/opt/polymarket/bot-polymarket-zelenskyy/real.json'))
    print(f'  saldo: \${d.get(\"saldo\")}  paso: {d.get(\"paso\")}  activa: {d.get(\"activa\")}')
    print(f'  bankroll_inicial_real: \${d.get(\"_bankroll_inicial_real\")}')
except Exception as e:
    print(f'  [ERROR] {e}')
"
echo
echo "--- bot Trump ---"
ls /opt/polymarket/bot-polymarket-trump/real.json 2>&1
python3 -c "
import json, os
for f in ['real.json','real_semanal.json','estado_bot_trump.json']:
    p = f'/opt/polymarket/bot-polymarket-trump/{f}'
    if os.path.exists(p):
        d = json.load(open(p))
        print(f'  {f}: {d}')
    else:
        print(f'  {f}: no existe')
"
echo
echo "== 4. ¿Dónde está el saldo REAL que todos deben compartir? =="
# Buscar en archivos de config o variables de entorno
echo "--- buscar '303.55' ---"
grep -rE "303.55|303\\.55" /opt/polymarket/bot-polymarket-*/config*.json /opt/polymarket/bot-polymarket-*/real*.json 2>/dev/null | head -10
echo
echo "--- buscar '500' ---"
grep -rE "saldo.*500|\"500\"" /opt/polymarket/bot-polymarket-*/config*.json /opt/polymarket/bot-polymarket-*/real*.json 2>/dev/null | head -10
echo
echo "== 5. ¿Qué dice bot_trump.log sobre el saldo? =="
grep -iE "saldo" /opt/polymarket/bot-polymarket-trump/bot_trump.log | tail -10
echo
echo "== 6. ¿Qué ventana tiene ACTIVA Trump? (mercado_activo.json) =="
python3 -c "
import json
d = json.load(open('/opt/polymarket/bot-polymarket-trump/mercado_activo.json'))
ms = d.get('mercados', [])
for m in ms:
    abierto = not m.get('cerrado', False)
    fin = m.get('fin', '?')
    titulo = m.get('titulo', '?')[:60]
    print(f'  [{\"ABIERTO\" if abierto else \"CERRADO\"}] {titulo}')
    print(f'    fin: {fin}')
    if abierto:
        # calcular horas restantes
        from datetime import datetime, timezone
        try:
            fin_dt = datetime.fromisoformat(fin.replace('Z','+00:00'))
            ahora = datetime.now(timezone.utc)
            rest = (fin_dt - ahora).total_seconds() / 3600
            print(f'    restantes: {rest:.1f}h')
        except Exception as e:
            print(f'    [error parseando fin: {e}]')
"
echo
echo "== 7. ¿Qué señales detectó en la última pasada? =="
tail -100 /opt/polymarket/bot-polymarket-trump/bot_trump.log | grep -iE "senal|señal|cuota|edge|bin|mercado" | head -20
echo
echo "== 8. ¿Por qué no abrió posición si AVG7=23? =="
grep -iE "BLOQUEADO|bloqueado|filter|filtro|threshold" /opt/polymarket/bot-polymarket-trump/bot_trump.log | tail -15
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
