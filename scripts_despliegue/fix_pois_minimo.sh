#!/usr/bin/env bash
# fix_pois_minimo.sh — versión mínima del fix de poisson_cdf
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/fix_pois_min_${TS}.log
NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== FIX poisson MINIMO — $TS UTC ==="
echo
echo "== poisson_cdf ANTES =="
grep -nA5 "def poisson_cdf" "$NEW_DIR/senal.py" | head -10
echo

# Backup
cp "$NEW_DIR/senal.py" "$NEW_DIR/senal.py.bak_min_${TS}"

# Fix simple con python inline (sin heredoc complejo)
python3 -c "
p = '$NEW_DIR/senal.py'
with open(p) as f: t = f.read()
old = '    k = int(k)  # aceptar floats del JSON\n    s = math.exp(-lam)\n    cdf = s\n    for i in range(1, k + 1):\n        s *= lam / i\n        cdf += s\n    return clamp(cdf, 0, 1)'
new = '''    if k is None or (isinstance(k, float) and (k != k or k == float('inf'))): return 1.0
    try: k = int(k)
    except (ValueError, OverflowError): return 1.0
    if k < 0: return 0.0
    if k > 1000: return 1.0
    s = math.exp(-lam)
    cdf = s
    for i in range(1, k + 1):
        s *= lam / i
        cdf += s
    return clamp(cdf, 0, 1)'''
if old in t:
    t = t.replace(old, new)
    print('poisson_cdf FIXED')
else:
    print('NO encontrado - intentando otra forma')
    # Si el formato es ligeramente diferente
    import re
    m = re.search(r'(    k = int\(k\)[^d]*?return clamp\(cdf, 0, 1\))', t, re.DOTALL)
    if m:
        t = t[:m.start()] + '    if k is None or (isinstance(k, float) and (k != k or k == float(\"inf\"))): return 1.0\n    try: k = int(k)\n    except (ValueError, OverflowError): return 1.0\n    if k < 0: return 0.0\n    if k > 1000: return 1.0\n    s = math.exp(-lam)\n    cdf = s\n    for i in range(1, k + 1):\n        s *= lam / i\n        cdf += s\n    return clamp(cdf, 0, 1)' + t[m.end():]
        print('FIXED via regex')
with open(p, 'w') as f: f.write(t)
"

echo
echo "== poisson_cdf DESPUES =="
grep -nA12 "def poisson_cdf" "$NEW_DIR/senal.py" | head -15
echo

# Compilar
python3 -m py_compile "$NEW_DIR/senal.py" 2>&1 && echo "compila OK"

# Borrar caches
find "$NEW_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

# Test
cd "$NEW_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
if 'senal' in sys.modules: del sys.modules['senal']
import senal
print(f'test p_bin(120, 139, 150): {senal.p_bin(120, 139, 150):.4f}')
print(f'test p_bin(120, inf, 150): {senal.p_bin(120, float(\"inf\"), 150):.4f}')
p = senal.p_bin(120, 139, 150)
d = senal.decidir_bin(p, 0.043, 22.99, 1.05)
print(f'test decision: {d}')
"

echo
echo "== Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 3
systemctl status poly-elon-semanal.service 2>&1 | head -5
echo
echo "== Log final =="
journalctl -u poly-elon-semanal.service -n 8 --no-pager 2>&1 | tail -6
} > "$LOG" 2>&1

cat "$LOG"

# publicar con código más simple
python3 -c "
import base64, json, urllib.request
LOG = '$LOG'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
import os
name = os.path.basename(LOG)
p = {'message': f'diag: {name}', 'branch': 'diag-public', 'content': b64}
try:
    req = urllib.request.urlopen(urllib.request.Request(
        'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/' + name,
        data=json.dumps(p).encode(),
        headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
        method='PUT'), timeout=30)
    print('Publicado:', json.loads(req.read())['content']['path'])
except Exception as e:
    print('ERROR:', e)
"
