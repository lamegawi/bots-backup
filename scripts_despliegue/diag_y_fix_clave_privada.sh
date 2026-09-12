#!/usr/bin/env bash
# diag_y_fix_clave_privada.sh — diagnosticar y limpiar clave privada
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_fix_clave_${TS}.log

{
echo "=== DIAG Y FIX CLAVE PRIVADA — ${TS} UTC ==="
echo
echo "== 1. ¿Cómo está la clave en /etc/default/poly-elon-semanal? =="
ENV_FILE=/etc/default/poly-elon-semanal
if [ -f "$ENV_FILE" ]; then
    echo "  contenido completo:"
    cat -A "$ENV_FILE" | head -10
    echo
    echo "  longitud de POLY_PRIVATE_KEY:"
    grep "POLY_PRIVATE_KEY=" "$ENV_FILE" | sed 's/POLY_PRIVATE_KEY=//' | wc -c
fi
echo
echo "== 2. ¿Cómo está en /etc/polymarket.env? =="
if [ -f /etc/polymarket.env ]; then
    grep "POLY_PRIVATE_KEY" /etc/polymarket.env | cat -A | head -5
fi
echo
echo "== 3. ¿Cómo está en /etc/default/poly-zelenskyy? =="
if [ -f /etc/default/poly-zelenskyy ]; then
    grep "POLY_PRIVATE_KEY" /etc/default/poly-zelenskyy | cat -A | head -5
fi
echo
echo "== 4. ¿Cómo está en /etc/default/poly-trump? =="
if [ -f /etc/default/poly-trump ]; then
    grep "POLY_PRIVATE_KEY" /etc/default/poly-trump | cat -A | head -5
fi
echo
echo "== 5. Probar firma con la clave del bot semanal =="
python3 -c "
import os
from py_clob_client.signer import Signer

# leer clave del env file
key = ''
with open('/etc/default/poly-elon-semanal') as f:
    for line in f:
        if line.startswith('POLY_PRIVATE_KEY='):
            key = line.split('=', 1)[1].strip()
            break

print(f'longitud leída: {len(key)}')
print(f'primeros 10 chars: {repr(key[:10])}')
print(f'últimos 5 chars: {repr(key[-5:])}')

# intentar firmar
try:
    signer = Signer(key, 137)
    print(f'✅ signer creado')
    addr = signer.get_address()
    print(f'✅ address: {addr}')
except Exception as e:
    print(f'❌ ERROR: {e}')
"
echo
echo "== 6. ¿Y con la clave de /etc/polymarket.env? =="
python3 -c "
import os
from py_clob_client.signer import Signer

key = ''
with open('/etc/polymarket.env') as f:
    for line in f:
        if line.startswith('POLY_PRIVATE_KEY='):
            key = line.split('=', 1)[1].strip()
            break

print(f'longitud: {len(key)}')
try:
    signer = Signer(key, 137)
    addr = signer.get_address()
    print(f'✅ address: {addr}')
except Exception as e:
    print(f'❌ ERROR: {e}')
"
echo
echo "== 7. Limpiar clave del bot semanal (quitar espacios/saltos) =="
ENV_FILE=/etc/default/poly-elon-semanal
if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "${ENV_FILE}.bak_clave_${TS}"
    # extraer, limpiar, reescribir
    python3 -c "
import re
p = '$ENV_FILE'
with open(p) as f: t = f.read()
# buscar POLY_PRIVATE_KEY=...
m = re.search(r'(POLY_PRIVATE_KEY=\")([0-9a-fA-F]+)(\")', t)
if m:
    print(f'clave actual: {len(m.group(2))} chars hex')
    # reescribir limpiando
    new_t = re.sub(r'(POLY_PRIVATE_KEY=\")[0-9a-fA-F]+(\")', r'\g<1>' + m.group(2) + r'\g<3>', t)
    with open(p, 'w') as f: f.write(new_t)
    print('  ✅ clave limpia (sin espacios/saltos)')
else:
    print('  ⚠️ no se encontró POLY_PRIVATE_KEY=\"...\"')
    # buscar formato sin comillas
    m = re.search(r'(POLY_PRIVATE_KEY=)([^\s]+)', t)
    if m:
        print(f'  encontrada sin comillas: {len(m.group(2))} chars')
        key = m.group(2).strip().strip('\"').strip(\"'\")
        if key.startswith('0x'):
            key = key[2:]
        if all(c in '0123456789abcdefABCDEF' for c in key) and len(key) == 64:
            new_key_line = f'POLY_PRIVATE_KEY=\"0x{key}\"'
            t = re.sub(r'POLY_PRIVATE_KEY=[^\n]+', new_key_line, t)
            with open(p, 'w') as f: f.write(t)
            print('  ✅ clave reescrita con formato limpio')
        else:
            print(f'  ❌ clave NO válida: {key[:20]}...')
"
fi
echo
echo "== 8. Verificar tras limpieza =="
ENV_FILE=/etc/default/poly-elon-semanal
grep "POLY_PRIVATE_KEY" "$ENV_FILE" | cat -A
echo
echo "== 9. Probar firma tras limpieza =="
python3 -c "
from py_clob_client.signer import Signer
key = ''
with open('/etc/default/poly-elon-semanal') as f:
    for line in f:
        if line.startswith('POLY_PRIVATE_KEY='):
            key = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")
            break
print(f'longitud: {len(key)}')
try:
    signer = Signer(key, 137)
    addr = signer.get_address()
    print(f'✅ address: {addr}')
except Exception as e:
    print(f'❌ ERROR: {e}')
"
echo
echo "== 10. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 11. Verificar log =="
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
