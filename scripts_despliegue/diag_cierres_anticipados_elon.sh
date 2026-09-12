#!/usr/bin/env bash
# diag_cierres_anticipados_elon.sh — analiza cierres anticipados y ops
# de la ventana 4-11 sept que acaba de cerrar
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_cierres_anticipados_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== DIAG CIERRES ANTICIPADOS 4-11 SEPT — $TS UTC ==="
echo
echo "== 1. EXCEL HISTORIAL COMPLETO =="
python3 -c "
from openpyxl import load_workbook
wb = load_workbook('Historial_Operaciones.xlsx')
print(f'hojas: {wb.sheetnames}')
ws = wb['Operaciones']
print(f'Operaciones: {ws.max_row} filas')
print()
print('--- todas las ops con detalle ---')
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
echo "== 2. operar_real.py — funciones de cierre =="
grep -nE "cerrar|close|resolver|exit|anticipad" operar_real.py 2>/dev/null | head -20
echo
echo "== 3. ¿hay lógica de 'cierre anticipado'? =="
grep -nE "tiempo_rest|horas_rest|min_rest|antes_de_cierre|umbral_cierre|cerrar_si" operar_real.py senal_vivo.py 2>/dev/null | head -20
echo
echo "== 4. POSICIÓN CERRADA EN CLOB 4-11 =="
python3 -c "
import urllib.request, json
url = 'https://data-api.polymarket.com/positions?user=0xb0E148FEb4bE59fD617c8Ad6ce5Cf2b5f0BB2Ae1'
try:
    d = json.loads(urllib.request.urlopen(url, timeout=20).read())
    elon_4_11 = [p for p in d if 'elon' in p.get('title','').lower() and ('september-4' in p.get('title','').lower() or 'september_4' in p.get('title','').lower())]
    print(f'posiciones Elon 4-11 sept: {len(elon_4_11)}')
    for p in elon_4_11:
        print(f'  {p.get(\"title\",\"?\")[:60]}')
        print(f'    size={p.get(\"size\",0)} avg={p.get(\"avgPrice\",0)} cur={p.get(\"curPrice\",0)} pnl={p.get(\"pnl\",0)}')
        print(f'    status: {p.get(\"status\", \"?\")} resolvedBy: {p.get(\"resolvedBy\", \"?\")}')
except Exception as e:
    print(f'  [ERROR] {e}')
"
echo
echo "== 5. ESTADO BOT ACTUAL =="
python3 -c "
import json, os
for f in ['real.json', 'estado_bot.json']:
    if os.path.exists(f):
        d = json.load(open(f))
        if 'saldo' in d:
            print(f'{f}: saldo={d.get(\"saldo\")} paso={d.get(\"paso\")} activa={d.get(\"activa\",\"ninguna\")} historial={len(d.get(\"historial\",[]))}')
        else:
            print(f'{f}: {d}')
"
echo
echo "== 6. BOT LOG: últimas líneas con 'cerrada'/'resuelta' =="
tail -200 bot.log | grep -iE "cerrada|resuelt|vendida|exit" | tail -15
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
