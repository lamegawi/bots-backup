#!/usr/bin/env bash
# fix_leer_clave_envfile.sh — leer clave desde /etc/default/poly-elon-semanal (correcto)
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/fix_env_clave_${TS}.log

NEW_DIR=/opt/polymarket/bot-polymarket-elon-semanal

{
echo "=== FIX LEER CLAVE DE ENVFILE — ${TS} UTC ==="
echo
echo "== 1. Ver la clave del envfile =="
ENV_FILE=/etc/default/poly-elon-semanal
grep "POLY_PRIVATE_KEY" "$ENV_FILE"
echo
echo "== 2. Ver config_real.json actual =="
cat "$NEW_DIR/config_real.json"
echo
echo "== 3. Reescribir config_real.json con clave real =="
python3 <<'PYEOF'
import json
new_dir = '/opt/polymarket/bot-polymarket-elon-semanal'
env_file = '/etc/default/poly-elon-semanal'

# leer clave del envfile
key = ''
addr = ''
with open(env_file) as f:
    for line in f:
        line = line.strip()
        if line.startswith('#') or not line:
            continue
        if line.startswith('POLY_PRIVATE_KEY='):
            key = line.split('=', 1)[1].strip().strip('"').strip("'")
            if key.startswith('0x'):
                pass  # ya está bien
            elif all(c in '0123456789abcdefABCDEF' for c in key):
                key = '0x' + key
        elif line.startswith('POLY_WALLET_ADDRESS='):
            addr = line.split('=', 1)[1].strip().strip('"').strip("'")

print(f'  clave leída del envfile: {len(key)} chars')
print(f'  empieza con: {key[:10]}')
print(f'  address: {addr}')

# reescribir config_real.json
p = f'{new_dir}/config_real.json'
cfg = {
    'wallet_private_key': key,
    'wallet_address': addr,
    'signature_type': 1,
    'confirmado': True,
}
with open(p, 'w') as f:
    json.dump(cfg, f, indent=2)
print(f'  ✅ config_real.json reescrito')
PYEOF
cat "$NEW_DIR/config_real.json"
echo
echo "== 4. Verificar clave es válida =="
python3 <<'PYEOF'
import json
from py_clob_client.signer import Signer
from eth_account import Account

p = '/opt/polymarket/bot-polymarket-elon-semanal/config_real.json'
with open(p) as f:
    cfg = json.load(f)

key = cfg['wallet_private_key']
print(f'  longitud: {len(key)}')
print(f'  empieza: {key[:10]}')
print(f'  chars no-hex: {[c for c in key if not c in "0123456789abcdefABCDEFx"]}')

# validar
try:
    acct = Account.from_key(key)
    print(f'  ✅ Account.from_key OK')
    print(f'     address: {acct.address}')
    if acct.address.lower() == cfg['wallet_address'].lower():
        print(f'  ✅ address coincide')
    else:
        print(f'  ❌ NO coincide: {acct.address} vs {cfg["wallet_address"]}')

    signer = Signer(key, 137)
    print(f'  ✅ Signer OK')
except Exception as e:
    print(f'  ❌ ERROR: {e}')
PYEOF
echo
echo "== 5. Probar ClobClient completo con clave correcta =="
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
        signature_type=1,
        funder=cfg['wallet_address'],
    )
    print(f'  ✅ ClobClient creado')
    # probar get_address
    addr = client.get_address()
    print(f'     address: {addr}')
    # probar derive api key
    try:
        creds = client.create_or_derive_api_creds()
        print(f'  ✅ API creds derivadas')
        client.set_api_creds(creds)
        # probar balance
        try:
            bal = client.get_balance_allowance()
            print(f'  💰 balance/allowance: {bal}')
        except Exception as e:
            print(f'  [aviso] no pude leer balance: {e}')
    except Exception as e:
        print(f'  [aviso] no pude derivar API creds: {e}')
except Exception as e:
    print(f'  ❌ ERROR: {e}')
    import traceback
    traceback.print_exc()
PYEOF
echo
echo "== 6. Probar pasada única del bot semanal =="
cd "$NEW_DIR"
timeout 30 python3 bot_semanal.py 2>&1 | tail -25
echo
echo "== 7. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 8. Verificar log =="
journalctl -u poly-elon-semanal.service -n 15 --no-pager 2>&1 | tail -12
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
