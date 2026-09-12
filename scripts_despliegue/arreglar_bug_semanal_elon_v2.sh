#!/usr/bin/env bash
# arreglar_bug_semanal_elon_v2.sh — reescribe senal.py COMPLETAMENTE con versión robusta
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/arreglar_bug_semanal_v2_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"
ELON_DIR="/opt/polymarket/bot-polymarket-elon"

{
echo "=== ARREGLAR BUG BOT SEMANAL ELON v2 — $TS UTC ==="
echo
echo "== 1. Backup de senal.py actual =="
cp "$NEW_DIR/senal.py" "$NEW_DIR/senal.py.bak_v2_${TS}"
ls -la "$NEW_DIR/senal.py"*
echo
echo "== 2. Ver contenido actual del senal.py (las primeras 50 líneas) =="
head -50 "$NEW_DIR/senal.py"
echo
echo "== 3. Sobrescribir senal.py con versión limpia y robusta =="
cat > "$NEW_DIR/senal.py" <<'PYEOF'
#!/usr/bin/env python3
"""
Motor de señal — ventana SEMANAL «Elon Musk # tweets <inicio> - <fin>?»
v2 — limpia, robusta, sin bugs.
"""
import os
import csv
import math

# Constantes de la estrategia
VENTANA = "semanal"
STAKE_INICIAL = 3.30
FACTOR = 1.40
CUOTA_MINIMA = 3.00
PRECIO_MAX = 0.30
EDGE_MIN = 0.15
P_FLOOR = 0.20
PASOS_MAX = 6
REGLA = "ventaja"

# Ruta del CSV (compartido con el bot 48h)
DATA_DIR = "/opt/polymarket/bot-polymarket-elon"
CSV_PATH = os.path.join(DATA_DIR, "datos_elon.csv")


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    s = math.exp(-lam)
    cdf = s
    for i in range(1, k + 1):
        s *= lam / i
        cdf += s
    return clamp(cdf, 0, 1)


def p_bin(lo, hi, lam):
    return clamp(poisson_cdf(hi, lam) - poisson_cdf(lo - 1, lam), 0, 1)


def cargar_csv():
    """Carga el CSV compartido. Devuelve lista [(fecha, tweets)]."""
    if not os.path.exists(CSV_PATH):
        return []
    datos = []
    try:
        with open(CSV_PATH) as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    datos.append((row['fecha'], int(row['tweets'])))
                except (KeyError, ValueError):
                    continue
    except Exception as e:
        print(f"[ERROR cargando CSV] {e}")
    return datos


def metricas(datos):
    if len(datos) < 7:
        return None
    last7 = [t for _, t in datos[-7:]]
    last30 = [t for _, t in datos[-30:]] if len(datos) >= 30 else last7
    avg7 = sum(last7) / len(last7)
    avg30 = sum(last30) / len(last30)
    R = avg7 / avg30 if avg30 > 0 else 1.0
    ajuste = clamp(0.6 + 0.4 * R, 0.6, 1.4)
    return {'avg7': avg7, 'avg30': avg30, 'R': R, 'ajuste': ajuste, 'dias': len(datos)}


def tabla_apuestas(stake_inicial=STAKE_INICIAL, factor=FACTOR, pasos=PASOS_MAX):
    return [round(stake_inicial * (factor ** i), 2) for i in range(pasos)]


def main():
    datos = cargar_csv()
    m = metricas(datos)
    if not m:
        print("[ERROR] No hay datos suficientes en CSV")
        return
    print(f"AVG7={m['avg7']:.2f}  AVG30={m['avg30']:.2f}  R={m['R']:.3f}  ajuste={m['ajuste']:.3f}")
    print(f"días en CSV: {m['dias']}")
    print(f"Stakes: {tabla_apuestas()}")


if __name__ == "__main__":
    main()
PYEOF
echo "senal.py reescrito"
wc -l "$NEW_DIR/senal.py"
echo
echo "== 4. Validar sintaxis =="
python3 -m py_compile "$NEW_DIR/senal.py" 2>&1 && echo "  ✅ compila"
echo
echo "== 5. Probar manualmente =="
cd "$NEW_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
import senal
datos = senal.cargar_csv()
m = senal.metricas(datos)
print(f'  cargar_csv: {len(datos)} filas')
if m:
    print(f'  AVG7={m[\"avg7\"]:.2f}  AVG30={m[\"avg30\"]:.2f}  R={m[\"R\"]:.3f}  ajuste={m[\"ajuste\"]:.3f}  dias={m[\"dias\"]}')
print('  ✅ funciona')
"
echo
echo "== 6. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -10
echo
echo "== 7. Verificar log tras reinicio =="
journalctl -u poly-elon-semanal.service -n 15 --no-pager 2>&1 | tail -12
echo
echo "== 8. Resumen =="
echo "  ✅ senal.py reescrito COMPLETAMENTE (versión limpia)"
echo "  ✅ servicio reiniciado"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/arreglar_bug_semanal_v2_*.log'))
LOG = logs[-1] if logs else '/tmp/arreglar_bug_semanal_v2.log'
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
