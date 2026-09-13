#!/usr/bin/env bash
# upgrade_py_clob_client.sh — actualiza py-clob-client a última versión
# IMPORTANTE: solo afecta a /usr/local/lib/python3.12/dist-packages/py_clob_client/
# NO toca poly-combos-bot (que no usa py-clob-client directamente)

TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/upgrade_pyclob_${TS}.log

{
echo "=== UPGRADE PY-CLOB-CLIENT — ${TS} UTC ==="
echo
echo "== 1. Versión actual =="
pip show py-clob-client 2>&1 | head -5
echo
echo "== 2. Última versión disponible en PyPI =="
pip index versions py-clob-client 2>&1 | head -3 || pip install py-clob-client== 2>&1 | grep -oE "from versions: [^)]+" | head -1
echo
echo "== 3. Backup versión actual =="
CURRENT_VER=$(pip show py-clob-client 2>&1 | grep "^Version:" | awk '{print $2}')
echo "  versión actual: $CURRENT_VER"
if [ -d /usr/local/lib/python3.12/dist-packages/py_clob_client ]; then
    cp -r /usr/local/lib/python3.12/dist-packages/py_clob_client \
          /tmp/py_clob_client_backup_${CURRENT_VER}_${TS}
    echo "  ✅ backup en /tmp/py_clob_client_backup_${CURRENT_VER}_${TS}"
fi
echo
echo "== 4. Instalar última versión estable =="
# Probar primero la última versión
pip install --break-system-packages --upgrade py-clob-client 2>&1 | tail -10
echo
echo "== 5. Verificar nueva versión =="
pip show py-clob-client 2>&1 | head -3
echo
echo "== 6. Probar imports =="
python3 -c "
from py_clob_client.client import ClobClient
print('  ✅ ClobClient OK')
try:
    from py_clob_client.order_args import OrderArgs
    print('  ✅ OrderArgs (order_args) OK')
except ImportError:
    from py_clob_client.clob_types import OrderArgs
    print('  ✅ OrderArgs (clob_types) OK')
"
echo
echo "== 7. Probar ClobClient firma y conexión =="
python3 << 'PYEOF'
import os
from py_clob_client.client import ClobClient

# leer clave del env
key = os.environ.get('POLY_PRIVATE_KEY', '')
if not key:
    # fallback a /etc/default/poly-elon-semanal
    with open('/etc/default/poly-elon-semanal') as f:
        for line in f:
            if line.startswith('POLY_PRIVATE_KEY='):
                key = line.split('=', 1)[1].strip().strip('"').strip("'")
                break

addr = '0xb0E1197098E6d427c01720F1631cAD24CE740FA0'
print(f'  clave len: {len(key)}')

try:
    client = ClobClient(
        'https://clob.polymarket.com',
        key=key,
        chain_id=137,
        signature_type=1,
        funder=addr,
    )
    print('  ✅ ClobClient creado')
    # probar API creds
    try:
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        print('  ✅ API creds OK')
        # probar balance
        try:
            bal = client.get_balance_allowance()
            print(f'  💰 balance: {bal}')
        except Exception as e:
            print(f'  [aviso] balance: {e}')
    except Exception as e:
        print(f'  [aviso] creds: {e}')
except Exception as e:
    print(f'  ❌ ERROR: {e}')
    import traceback
    traceback.print_exc()
PYEOF
echo
echo "== 8. Probar pasada única del bot semanal =="
cd /opt/polymarket/bot-polymarket-elon-semanal
timeout 30 python3 bot_semanal.py 2>&1 | tail -25
echo
echo "== 9. Reiniciar servicio poly-elon-semanal =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 10. Verificar log post-upgrade =="
journalctl -u poly-elon-semanal.service -n 10 --no-pager 2>&1 | tail -15
echo
echo "== 11. Resumen =="
NEW_VER=$(pip show py-clob-client 2>&1 | grep "^Version:" | awk '{print $2}')
echo "  versión anterior: $CURRENT_VER"
echo "  versión nueva:    $NEW_VER"
echo "  backup:           /tmp/py_clob_client_backup_${CURRENT_VER}_${TS}"
echo "  para revertir:    pip install --break-system-packages py-clob-client==${CURRENT_VER}"
} > "${LOG}" 2>&1

cat "${LOG}"

# publicar en diag-public
python3 -c "
import base64, json, urllib.request, os
LOG = '${LOG}'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': 'diag: ' + name, 'branch': 'diag-public', 'content': b64}
req = urllib.request.Request(
    'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/' + name,
    data=json.dumps(p).encode(),
    headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json'},
    method='PUT')
try:
    r = urllib.request.urlopen(req, timeout=30)
    print('Publicado:', json.loads(r.read())['content']['path'])
except Exception as e:
    print('ERROR publicando:', e)
"
