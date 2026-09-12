#!/usr/bin/env bash
# fix_poisson_int.sh — convierte k a int en poisson_cdf
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/fix_poisson_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== FIX poisson_cdf INT — $TS UTC ==="
echo
echo "== 1. Backup =="
cp "$NEW_DIR/senal.py" "$NEW_DIR/senal.py.bak_pois_${TS}"
echo
echo "== 2. Ver poisson_cdf actual =="
grep -nA8 "def poisson_cdf" "$NEW_DIR/senal.py"
echo
echo "== 3. Aplicar fix (int() en k) =="
# Usar python para modificar el archivo de forma robusta
python3 <<'PYEOF'
path = '/opt/polymarket/bot-polymarket-elon-semanal/senal.py'
with open(path) as f:
    txt = f.read()

# Buscar y reemplazar poisson_cdf
old = '''def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    s = math.exp(-lam)
    cdf = s
    for i in range(1, k + 1):
        s *= lam / i
        cdf += s
    return clamp(cdf, 0, 1)'''

new = '''def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    k = int(k)  # aceptar floats del JSON
    s = math.exp(-lam)
    cdf = s
    for i in range(1, k + 1):
        s *= lam / i
        cdf += s
    return clamp(cdf, 0, 1)'''

if old in txt:
    txt = txt.replace(old, new)
    print('  ✅ poisson_cdf fixed')
else:
    print('  ⚠️ patrón no encontrado, probando versión alternativa')
    # versión alternativa (puede haber sido modificada antes)
    import re
    txt = re.sub(
        r'def poisson_cdf\(k, lam\):\s*\n(\s+)if lam <= 0:\s*\n\s+return 1\.0\s*\n(\s+)s = math\.exp\(-lam\)',
        r'def poisson_cdf(k, lam):\n    if lam <= 0:\n        return 1.0\n    k = int(k)  # aceptar floats del JSON\n    s = math.exp(-lam)',
        txt
    )

with open(path, 'w') as f:
    f.write(txt)
PYEOF
echo
echo "== 4. Verificar =="
grep -nA8 "def poisson_cdf" "$NEW_DIR/senal.py"
echo
echo "== 5. Validar =="
python3 -m py_compile "$NEW_DIR/senal.py" 2>&1 && echo "  ✅ compila"
echo
echo "== 6. Test unitario =="
cd "$NEW_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
if 'senal' in sys.modules:
    del sys.modules['senal']
import senal
# test con floats
p1 = senal.p_bin(120.0, 139.0, 150.0)
print(f'  p_bin(120, 139, λ=150): {p1:.4f}')
p2 = senal.p_bin(120, 139, 150)
print(f'  p_bin(120, 139, λ=150) int: {p2:.4f}')
# decisión
d = senal.decidir_bin(p1, 0.045, 22.22, 1.05)
print(f'  decision: {d}')
"
echo
echo "== 7. Borrar __pycache__ =="
find "$NEW_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>&1
echo "  ✅ caches borrados"
echo
echo "== 8. Probar bot completo =="
timeout 30 python3 bot_semanal.py 2>&1 | head -30
echo
echo "== 9. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 10. Verificar log =="
journalctl -u poly-elon-semanal.service -n 10 --no-pager 2>&1 | tail -8
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/fix_poisson_*.log'))
LOG = logs[-1] if logs else '/tmp/fix_poisson.log'
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
