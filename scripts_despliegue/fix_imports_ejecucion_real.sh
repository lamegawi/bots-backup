#!/usr/bin/env bash
# fix_imports_ejecucion_real.sh — corrige imports de py_clob_client y reintenta
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/fix_imports_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== FIX IMPORTS PY_CLOB_CLIENT — $TS UTC ==="
echo
echo "== 1. ¿Qué versión de py_clob_client está? =="
python3 -c "import py_clob_client; print('path:', py_clob_client.__file__)"
echo
echo "== 2. ¿Qué submódulos tiene? =="
python3 -c "
import pkgutil, py_clob_client
mods = [m.name for m in pkgutil.iter_modules(py_clob_client.__path__)]
print(f'módulos: {mods}')
"
echo
echo "== 3. ¿Dónde está OrderArgs? =="
python3 -c "
import py_clob_client
import os
# buscar OrderArgs en cualquier submódulo
for root, dirs, files in os.walk(os.path.dirname(py_clob_client.__file__)):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            try:
                txt = open(p).read()
                if 'class OrderArgs' in txt or 'OrderArgs =' in txt:
                    print(f'encontrado en: {p}')
            except: pass
"
echo
echo "== 4. Backup y corrección bot_semanal.py =="
cp "$NEW_DIR/bot_semanal.py" "$NEW_DIR/bot_semanal.py.bak_imp_${TS}"
echo "backup: bot_semanal.py.bak_imp_${TS}"
echo
echo "== 5. Cambiar imports =="
python3 <<'PYEOF'
p = '/opt/polymarket/bot-polymarket-elon-semanal/bot_semanal.py'
with open(p) as f: t = f.read()

# viejo: from py_clob_client.order_args import OrderArgs
# nuevo: OrderArgs puede estar en py_clob_client directamente
old_imports = """        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.order_args import OrderArgs"""
new_imports = """        try:
            from py_clob_client.client import ClobClient
            try:
                from py_clob_client.order_args import OrderArgs
            except ImportError:
                from py_clob_client.clob_types import OrderArgs"""

if old_imports in t:
    t = t.replace(old_imports, new_imports)
    print('imports parcheados')
else:
    print('NO encontrado el patron, buscando variantes')
    # buscar cualquier 'order_args'
    import re
    t = re.sub(r'from py_clob_client\.order_args import.*?OrderArgs',
               'try:\n                from py_clob_client.order_args import OrderArgs\nexcept ImportError:\n                from py_clob_client.clob_types import OrderArgs',
               t)
    print('regex aplicado')

with open(p, 'w') as f: f.write(t)
PYEOF
echo
echo "== 6. Verificar imports =="
grep -n "from py_clob_client" "$NEW_DIR/bot_semanal.py"
echo
echo "== 7. Probar import manualmente =="
cd "$NEW_DIR"
python3 -c "
try:
    from py_clob_client.client import ClobClient
    print('  ✅ ClobClient')
    try:
        from py_clob_client.order_args import OrderArgs
        print('  ✅ OrderArgs (order_args)')
    except ImportError:
        from py_clob_client.clob_types import OrderArgs
        print('  ✅ OrderArgs (clob_types)')
except Exception as e:
    print(f'  ❌ ERROR: {e}')
"
echo
echo "== 8. Validar =="
python3 -m py_compile "$NEW_DIR/bot_semanal.py" 2>&1 && echo "  compila OK"
echo
echo "== 9. Probar pasada única =="
timeout 30 python3 bot_semanal.py 2>&1 | tail -25
echo
echo "== 10. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 11. Log final =="
journalctl -u poly-elon-semanal.service -n 15 --no-pager 2>&1 | tail -12
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/fix_imports_*.log'))
LOG = logs[-1] if logs else '/tmp/fix_imports.log'
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
