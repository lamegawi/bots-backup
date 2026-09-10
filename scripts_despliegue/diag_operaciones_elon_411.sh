#!/usr/bin/env bash
# diag_operaciones_elon_411.sh — analiza las operaciones del bot de Elon
# en la ventana 4-11 sept que se cerraron y reabrieron sin tiempo
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_operaciones_elon_411_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== DIAG OPERACIONES ELON 4-11 SEPT — $TS UTC ==="
echo
echo "== 1. ESTADO BOT (posiciones activas) =="
python3 -c "
import json
import os
# buscar archivos de estado
for f in ['estado_bot.json', 'posicion.json', 'papel.json', 'operar_real.json']:
    if os.path.exists(f):
        d = json.load(open(f))
        print(f'--- {f} ---')
        if isinstance(d, dict):
            for k, v in d.items():
                if k in ['activa', 'historial', 'posiciones', 'saldo', 'paso']:
                    if isinstance(v, list) and len(v) > 5:
                        print(f'  {k}: <{len(v)} items>')
                    else:
                        print(f'  {k}: {v}')
"
echo
echo "== 2. HISTORIAL DE OPERACIONES (mercado 4-11 sept) =="
python3 -c "
import json
import os
# leer todas las posiciones cerradas
import glob
pos_files = glob.glob('posiciones_cerradas*.json') + glob.glob('historial*.json') + glob.glob('operaciones*.json')
print(f'archivos: {pos_files}')
for f in pos_files:
    print(f'--- {f} ---')
    try:
        d = json.load(open(f))
        if isinstance(d, list):
            for op in d:
                if 'elon' in str(op).lower() and ('4-11' in str(op) or 'september-4' in str(op).lower() or 'september_4' in str(op).lower()):
                    print(f'  {op}')
        else:
            for k, v in d.items():
                if 'elon' in k.lower():
                    print(f'  {k}: {v}')
    except Exception as e:
        print(f'  [ERROR] {e}')
"
echo
echo "== 3. EXCEL HISTORIAL (si existe) =="
ls -la Historial_Operaciones.xlsx 2>/dev/null
if [ -f Historial_Operaciones.xlsx ]; then
  python3 -c "
from openpyxl import load_workbook
wb = load_workbook('Historial_Operaciones.xlsx')
for sh in wb.sheetnames:
    print(f'--- hoja: {sh} ---')
    ws = wb[sh]
    for row in ws.iter_rows(values_only=True):
        if row and any('elon' in str(c).lower() for c in row if c):
            print('  ', row)
"
fi
echo
echo "== 4. bot.log (últimas 100 líneas, filtrar 4-11) =="
tail -200 bot.log 2>/dev/null | grep -iE "4-11|september-4" | head -30
echo
echo "== 5. logs de hoy (todo) =="
date -u +%Y-%m-%d
ls -la /var/log/poly/ 2>/dev/null | head -5
} > "$LOG" 2>&1

cat "$LOG"

# publicar
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
