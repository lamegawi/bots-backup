#!/usr/bin/env bash
# diag_wallet_y_saldo.sh — encontrar la wallet real y sincronizar saldo
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_wallet_${TS}.log

{
echo "=== DIAG WALLET Y SALDO REAL — $TS UTC ==="
echo
echo "== 1. ¿Qué wallet usa CADA bot? =="
echo "--- bot Elon ---"
grep -rE "0x[a-fA-F0-9]{40}|wallet|address|funder" /opt/polymarket/bot-polymarket-elon/config_real.json /opt/polymarket/bot-polymarket-elon/operar_real.py 2>/dev/null | head -10
echo
echo "--- bot Zelenskyy ---"
grep -rE "0x[a-fA-F0-9]{40}|wallet|address|funder" /opt/polymarket/bot-polymarket-zelenskyy/*.py /opt/polymarket/bot-polymarket-zelenskyy/config*.json 2>/dev/null | head -10
echo
echo "--- bot Trump ---"
grep -rE "0x[a-fA-F0-9]{40}|wallet|address|funder" /opt/polymarket/bot-polymarket-trump/*.py /opt/polymarket/bot-polymarket-trump/config*.json 2>/dev/null | head -10
echo
echo "== 2. ¿Qué wallets hay en /opt/polymarket/.polymarket/ ? =="
ls -la /root/.polymarket/ 2>/dev/null
ls -la /opt/polymarket/.polymarket/ 2>/dev/null
cat /root/.polymarket/* 2>/dev/null | head -20
echo
echo "== 3. ¿Hay claves privadas? =="
ls -la /opt/polymarket/*.key /opt/polymarket/*pk* /root/*.key 2>/dev/null
find /opt/polymarket -name "pk_*" -o -name "*.pk" -o -name "private_key" 2>/dev/null | head -10
echo
echo "== 4. Buscar wallet address en TODOS los archivos =="
grep -rhE "0x[a-fA-F0-9]{40}" /opt/polymarket/ --include="*.py" --include="*.json" --include="*.txt" 2>/dev/null | grep -v venv | grep -v node_modules | sort -u | head -20
echo
echo "== 5. Probar otras wallets con el data-api =="
python3 -c "
import urllib.request, json
# wallets candidatas
wallets = [
    '0xb0E148FEb4bE59fD617c8Ad6ce5Cf2b5f0BB2Ae1',  # la que probamos
]
# Buscar en archivos de config
import os, re
for root, dirs, files in os.walk('/opt/polymarket'):
    if 'venv' in root or '__pycache__' in root or '.git' in root:
        continue
    for f in files:
        if f.endswith(('.py','.json','.txt','.env')):
            try:
                txt = open(os.path.join(root, f)).read()
                for m in re.findall(r'0x[a-fA-F0-9]{40}', txt):
                    if m not in wallets and m != '0x' + '0'*40:
                        wallets.append(m)
            except:
                pass
print(f'wallets encontradas: {len(wallets)}')
for w in wallets[:10]:
    url = f'https://data-api.polymarket.com/value?user={w}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        v = d[0].get('value', 0) if isinstance(d, list) and d else d.get('value', 0) if isinstance(d, dict) else 0
        print(f'  {w}: \${v}')
    except Exception as e:
        print(f'  {w}: [ERROR]')
" 2>&1
echo
echo "== 6. ¿El bot de Trump tiene config_real.json? =="
cat /opt/polymarket/bot-polymarket-trump/config_real.json.example 2>&1
echo
ls /opt/polymarket/bot-polymarket-trump/config_real.json 2>&1
echo
echo "== 7. ¿Qué saldo muestra el bot de Zelenskyy? =="
find /opt/polymarket/bot-polymarket-zelenskyy -name "real*.json" -o -name "saldo*.json" 2>/dev/null
python3 -c "
import json, os
for f in os.listdir('/opt/polymarket/bot-polymarket-zelenskyy'):
    if 'json' in f:
        p = f'/opt/polymarket/bot-polymarket-zelenskyy/{f}'
        try:
            d = json.load(open(p))
            if 'saldo' in d or 'bankroll' in d:
                print(f'  {f}: saldo={d.get(\"saldo\")} bankroll={d.get(\"_bankroll_inicial_real\")}')
        except:
            pass
" 2>&1
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
