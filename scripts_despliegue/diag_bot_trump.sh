#!/usr/bin/env bash
# diag_bot_trump.sh — diagnóstico completo del bot de Trump
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_bot_trump_${TS}.log

cd /opt/polymarket/bot-polymarket-trump 2>/dev/null || {
    echo "[ERROR] no se puede acceder a /opt/polymarket/bot-polymarket-trump"
    exit 1
}

{
echo "=== DIAG BOT TRUMP — $TS UTC ==="
echo
echo "== 1. ¿Servicio systemd? =="
systemctl status poly-trump.service 2>&1 | head -15
echo
echo "== 2. ¿Procesos activos? =="
ps aux | grep -E "trump" | grep -v grep
echo
echo "== 3. ¿Cron? =="
crontab -l 2>/dev/null | grep -i trump
ls /etc/cron.d/ 2>&1 | grep -i trump
cat /etc/cron.d/poly_trump 2>/dev/null
echo
echo "== 4. Contenido del directorio =="
ls -la /opt/polymarket/bot-polymarket-trump/
echo
echo "== 5. Configuración =="
cat config.json 2>/dev/null
echo
cat config_real.json 2>/dev/null | head -20
echo
echo "== 6. ¿Hay real.json? =="
ls -la real.json 2>&1
echo
echo "== 7. ¿Hay balance/estado? =="
for f in estado_bot.json saldo.json balance.json estado.json real.json resultados.json; do
    if [ -f "$f" ]; then
        echo "--- $f ---"
        cat "$f"
        echo
    fi
done
echo
echo "== 8. bot.py / bot principal =="
ls -la *.py | head -20
echo
echo "== 9. Log del bot =="
ls -la *.log 2>/dev/null
for LOGFILE in bot.log trump.log diario.log; do
    if [ -f "$LOGFILE" ]; then
        echo "--- $LOGFILE (últimas 30 líneas) ---"
        tail -30 "$LOGFILE"
        echo
    fi
done
echo
echo "== 10. Excel historial =="
for XLSX in *.xlsx; do
    if [ -f "$XLSX" ]; then
        echo "--- $XLSX ---"
        python3 -c "
from openpyxl import load_workbook
try:
    wb = load_workbook('$XLSX')
    print(f'hojas: {wb.sheetnames}')
    ws = wb['Operaciones'] if 'Operaciones' in wb.sheetnames else wb.active
    print(f'{ws.max_row} filas')
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 4:
            continue
        if row and any(row):
            print(f'  fila {i+1}: {row}')
except Exception as e:
    print(f'[ERROR] {e}')
"
    fi
done
echo
echo "== 11. Servicio poly-trump.service contenido =="
cat /etc/systemd/system/poly-trump.service 2>&1
echo
echo "== 12. ¿Cuánto tiempo lleva activo? =="
systemctl show poly-trump.service --property=ActiveEnterTimestamp,ActiveState,MainPID 2>&1
echo
echo "== 13. ¿Hay logs en /var/log/ ? =="
ls -la /var/log/poly-trump* 2>&1
tail -30 /var/log/poly-trump.log 2>/dev/null
echo
echo "== 14. mercado_activo.json y CSV =="
ls -la mercado_activo.json datos_trump.csv 2>&1
python3 -c "
import json
try:
    d = json.load(open('mercado_activo.json'))
    print(f'mercados: {len(d.get(\"mercados\",[]))}')
    for m in d.get('mercados',[])[:5]:
        print(f'  {m.get(\"titulo\",\"?\")[:50]}')
except Exception as e:
    print(f'[ERROR] {e}')
"
echo
echo "== 15. ¿Qué está escupiendo el servicio? journalctl últimas 50 líneas =="
journalctl -u poly-trump.service -n 50 --no-pager 2>&1 | tail -50
echo
echo "== 16. ¿Errores? =="
journalctl -u poly-trump.service --since '2026-09-01' --no-pager 2>&1 | grep -iE "error|fail|exception|traceback" | tail -20
} > "$LOG" 2>&1

cat "$LOG"

python3 -c "
import base64, json, urllib.request
tok = open('/opt/polymarket/.gh_token').read().strip()
with open('$LOG','rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = '$(basename $LOG)'
p = {'message':f'diag: {name}','branch':'diag-public','content':b64}
req = urllib.request.urlopen(urllib.request.Request(
    f'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/{name}',
    data=json.dumps(p).encode(),
    headers={'Authorization':f'token {tok}','Content-Type':'application/json','Accept':'application/vnd.github.v3+json'},
    method='PUT'), timeout=30)
print('Publicado:', json.loads(req.read())['content']['path'])
"
