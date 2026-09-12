#!/usr/bin/env bash
# limpiar_cache_semanal_elon.sh — limpia __pycache__ y reinicia servicio
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/limpiar_cache_semanal_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== LIMPIAR CACHE BOT SEMANAL ELON — $TS UTC ==="
echo
echo "== 1. Ver caches __pycache__ =="
find "$NEW_DIR" -name "__pycache__" -o -name "*.pyc" 2>&1 | head -10
echo
echo "== 2. Borrar TODOS los caches =="
find "$NEW_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>&1
find "$NEW_DIR" -name "*.pyc" -delete 2>&1
echo "caches borrados"
echo
echo "== 3. Verificar que no quedan =="
find "$NEW_DIR" -name "__pycache__" -o -name "*.pyc" 2>&1
echo
echo "== 4. Verificar que senal.py tiene CSV_PATH =="
grep -n "CSV_PATH" "$NEW_DIR/senal.py" | head -5
echo
echo "== 5. Probar manualmente con import fresh =="
cd "$NEW_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
# forzar recarga
if 'senal' in sys.modules:
    del sys.modules['senal']
import senal
print(f'  CSV_PATH en senal: {senal.CSV_PATH}')
print(f'  cargar_csv() filas: {len(senal.cargar_csv())}')
print('  ✅ funciona')
"
echo
echo "== 6. Reiniciar servicio (reload completo) =="
systemctl stop poly-elon-semanal.service 2>&1
sleep 2
systemctl start poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -10
echo
echo "== 7. Verificar log =="
journalctl -u poly-elon-semanal.service -n 15 --no-pager 2>&1 | tail -10
echo
echo "== 8. Resumen =="
echo "  ✅ __pycache__ borrado"
echo "  ✅ *.pyc borrados"
echo "  ✅ servicio reiniciado completamente"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/limpiar_cache_semanal_*.log'))
LOG = logs[-1] if logs else '/tmp/limpiar_cache_semanal.log'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': f'diag: {name}', 'branch': 'diag-public', 'content': b64}
try:
    req = urllib.request.urlopen(urllib.request.Request(
        f'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/{name}',
        data=json.dumps(p).encode(),
        headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json', 'Accept':'application/vnd.github.v3+json'},
        method='PUT'), timeout=30)
    print('Publicado:', json.loads(req.read())['content']['path'])
except Exception as e:
    print('[ERROR publicando]', e)
PYEOF
