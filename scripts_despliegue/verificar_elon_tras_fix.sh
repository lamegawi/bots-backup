#!/usr/bin/env bash
# verificar_elon_tras_fix.sh — confirma que el bot de Elon usa el nuevo dato
#   1) muestra el CSV (últimas filas)
#   2) ejecuta senal_vivo para ver qué decisión toma con el dato 152
#   3) muestra logs recientes del bot
#   4) publica todo a diag-public
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/verificar_elon_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== VERIFICACIÓN BOT ELON TRAS FIX — $TS UTC ==="
echo
echo "== 1. CSV (últimas 12 filas) =="
tail -12 datos_elon.csv
echo
echo "== 2. POLYMARKET OFICIAL JSON =="
cat polymarket_oficial.json 2>/dev/null || echo "(no existe)"
echo
echo "== 3. CÁLCULO DE MÉTRICAS (AVG7, V2, λ48) =="
python3 -c "
import csv
with open('datos_elon.csv') as f:
    filas = [(r['fecha'], int(r['tweets'])) for r in csv.DictReader(f)]
print(f'  Total filas: {len(filas)}')
if len(filas) >= 9:
    ult7 = [n for _, n in filas[-7:]]
    ult2 = [n for _, n in filas[-2:]]
    avg7 = sum(ult7) / 7
    v2 = sum(ult2)
    r = v2 / (2 * avg7)
    aj = min(1.5, max(0.5, 1 + 0.5 * (r - 1)))
    lam = 2 * avg7 * aj
    print(f'  AVG7 = {avg7:.2f}  V2 = {v2}  R = {r:.3f}  ajuste = {aj:.3f}  λ48 = {lam:.1f}')
    print(f'  Últimos 7 días: {ult7}')
    print(f'  Últimos 2 días: {ult2}')
    # Proyección probabilística para el mercado 4-11 sept (cierra 11 sept 12:00 ET)
    # Asumiendo Poisson con λ48h, P(N=k) = (λ^k / k!) * exp(-λ)
    import math
    print(f'  Distribución proyectada (Poisson λ={lam:.1f}):')
    for k in range(140, 220, 20):
        p = (lam**k / math.factorial(k)) * math.exp(-lam)
        print(f'    P(N={k:>3}) = {p*100:5.1f}%')
"
echo
echo "== 4. DECISIÓN DEL BOT (ejecutar senal_vivo en modo lectura) =="
timeout 30 python3 senal_vivo.py --mercado 2>&1 | head -50 || echo "(senal_vivo requiere argumentos)"
echo
echo "== 5. LOGS RECIENTES DEL BOT =="
echo "-- journalctl (últimas 30 líneas) --"
journalctl -u poly-elon --since "1 hour ago" --no-pager -n 30 2>/dev/null || tail -30 /var/log/poly/elon.log 2>/dev/null || echo "(sin logs)"
echo
echo "-- log del bot si existe --"
ls -la /opt/polymarket/bot-polymarket-elon/*.log 2>/dev/null
for f in /opt/polymarket/bot-polymarket-elon/*.log; do
  if [ -f "$f" ]; then
    echo "--- $f (últimas 20 líneas) ---"
    tail -20 "$f"
  fi
done
echo
echo "== 6. ESTADO DEL SERVICIO systemd =="
systemctl status poly-elon --no-pager -n 5 2>/dev/null | head -20
echo
echo "== 7. POSICIÓN EN CLOB =="
python3 -c "
import urllib.request, json
url = 'https://data-api.polymarket.com/positions?user=0xb0E148FEb4bE59fD617c8Ad6ce5Cf2b5f0BB2Ae1'
try:
    d = json.loads(urllib.request.urlopen(url, timeout=20).read())
    elon_vivas = [p for p in d if 'elon' in p.get('title','').lower() and float(p.get('curPrice', 0)) > 0]
    print(f'  Posiciones vivas de Elon: {len(elon_vivas)}')
    for p in elon_vivas[:5]:
        print(f'    {p.get(\"title\",\"?\")[:60]}: {p.get(\"size\",0)} shares @ avg {p.get(\"avgPrice\",0)} cur {p.get(\"curPrice\",0)} pnl {p.get(\"pnl\",0)}')
    if not elon_vivas:
        # mostrar todas las de Elon
        elon = [p for p in d if 'elon' in p.get('title','').lower()]
        print(f'  (Total posiciones Elon: {len(elon)}, todas con cur=0)')
except Exception as e:
    print(f'  [ERROR] {e}')
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
