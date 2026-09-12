#!/usr/bin/env bash
# verificar_senal_actual.sh — ver EXACTAMENTE qué archivo está usando el bot
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/verif_senal_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== VERIFICAR SENAL.PY ACTUAL — $TS UTC ==="
echo
echo "== 1. ¿Qué archivo Python importa el bot? =="
grep -nE "^import |^from " "$NEW_DIR/bot_semanal.py" | head -10
echo
echo "== 2. Hash y contenido actual de senal.py =="
md5sum "$NEW_DIR/senal.py"
wc -l "$NEW_DIR/senal.py"
echo
echo "== 3. ¿Qué funciones tiene? =="
grep -nE "^def |^[A-Z_]+ *=" "$NEW_DIR/senal.py"
echo
echo "== 4. ¿Hay otro senal.py en otro sitio? =="
find /opt/polymarket -name "senal.py" 2>/dev/null
echo
echo "== 5. ¿sys.path incluye NEW_DIR? =="
grep -n "sys.path" "$NEW_DIR/bot_semanal.py"
echo
echo "== 6. ¿Qué ve Python si hace 'import senal' desde NEW_DIR? =="
cd "$NEW_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
import senal
print('sys.path:', sys.path[:3])
print('senal.__file__:', senal.__file__)
print('tiene CSV_PATH?', hasattr(senal, 'CSV_PATH'))
print('dir(senal)[:10]:', [x for x in dir(senal) if not x.startswith('_')][:10])
"
echo
echo "== 7. ¿Qué ve el proceso en ejecución? =="
PID=$(systemctl show poly-elon-semanal.service --property=MainPID --value)
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    echo "PID: $PID"
    echo "  working dir:"
    readlink /proc/$PID/cwd 2>/dev/null
    echo "  binary:"
    readlink /proc/$PID/exe 2>/dev/null
    echo "  argumentos:"
    tr '\0' ' ' < /proc/$PID/cmdline 2>/dev/null
    echo
    echo "  entorno PYTHONPATH:"
    tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | grep -i "PYTHON"
fi
echo
echo "== 8. ¿El servicio sigue vivo? =="
systemctl status poly-elon-semanal.service 2>&1 | head -5
echo
echo "== 9. Última línea de journal =="
journalctl -u poly-elon-semanal.service -n 5 --no-pager 2>&1 | tail -5
echo
echo "== 10. Conclusión =="
echo "  El bot importa 'senal' pero el módulo no tiene 'CSV_PATH'"
echo "  Esto indica que el archivo que se está importando NO es el actual"
echo "  Posibles causas:"
echo "    a) Hay otro senal.py en el path"
echo "    b) El servicio está usando un working directory diferente"
echo "    c) Hay caché en algún sitio"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/verif_senal_*.log'))
LOG = logs[-1] if logs else '/tmp/verif_senal.log'
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
