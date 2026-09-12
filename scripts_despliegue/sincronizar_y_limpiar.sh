#!/usr/bin/env bash
# sincronizar_y_limpiar.sh — sincronizar saldo + limpiar clave + proteger contra dobles posiciones
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/sinc_y_limp_${TS}.log

NEW_DIR=/opt/polymarket/bot-polymarket-elon-semanal

{
echo "=== SINCRONIZAR Y LIMPIAR — ${TS} UTC ==="
echo
echo "== 1. Sincronizar saldo del bot semanal con el real actual =="
# leer saldo real desde la API
python3 <<'PYEOF'
import json, os

new_dir = '/opt/polymarket/bot-polymarket-elon-semanal'
p = f'{new_dir}/real_semanal.json'
with open(p) as f:
    est = json.load(f)

# leer saldo desde el .env (donde dice $228.45)
# o desde la API pública
import urllib.request
addr = '0xb0E1197098E6d427c01720F1631cAD24CE740FA0'
try:
    url = f'https://data-api.polymarket.com/value?user={addr}'
    req = urllib.request.urlopen(url, timeout=10)
    data = json.loads(req.read())
    # buscar campo de valor
    valor = data.get('value') or data.get('balance') or data.get('usdcBalance')
    print(f'  API valor: ${valor}')
except Exception as e:
    print(f'  no pude leer API: {e}')
    valor = 186.49  # según lo que dijo el bot Trump

print(f'  saldo actual en real_semanal.json: ${est.get("saldo")}')
print(f'  nuevo saldo: ${valor}')
est['saldo'] = valor
with open(p, 'w') as f:
    json.dump(est, f, indent=2)
print(f'  ✅ actualizado a ${valor}')
PYEOF
echo
echo "== 2. Ver posiciones abiertas de TODOS los bots =="
python3 <<'PYEOF'
import json, os, urllib.request

addr = '0xb0E1197098E6d427c01720F1631cAD24CE740FA0'
try:
    url = f'https://data-api.polymarket.com/positions?user={addr}'
    req = urllib.request.urlopen(url, timeout=10)
    pos = json.loads(req.read())
    print(f'  {len(pos)} posiciones activas:')
    for p in pos:
        title = p.get('title', '?')[:60]
        size = p.get('size', 0)
        cur = p.get('currentValue', 0)
        init = p.get('initialValue', 0)
        print(f'   · {title}')
        print(f'     size={size} initial=${init} current=${cur}')
except Exception as e:
    print(f'  ERROR: {e}')
PYEOF
echo
echo "== 3. Backup y limpieza de la clave =="
# Backup
cp "$NEW_DIR/config_real.json" "$NEW_DIR/config_real.json.bak_clavev2_${TS}"
cp "$NEW_DIR/bot_semanal.py" "$NEW_DIR/bot_semanal.py.bak_clavev2_${TS}"
echo "  ✅ backups hechos"
echo
echo "== 4. Limpiar config_real.json =="
python3 <<'PYEOF'
import json, os
p = '/opt/polymarket/bot-polymarket-elon-semanal/config_real.json'
with open(p) as f:
    cfg = json.load(f)

key = cfg.get('wallet_private_key', '')
print(f'  longitud antes: {len(key)}')
# limpieza exhaustiva
key = key.strip()
if key.startswith('"') and key.endswith('"'):
    key = key[1:-1]
if key.startswith("'"):
    key = key[1:]
if key.endswith("'"):
    key = key[:-1]
if key.startswith('0x'):
    key = key[2:]
# verificar
if not all(c in '0123456789abcdefABCDEF' for c in key):
    print(f'  ❌ chars no-hex: {[c for c in key if not c in "0123456789abcdefABCDEF"]}')
else:
    cfg['wallet_private_key'] = '0x' + key
    with open(p, 'w') as f:
        json.dump(cfg, f, indent=2)
    print(f'  ✅ clave limpia: {cfg["wallet_private_key"][:20]}... ({len(cfg["wallet_private_key"])} chars)')
PYEOF
echo
echo "== 5. Probar Signer con la clave limpia =="
python3 <<'PYEOF'
import json
from py_clob_client.signer import Signer

with open('/opt/polymarket/bot-polymarket-elon-semanal/config_real.json') as f:
    cfg = json.load(f)

try:
    signer = Signer(cfg['wallet_private_key'], 137)
    print(f'  ✅ signer creado')
    print(f'     chain_id={signer.get_chain_id()}')
    # el address está en signer.address (método) o signer.account.address
    addr = signer.address() if callable(signer.address) else signer.address
    print(f'     address={addr}')
except Exception as e:
    print(f'  ❌ ERROR: {e}')
PYEOF
echo
echo "== 6. Probar ClobClient completo con clave limpia =="
python3 <<'PYEOF'
import json
from py_clob_client.client import ClobClient

with open('/opt/polymarket/bot-polymarket-elon-semanal/config_real.json') as f:
    cfg = json.load(f)

try:
    client = ClobClient(
        'https://clob.polymarket.com',
        key=cfg['wallet_private_key'],
        chain_id=137,
        signature_type=cfg.get('signature_type', 1),
        funder=cfg.get('wallet_address'),
    )
    print(f'  ✅ cliente creado')
    # probar get_address
    try:
        addr = client.get_address()
        print(f'     address: {addr}')
    except Exception as e:
        print(f'     [aviso] get_address: {e}')
    # probar derive api key
    try:
        creds = client.create_or_derive_api_creds()
        print(f'  ✅ API creds derivadas: {creds}')
        client.set_api_creds(creds)
    except Exception as e:
        print(f'  [aviso] no pude derivar API creds: {e}')
    # probar saldo
    try:
        bal = client.get_balance_allowance()
        print(f'  💰 balance/allowance: {bal}')
    except Exception as e:
        print(f'  [aviso] no pude leer balance: {e}')
except Exception as e:
    print(f'  ❌ ERROR: {e}')
    import traceback
    traceback.print_exc()
PYEOF
echo
echo "== 7. Probar pasada única del bot semanal =="
cd "$NEW_DIR"
timeout 30 python3 bot_semanal.py 2>&1 | tail -30
echo
echo "== 8. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 9. Verificar log =="
journalctl -u poly-elon-semanal.service -n 15 --no-pager 2>&1 | tail -12
echo
echo "== 10. Verificar log Trump =="
journalctl -u poly-trump.service -n 15 --no-pager 2>&1 | tail -12
} > "${LOG}" 2>&1

cat "${LOG}"

# publicar
python3 -c "
import base64, json, urllib.request, os
LOG = '${LOG}'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': 'diag: ' + name, 'branch': 'diag-public', 'content': b64}
try:
    req = urllib.request.urlopen(urllib.request.Request(
        'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/' + name,
        data=json.dumps(p).encode(),
        headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
        method='PUT'), timeout=30)
    print('Publicado:', json.loads(req.read())['content']['path'])
except Exception as e:
    print('ERROR publicando:', e)
"
