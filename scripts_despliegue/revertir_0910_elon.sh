#!/usr/bin/env bash
# revertir_0910_elon.sh — restaura el 09-10 a 18 (estado real)
#   y borra polymarket_oficial.json para evitar confusión
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/revertir_0910_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== REVERTIR 09-10 A 18 — $TS UTC ==="
echo
echo "== ANTES =="
tail -3 datos_elon.csv
echo
echo "== Restaurar desde .bak =="
if [ -f datos_elon.csv.bak ]; then
  cp datos_elon.csv.bak datos_elon.csv
  echo "[OK] CSV restaurado desde .bak"
else
  echo "[AVISO] no hay .bak, sobrescribiendo 09-10 a 18 manualmente"
  python3 -c "
import csv
filas = {}
with open('datos_elon.csv') as f:
    for r in csv.DictReader(f):
        filas[r['fecha']] = int(r['tweets'])
filas['2026-09-10'] = 18
with open('datos_elon.csv', 'w') as f:
    w = csv.writer(f)
    w.writerow(['fecha', 'tweets'])
    for f_ in sorted(filas):
        w.writerow([f_, filas[f_]])
print('[OK] 09-10 = 18')
"
fi
echo
echo "== DESPUÉS =="
tail -3 datos_elon.csv
echo
echo "== Borrar polymarket_oficial.json =="
if [ -f polymarket_oficial.json ]; then
  mv polymarket_oficial.json polymarket_oficial.json.disabled
  echo "[OK] polymarket_oficial.json → polymarket_oficial.json.disabled"
fi
echo
echo "== Métricas con CSV restaurado =="
python3 -c "
import csv
with open('datos_elon.csv') as f:
    filas = [(r['fecha'], int(r['tweets'])) for r in csv.DictReader(f)]
ult7 = [n for _, n in filas[-7:]]
ult2 = [n for _, n in filas[-2:]]
avg7 = sum(ult7) / 7
v2 = sum(ult2)
r = v2 / (2 * avg7)
aj = min(1.5, max(0.5, 1 + 0.5 * (r - 1)))
lam = 2 * avg7 * aj
print(f'  AVG7 = {avg7:.2f}  V2 = {v2}  R = {r:.3f}  ajuste = {aj:.3f}  λ48 = {lam:.1f}')
print(f'  Últimos 7 días: {ult7}')
"
} > "$LOG" 2>&1

cat "$LOG"

# publicar
python3 -c "
import base64, json, urllib.request, urllib.error
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
