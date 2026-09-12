#!/usr/bin/env bash
# corregir_signer_y_ejecutar.sh — usar signer.address en lugar de get_address
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/corregir_signer_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== CORREGIR SIGNER Y EJECUTAR — ${TS} UTC ==="
echo
echo "== 1. Ver signer.address =="
python3 -c "
from py_clob_client.signer import Signer
signer = Signer('0x5a140fd5482dd565f6abe8ddd100b63fe451bff399be5609e56a0cfafc888af3', 137)
print(f'signer.address: {signer.address}')
print(f'tipo: {type(signer.address)}')
"
echo
echo "== 2. Backup bot_semanal.py =="
cp "$NEW_DIR/bot_semanal.py" "$NEW_DIR/bot_semanal.py.bak_sign_${TS}"
echo "backup: bot_semanal.py.bak_sign_${TS}"
echo
echo "== 3. Aplicar corrección =="
python3 <<'PYEOF'
p = '/opt/polymarket/bot-polymarket-elon-semanal/bot_semanal.py'
with open(p) as f:
    t = f.read()

# Cambiar signer.get_address() a signer.address
old = "addr = client.get_address()"
new = "addr = client.address  # en v0.34.6 el atributo es .address, no .get_address()"

if old in t:
    t = t.replace(old, new)
    print('  ✅ reemplazado get_address -> .address')
else:
    print('  no se encontró el patrón exacto')

# También añadir un chequeo previo
extra_check = """        try_ejecutar_orden(mejor, estado, m)"""
if extra_check in t:
    # añadir print antes
    t = t.replace(extra_check, """        log(f"   🔐 intentando ejecutar orden con proxy...")
            try_ejecutar_orden(mejor, estado, m)""")
    print('  ✅ log añadido antes de ejecutar')

with open(p, 'w') as f:
    f.write(t)
PYEOF
echo
echo "== 4. Validar =="
python3 -m py_compile "$NEW_DIR/bot_semanal.py" 2>&1 && echo "  compila OK"
echo
echo "== 5. Borrar caches =="
find "$NEW_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo "  ✅ caches borrados"
echo
echo "== 6. Probar pasada única =="
cd "$NEW_DIR"
timeout 30 python3 bot_semanal.py 2>&1 | tail -25
echo
echo "== 7. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 8. Verificar log =="
journalctl -u poly-elon-semanal.service -n 20 --no-pager 2>&1 | tail -15
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
