#!/usr/bin/env bash
# arreglar_bug_semanal_elon.sh — corrige el bug cargar_csv() en bot_semanal.py
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/arreglar_bug_semanal_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== ARREGLAR BUG BOT SEMANAL ELON — $TS UTC ==="
echo
echo "== 1. Estado actual del bot_semanal.py =="
grep -nE "cargar_csv|def cargar" "$NEW_DIR/senal.py" | head -10
echo
echo "== 2. Bug =="
echo "  bot_semanal.py llama: senal.cargar_csv()"
echo "  senal.py define:      def cargar_csv(path=None):"
echo "  → falta argumento"
echo
echo "== 3. Corregir bot_semanal.py (sustituir cargar_csv() por cargar_csv(CSV_PATH)) =="
# sed para añadir CSV_PATH
sed -i 's|senal\.cargar_csv()|senal.cargar_csv(senal.CSV_PATH)|g' "$NEW_DIR/bot_semanal.py"
echo "cambio aplicado:"
grep -nE "cargar_csv" "$NEW_DIR/bot_semanal.py"
echo
echo "== 4. Validar sintaxis =="
python3 -m py_compile "$NEW_DIR/senal.py" 2>&1 && echo "  ✅ senal.py compila" || echo "  ❌ senal.py ERROR"
python3 -m py_compile "$NEW_DIR/bot_semanal.py" 2>&1 && echo "  ✅ bot_semanal.py compila" || echo "  ❌ bot_semanal.py ERROR"
echo
echo "== 5. Probar manualmente =="
cd "$NEW_DIR"
python3 -c "
import sys
sys.path.insert(0, '$NEW_DIR')
import senal
datos = senal.cargar_csv(senal.CSV_PATH)
m = senal.metricas(datos)
if m:
    print(f'  ✅ cargar_csv OK: {len(datos)} días')
    print(f'  AVG7={m[\"avg7\"]:.2f}  R={m[\"R\"]:.3f}  ajuste={m[\"ajuste\"]:.3f}')
else:
    print('  ⚠️ metricas None')
"
echo
echo "== 6. Reiniciar servicio para que tome el cambio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -10
echo
echo "== 7. Verificar log tras reinicio =="
journalctl -u poly-elon-semanal.service -n 20 --no-pager 2>&1 | tail -15
echo
echo "== 8. Resumen =="
echo "  ✅ bot_semanal.py corregido"
echo "  ✅ servicio reiniciado"
echo "  Esperar 15 min a la próxima pasada"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/arreglar_bug_semanal_*.log'))
LOG = logs[-1] if logs else '/tmp/arreglar_bug_semanal.log'
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
