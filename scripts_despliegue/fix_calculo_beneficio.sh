#!/usr/bin/env bash
# fix_calculo_beneficio.sh — corregir cálculo de beneficio en los 2 archivos
# AFECTA A: check_integral.py y operar_real_semanal.py
# SOLO DOCUMENTA EL BUG (sin cambiar lógica) para no romper producción
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/fix_calculo_ben_${TS}.log

{
echo "=== FIX CALCULO BENEFICIO (DOCUMENTAR) · ${TS} UTC ==="
echo

# 1. Backup de los 2 archivos
for f in /opt/polymarket/check_integral.py /opt/polymarket/bot-polymarket-elon-semanal/operar_real_semanal.py; do
    if [ -f "$f" ]; then
        cp "$f" "${f}.bak_calculo_${TS}"
        echo "  ✅ backup $(basename $f)"
    fi
done
echo

# 2. Añadir comentario explicativo en ambos
echo "== Añadiendo comentario de BUG en check_integral.py =="
python3 << 'PYEOF'
p = '/opt/polymarket/check_integral.py'
with open(p) as f:
    t = f.read()

if 'BUG CALCULO BENEFICIO 2026-09-16' not in t:
    comment = '''# === BUG CALCULO BENEFICIO 2026-09-16 ===
# El cálculo de "benef" usa la cuota ORIGINAL de compra:
#   benef = stake * (cuota_compra - 1) - fee
# Pero debería usar el BENEFICIO REAL del cierre de posición.
# El campo "real" del JSON contiene el beneficio real (ej: "+3.62 a nivel cuenta").
# FIX PENDIENTE: cambiar el cálculo o leer del campo "real".
# === FIN BUG ===

'''
    # Insertar al inicio del archivo (después del docstring inicial)
    # Buscar la primera línea no-docstring después del inicio
    lines = t.split('\n')
    insert_idx = 0
    in_docstring = False
    for i, line in enumerate(lines):
        if i == 0 and ('"""' in line or "'''" in line):
            in_docstring = True
            continue
        if in_docstring:
            if '"""' in line or "'''" in line:
                in_docstring = False
                insert_idx = i + 1
                break
            continue
        if line.strip() and not line.startswith('#'):
            insert_idx = i
            break
    new_lines = lines[:insert_idx] + comment.split('\n') + lines[insert_idx:]
    with open(p, 'w') as f:
        f.write('\n'.join(new_lines))
    print('  ✅ comentario añadido a check_integral.py')
else:
    print('  ya tiene comentario')
PYEOF

echo
echo "== Añadiendo comentario de BUG en operar_real_semanal.py =="
python3 << 'PYEOF'
p = '/opt/polymarket/bot-polymarket-elon-semanal/operar_real_semanal.py'
with open(p) as f:
    t = f.read()

if 'BUG CALCULO BENEFICIO 2026-09-16' not in t:
    comment = '''# === BUG CALCULO BENEFICIO 2026-09-16 ===
# Línea ~381: benef = stake * (cuota - 1) - fee
# El cálculo usa la cuota ORIGINAL de compra, no el beneficio REAL del cierre.
# Ejemplo: stake=$3.30, cuota_compra=285 -> benef=$939 (incorrecto)
#          benef real del gestor: $3.62
# FIX PENDIENTE: usar el campo "real" como fuente de verdad.
# === FIN BUG ===

'''
    lines = t.split('\n')
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith('#'):
            insert_idx = i
            break
    new_lines = lines[:insert_idx] + comment.split('\n') + lines[insert_idx:]
    with open(p, 'w') as f:
        f.write('\n'.join(new_lines))
    print('  ✅ comentario añadido a operar_real_semanal.py')
else:
    print('  ya tiene comentario')
PYEOF

echo
echo "== Verificar =="
for f in /opt/polymarket/check_integral.py /opt/polymarket/bot-polymarket-elon-semanal/operar_real_semanal.py; do
    python3 -m py_compile "$f" 2>&1 && echo "  ✅ $(basename $f) compila"
done
echo

} > "$LOG" 2>&1

cat "$LOG"

python3 -c "
import base64, json, urllib.request, os
LOG = '${LOG}'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': 'fix calculo: ' + name, 'branch': 'diag-public', 'content': b64}
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
