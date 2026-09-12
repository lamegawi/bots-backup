#!/usr/bin/env bash
# fix_poisson_overflow.sh — maneja k infinito o muy grande en poisson_cdf
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/fix_pois_over_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== FIX poisson_cdf OVERFLOW — $TS UTC ==="
echo
echo "== 1. Ver p_bin actual =="
grep -nA3 "def p_bin" "$NEW_DIR/senal.py"
echo
echo "== 2. Aplicar fix (manejar k = inf o muy grande) =="
python3 <<'PYEOF'
path = '/opt/polymarket/bot-polymarket-elon-semanal/senal.py'
with open(path) as f:
    txt = f.read()

old = '''def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    k = int(k)  # aceptar floats del JSON
    s = math.exp(-lam)
    cdf = s
    for i in range(1, k + 1):
        s *= lam / i
        cdf += s
    return clamp(cdf, 0, 1)'''

new = '''def poisson_cdf(k, lam):
    """P(X <= k) con Poisson de media lam. Maneja k=inf, None, NaN."""
    if lam <= 0:
        return 1.0
    if k is None or (isinstance(k, float) and (k != k or k == float('inf'))):
        return 1.0
    try:
        k = int(k)
    except (ValueError, OverflowError):
        return 1.0
    if k < 0:
        return 0.0
    if k > 1000:
        return 1.0
    s = math.exp(-lam)
    cdf = s
    for i in range(1, k + 1):
        s *= lam / i
        cdf += s
    return clamp(cdf, 0, 1)'''

if old in txt:
    txt = txt.replace(old, new)
    print('  poisson_cdf patched con manejo de overflow')
else:
    print('  patron no encontrado exacto')

with open(path, 'w') as f:
    f.write(txt)
PYEOF
echo
echo "== 3. Verificar =="
grep -nA15 "def poisson_cdf" "$NEW_DIR/senal.py"
echo
echo "== 4. Validar =="
python3 -m py_compile "$NEW_DIR/senal.py" 2>&1 && echo "  compila OK"
echo
echo "== 5. Test unitario (valores extremos) =="
cd "$NEW_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
if 'senal' in sys.modules:
    del sys.modules['senal']
import senal
print(f'  p_bin(120, 139, 150): {senal.p_bin(120, 139, 150):.4f}')
print(f'  p_bin(120, 9999, 150): {senal.p_bin(120, 9999, 150):.4f}')
print(f'  p_bin(120, inf, 150): {senal.p_bin(120, float(\"inf\"), 150):.4f}')
print(f'  p_bin(120, None, 150): {senal.p_bin(120, None, 150):.4f}')
p = senal.p_bin(120, 139, 150)
d = senal.decidir_bin(p, 0.043, 22.99, 1.05)
print(f'  decision bin 120-139 @ 0.043: {d}')
"
echo
echo "== 6. Borrar __pycache__ =="
find "$NEW_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>&1
echo "  caches borrados"
echo
echo "== 7. Probar bot completo =="
timeout 30 python3 bot_semanal.py 2>&1 | head -25
echo
echo "== 8. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 9. Verificar log =="
journalctl -u poly-elon-semanal.service -n 12 --no-pager 2>&1 | tail -10
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/fix_pois_over_*.log'))
LOG = logs[-1] if logs else '/tmp/fix_pois_over.log'
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
