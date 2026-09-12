#!/usr/bin/env bash
# anadir_decidir_bin_senal.sh — añade decidir_bin() a senal.py
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/anadir_decidir_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== AÑADIR decidir_bin() — $TS UTC ==="
echo
echo "== 1. Backup del senal.py =="
cp "$NEW_DIR/senal.py" "$NEW_DIR/senal.py.bak_dec_${TS}"
echo "backup: $NEW_DIR/senal.py.bak_dec_${TS}"
echo
echo "== 2. Ver funciones actuales =="
grep -nE "^def " "$NEW_DIR/senal.py"
echo
echo "== 3. Añadir decidir_bin() al senal.py =="
# Crear archivo temporal con la nueva función
cat > /tmp/decidir_bin_func.py <<'EOF'

def decidir_bin(p, precio_yes, cuota_yes, cuota_no):
    """Regla 'ventaja' (semanal): p_modelo ≥ precio + EDGE_MIN, con filtros."""
    if not (precio_yes and precio_yes > 0):
        return "PASAR", None, "precio_yes inválido"
    # Regla YES (p_modelo alta, queremos YES)
    if p >= 1 - P_FLOOR and cuota_yes and cuota_yes >= CUOTA_MINIMA and precio_yes <= PRECIO_MAX:
        return "APOSTAR YES", "YES", f"p_modelo {p:.1%} muy alta, cuota {cuota_yes:.2f}"
    # Regla NO (p_modelo baja, queremos NO)
    precio_no = 1 - precio_yes
    if p <= P_FLOOR and cuota_no and cuota_no >= CUOTA_MINIMA and precio_no <= PRECIO_MAX:
        return "APOSTAR NO", "NO", f"p_modelo {p:.1%} muy baja, cuota NO {cuota_no:.2f}"
    # Regla ventaja YES
    vy = p - precio_yes
    if p >= P_FLOOR and vy >= EDGE_MIN and cuota_yes and cuota_yes >= CUOTA_MINIMA and precio_yes <= PRECIO_MAX:
        return "APOSTAR YES", "YES", f"ventaja {vy:.0%}pp, cuota {cuota_yes:.2f} ≥ {CUOTA_MINIMA:.2f}"
    # Regla ventaja NO
    vn = (1 - p) - precio_no
    if p <= 1 - P_FLOOR and vn >= EDGE_MIN and cuota_no and cuota_no >= CUOTA_MINIMA and precio_no <= PRECIO_MAX:
        return "APOSTAR NO", "NO", f"ventaja {vn:.0%}pp, cuota NO {cuota_no:.2f} ≥ {CUOTA_MINIMA:.2f}"
    return "PASAR", None, f"sin ventaja: p={p:.1%}, vy={vy:.0%}pp, vn={vn:.0%}pp"
EOF

# Insertar antes de "def main()"
sed -i '/^def main():/i\
\
def decidir_bin(p, precio_yes, cuota_yes, cuota_no):\
    """Regla '"'"'ventaja'"'"' (semanal): p_modelo ≥ precio + EDGE_MIN, con filtros."""\
    if not (precio_yes and precio_yes > 0):\
        return "PASAR", None, "precio_yes invalido"\
    precio_no = 1 - precio_yes\
    vy = p - precio_yes\
    vn = (1 - p) - precio_no\
    if p >= 1 - P_FLOOR and cuota_yes and cuota_yes >= CUOTA_MINIMA and precio_yes <= PRECIO_MAX:\
        return "APOSTAR YES", "YES", f"p_modelo {p:.1%} muy alta"\
    if p <= P_FLOOR and cuota_no and cuota_no >= CUOTA_MINIMA and precio_no <= PRECIO_MAX:\
        return "APOSTAR NO", "NO", f"p_modelo {p:.1%} muy baja"\
    if p >= P_FLOOR and vy >= EDGE_MIN and cuota_yes and cuota_yes >= CUOTA_MINIMA and precio_yes <= PRECIO_MAX:\
        return "APOSTAR YES", "YES", f"ventaja {vy:.0%}pp"\
    if p <= 1 - P_FLOOR and vn >= EDGE_MIN and cuota_no and cuota_no >= CUOTA_MINIMA and precio_no <= PRECIO_MAX:\
        return "APOSTAR NO", "NO", f"ventaja {vn:.0%}pp"\
    return "PASAR", None, f"sin ventaja suficiente"\
' "$NEW_DIR/senal.py"

echo "decidir_bin() añadido"
echo
echo "== 4. Verificar =="
grep -n "^def " "$NEW_DIR/senal.py"
echo
echo "== 5. Validar sintaxis =="
python3 -m py_compile "$NEW_DIR/senal.py" 2>&1 && echo "  ✅ compila"
echo
echo "== 6. Probar manualmente =="
cd "$NEW_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
if 'senal' in sys.modules:
    del sys.modules['senal']
import senal
print('funciones:', [x for x in dir(senal) if not x.startswith('_') and callable(getattr(senal, x))][:10])
# test decidir_bin
print('test 1 (alta p, sin ventaja):', senal.decidir_bin(0.6, 0.5, 2.0, 2.0))
print('test 2 (alta p, con ventaja):', senal.decidir_bin(0.7, 0.5, 3.5, 2.0))
print('test 3 (baja p, con ventaja):', senal.decidir_bin(0.2, 0.5, 2.0, 6.0))
print('test 4 (sin cuota mín):', senal.decidir_bin(0.7, 0.5, 2.0, 2.0))
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
journalctl -u poly-elon-semanal.service -n 15 --no-pager 2>&1 | tail -10
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/anadir_decidir_*.log'))
LOG = logs[-1] if logs else '/tmp/anadir_decidir.log'
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
