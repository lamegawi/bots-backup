#!/usr/bin/env bash
# diag_bot_semanal_v2.sh — diagnóstico completo del bot semanal v2
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_bot_semanal_v2_${TS}.log

cd /opt/polymarket/bot-polymarket-elon-semanal-v2

{
echo "=== DIAG BOT SEMANAL V2 — $TS UTC ==="
echo
echo "== 1. ¿Está corriendo? (systemd / procesos) =="
systemctl status poly-elon-semanal-v2 2>&1 | head -15
ps aux | grep -E "semanal|bot_semanal" | grep -v grep
echo
echo "== 2. ¿Cron del semanal v2? =="
crontab -l 2>/dev/null | grep -i semanal
ls /etc/cron.d/ 2>&1 | head
cat /etc/cron.d/poly_semanal_v2 2>/dev/null
echo
echo "== 3. Última actividad =="
ls -lat *.json *.log *.csv *.xlsx *.py 2>&1 | head -20
echo
echo "== 4. estado_bot_semanal_v2.json =="
cat estado_bot_semanal_v2.json
echo
echo "== 5. config.json =="
cat config.json
echo
echo "== 6. Excel historial Semanal V2 =="
python3 -c "
from openpyxl import load_workbook
wb = load_workbook('Historial_Operaciones_Semanal_V2.xlsx')
print(f'hojas: {wb.sheetnames}')
ws = wb['Operaciones'] if 'Operaciones' in wb.sheetnames else wb.active
print(f'{ws.max_row} filas')
print('--- todas las ops ---')
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i < 2:
        continue
    if row and any(row):
        if len(row) > 13:
            ventana = str(row[3]) if row[3] else ''
            bin_t = str(row[4]) if row[4] else ''
            lado = str(row[5]) if row[5] else ''
            precio = row[6] if row[6] is not None else 0
            resultado = str(row[12]) if row[12] else ''
            beneficio = row[13] if row[13] is not None else 0
            print(f'  {ventana[:35]:<35} | {bin_t:<8} | {lado:<3} | precio={precio} | {resultado} | benef={beneficio}')
"
echo
echo "== 7. avisos_cooldown.json del semanal v2 =="
cat avisos_cooldown.json
echo
echo "== 8. bot_semanal.py: funciones clave =="
grep -nE "^def |cerrar|anticipad|resolver" bot_semanal.py | head -25
echo
echo "== 9. ¿Tiene archivo de balance/estado? =="
ls *.json | head -20
echo
echo "== 10. bot_semanal_v2.log: últimas 30 líneas =="
tail -30 bot_semanal_v2.log
echo
echo "== 11. ¿Qué dice bot_semanal_v2.log sobre errores? =="
grep -iE "error|fail|exception|traceback|stop|kill" bot_semanal_v2.log | tail -20
echo
echo "== 12. ¿Frecuencia de pasadas? =="
grep -c "PASADA COMPLETA\|Pasada completada" bot_semanal_v2.log
echo
echo "== 13. ¿Tiene servicio o solo es manual? =="
find /etc/systemd -name "*semanal*" 2>/dev/null
find /opt/polymarket -name "scraper_cron_semanal*" 2>/dev/null
echo
echo "== 14. ¿Está en repositorio Git? =="
cd /opt/polymarket/bot-polymarket-elon-semanal-v2
git log --oneline -10 2>&1
git status 2>&1 | head -5
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
