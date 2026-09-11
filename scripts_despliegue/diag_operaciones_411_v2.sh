#!/usr/bin/env bash
# diag_operaciones_411_v2.sh — busca TODAS las operaciones del bot en
# la ventana 4-11 sept, en Excel, en JSON, en logs
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_op_411_v2_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== DIAG OPERACIONES 4-11 v2 — $TS UTC ==="
echo
echo "== 1. TODAS las hojas del Excel =="
python3 -c "
from openpyxl import load_workbook
wb = load_workbook('Historial_Operaciones.xlsx')
print(f'hojas: {wb.sheetnames}')
for sh in wb.sheetnames:
    ws = wb[sh]
    print(f'--- {sh} ({ws.max_row} filas) ---')
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 3 or (row and any('september-4' in str(c).lower() or '4-11' in str(c) for c in row if c)):
            print(f'  fila {i+1}: {row}')
"
echo
echo "== 2. Bot log — buscar 4-11 =="
echo "tamaño bot.log: $(wc -l bot.log)"
grep -iE "4-11|september-4|sept-4|sep-4" bot.log 2>/dev/null | head -40
echo
echo "== 3. JSON files con datos del 4-11 =="
ls -la *.json | head -20
echo
echo "== 4. operar_real.py — funciones de logging =="
grep -n "log.*opera\|log.*trade\|log.*bin\|apuesta" operar_real.py 2>/dev/null | head -20
echo
echo "== 5. ejecutar senal para ver qué dice =="
timeout 15 python3 -c "
import sys
sys.path.insert(0, '.')
import json
import senal
import senal_vivo
datos = senal.cargar_csv('datos_elon.csv')
m = senal.metricas(datos)
print(f'Métricas: AVG7={m[\"avg7\"]:.2f} V2={m[\"v2\"]} R={m[\"r\"]:.3f} ajuste={m[\"ajuste\"]:.3f} λ48={m[\"lam48\"]:.1f}')
try:
    mercados = json.load(open('mercado_activo.json'))['mercados']
    ab = [x for x in mercados if not x.get('cerrado') and 'elon' in x.get('titulo','').lower()]
    print(f'Mercados Elon activos: {len(ab)}')
    for x in ab:
        print(f'  - {x.get(\"titulo\",\"?\")[:80]}')
        print(f'    cierre: {x.get(\"fin\",\"?\")} tipo: {x.get(\"tipo\",\"?\")}')
        if x.get('bins'):
            for b in x['bins'][:3]:
                print(f'      bin: {b.get(\"titulo\",\"?\")} YES={b.get(\"precio_yes\",0):.3f}')
except Exception as e:
    print(f'  [ERROR mercado] {e}')
" 2>&1 | head -30
echo
echo "== 6. tiempo restante para cierre 4-11 sept =="
python3 -c "
from datetime import datetime
from zoneinfo import ZoneInfo
ET = ZoneInfo('America/New_York')
# cierre 11 sept 12:00 ET
cierre = datetime(2026, 9, 11, 12, 0, tzinfo=ET)
ahora_et = datetime.now(ET)
diff = cierre - ahora_et
print(f'ahora ET: {ahora_et}')
print(f'cierre: {cierre}')
print(f'restante: {diff}')
print(f'  horas: {diff.total_seconds()/3600:.1f}')
print(f'  minutos: {diff.total_seconds()/60:.0f}')
"
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
