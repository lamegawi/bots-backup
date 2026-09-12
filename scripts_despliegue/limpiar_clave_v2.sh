#!/usr/bin/env bash
# limpiar_clave_v2.sh — limpiar la clave privada REAL del config_real.json
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/limpiar_clave_v2_${TS}.log

{
echo "=== LIMPIAR CLAVE V2 — ${TS} UTC ==="
echo
echo "== 1. Estado actual del config_real.json =="
NEW_DIR=/opt/polymarket/bot-polymarket-elon-semanal
if [ -f "$NEW_DIR/config_real.json" ]; then
    cat "$NEW_DIR/config_real.json" | python3 -m json.tool
else
    echo "  ⚠️ no existe config_real.json"
fi
echo
echo "== 2. ¿Qué contiene wallet_private_key? =="
python3 -c "
import json
with open('$NEW_DIR/config_real.json') as f:
    cfg = json.load(f)
key = cfg.get('wallet_private_key', '')
print(f'longitud: {len(key)}')
print(f'repr: {repr(key[:80])}')
print(f'hex bytes: {key.encode(\"utf-8\").hex()[:80]}')
"
echo
echo "== 3. Probar diferentes formas de leer la clave =="
python3 -c "
from py_clob_client.signer import Signer
import json

with open('$NEW_DIR/config_real.json') as f:
    cfg = json.load(f)

key_raw = cfg.get('wallet_private_key', '')
print(f'largo raw: {len(key_raw)}')

# limpieza
key = key_raw.strip()
print(f'después de strip: {len(key)}')
if key.startswith('\"') and key.endswith('\"'):
    key = key[1:-1]
    print(f'después de quitar comillas: {len(key)}')
if key.startswith(\"'\"):
    key = key[1:]
    print(f'después de una comilla: {len(key)}')
if key.endswith(\"'\"):
    key = key[:-1]
if key.startswith('0x'):
    key_clean = key
else:
    key_clean = '0x' + key

print(f'key_clean: {repr(key_clean[:80])}')
print(f'largo final: {len(key_clean)}')
print(f'caracteres no-hex: {[c for c in key_clean if not c in \"0123456789abcdefABCDEFx\"]}')

try:
    signer = Signer(key_clean, 137)
    print(f'✅ signer creado')
except Exception as e:
    print(f'❌ ERROR: {e}')

# alternativa con from_key
try:
    from eth_account import Account
    acct = Account.from_key(key_clean)
    print(f'✅ account creado: {acct.address}')
except Exception as e:
    print(f'❌ ERROR from_key: {e}')
"
echo
echo "== 4. Reescribir config_real.json con clave limpia =="
python3 <<'PYEOF'
import json
p = '/opt/polymarket/bot-polymarket-elon-semanal/config_real.json'
with open(p) as f:
    cfg = json.load(f)

key = cfg.get('wallet_private_key', '')
print(f'  clave actual: {len(key)} chars')
# limpiar
key = key.strip()
if key.startswith('"') and key.endswith('"'):
    key = key[1:-1]
if key.startswith("'"):
    key = key[1:]
if key.endswith("'"):
    key = key[:-1]
# quitar 0x si está, luego poner 0x
if key.startswith('0x'):
    key = key[2:]
if not all(c in '0123456789abcdefABCDEF' for c in key):
    print(f'  ❌ clave contiene chars no-hex: {key}')
else:
    cfg['wallet_private_key'] = '0x' + key
    with open(p, 'w') as f:
        json.dump(cfg, f, indent=2)
    print(f'  ✅ clave reescrita limpia: {len(cfg["wallet_private_key"])} chars')
    print(f'     empieza con: {cfg["wallet_private_key"][:10]}')
PYEOF
echo
echo "== 5. Reescribir bot_semanal.py con clave limpia dentro =="
# Backup
cp "$NEW_DIR/bot_semanal.py" "$NEW_DIR/bot_semanal.py.bak_clave_v2_${TS}"

python3 <<'PYEOF'
p = '/opt/polymarket/bot-polymarket-elon-semanal/bot_semanal.py'
with open(p) as f:
    t = f.read()

# Buscar y reemplazar el patrón de lectura de clave
old = "key=cfg.get('wallet_private_key'),"
new = "key=cfg.get('wallet_private_key', '').strip().strip('\"').strip(\"'\").lstrip('0x') and ('0x' + cfg.get('wallet_private_key', '').strip().strip('\"').strip(\"'\").lstrip('0x')),"

if old in t:
    t = t.replace(old, new)
    print('  ✅ limpiada lectura de clave')
else:
    print('  ⚠️ no se encontró el patrón exacto')
    # alternativa: búsqueda regex
    import re
    pattern = r"key=cfg\.get\('wallet_private_key'\)"
    if re.search(pattern, t):
        t = re.sub(
            pattern,
            "key='0x' + cfg.get('wallet_private_key', '').strip().strip('\"').strip(\"'\").lstrip('0x')",
            t,
        )
        print('  ✅ limpiada con regex')

with open(p, 'w') as f:
    f.write(t)
PYEOF
echo
echo "== 6. Validar =="
python3 -m py_compile "$NEW_DIR/bot_semanal.py" 2>&1 && echo "  ✅ compila OK"
echo
echo "== 7. Probar pasada única =="
cd "$NEW_DIR"
timeout 30 python3 bot_semanal.py 2>&1 | tail -25
echo
echo "== 8. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 9. Verificar log =="
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
