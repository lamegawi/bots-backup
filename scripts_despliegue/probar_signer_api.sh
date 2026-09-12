#!/usr/bin/env bash
# probar_signer_api.sh — descubrir API correcta de Signer en py_clob_client 0.34.6
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/probar_signer_${TS}.log

{
echo "=== PROBAR SIGNER API — ${TS} UTC ==="
echo
echo "== 1. Listar métodos/atributos de Signer =="
python3 -c "
from py_clob_client.signer import Signer
s = Signer
print('Atributos:')
for attr in dir(s):
    if not attr.startswith('_'):
        print(f'  {attr}')
"
echo
echo "== 2. Ver el código fuente de Signer =="
SFILE=$(python3 -c "from py_clob_client.signer import Signer; print(Signer.__module__); import py_clob_client.signer; print(py_clob_client.signer.__file__)")
echo "fichero: $SFILE"
grep -nE "^    def |^class " "$SFILE" 2>&1 | head -20
echo
echo "== 3. Probar firma completa (sin get_address) =="
python3 -c "
from py_clob_client.signer import Signer
key = '0x5a140fd5482dd565f6abe8ddd100b63fe451bff399be5609e56a0cfafc888af3'
try:
    signer = Signer(key, 137)
    print(f'signer creado: {signer}')
    print(f'tipo: {type(signer)}')
    # ver atributos
    print('atributos:')
    for a in dir(signer):
        if not a.startswith('_'):
            print(f'  {a}')
    # intentar firmar algo simple
    msg = b'hello'
    sig = signer.sign(msg)
    print(f'✅ firma: {sig[:30]}...')
except Exception as e:
    print(f'❌ ERROR: {e}')
    import traceback
    traceback.print_exc()
"
echo
echo "== 4. ¿Cómo Zelenskyy usa el Signer? =="
grep -nE "Signer|signer" /opt/polymarket/bot-polymarket-zelenskyy/operar_real_semanal.py 2>/dev/null | head -10
echo
echo "== 5. ¿Cómo Zelenskyy autentica con ClobClient? =="
grep -nA8 "ClobClient(HOST" /opt/polymarket/bot-polymarket-zelenskyy/operar_real_semanal.py 2>/dev/null | head -20
echo
echo "== 6. Probar ClobClient completo con sign =="
python3 -c "
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
import json

key = '0x5a140fd5482dd565f6abe8ddd100b63fe451bff399be5609e56a0cfafc888af3'
addr = '0xb0E1197098E6d427c01720F1631cAD24CE740FA0'

try:
    client = ClobClient(
        'https://clob.polymarket.com',
        key=key,
        chain_id=137,
        signature_type=1,
        funder=addr,
    )
    print(f'✅ cliente creado')
    # ver métodos
    print('métodos públicos:')
    for m in dir(client):
        if not m.startswith('_') and callable(getattr(client, m, None)):
            print(f'  {m}')
except Exception as e:
    print(f'❌ ERROR creando cliente: {e}')
    import traceback
    traceback.print_exc()
"
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
