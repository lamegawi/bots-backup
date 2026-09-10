#!/usr/bin/env bash
# arreglar_cron_y_csv_elon.sh — corrige 3 cosas:
#   1) actualiza el wrapper del cron para NO usar --actualizar-csv
#   2) re-vierte 09-10 a 18 (estado real)
#   3) re-ejecuta mercado_ultima_oportunidad
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/arreglar_cron_csv_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== ARREGLAR CRON Y CSV — $TS UTC ==="
echo
echo "== 1. ARREGLANDO WRAPPER DEL CRON (sin --actualizar-csv) =="
cat > /opt/polymarket/scraper_cron_elon.sh <<'WRAP'
#!/usr/bin/env bash
# Ejecuta el scraper de Polymarket SIN --actualizar-csv.
# El TWEET_COUNT es el TOTAL del periodo, no el conteo de un día.
# Si activamos --actualizar-csv, sobreescribe 09-10 con el TOTAL.
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/var/log/poly/scraper_elon_${TS}.log
cd /opt/polymarket/bot-polymarket-elon
python3 scraper_tweets_pm.py --user elonmusk >> "$LOG" 2>&1
# limpiar logs de más de 7 días
find /var/log/poly/scraper_elon_*.log -mtime +7 -delete 2>/dev/null
WRAP
chmod +x /opt/polymarket/scraper_cron_elon.sh
cat /opt/polymarket/scraper_cron_elon.sh
echo
echo "== 2. REVIRTIENDO 09-10 A 18 =="
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
print('[OK] 09-10 = 18 (forzado)')
"
echo
echo "== 3. RE-VERIFICANDO CSV =="
tail -3 datos_elon.csv
echo
echo "== 4. PROBANDO MERCADO ÚLTIMAS OPORTUNIDADES =="
# descargar el script si no está
BRANCH="arena/01a058fe-bots-backup"
TS_NOW=$(date +%s%N)
[ ! -f mercado_ultima_oportunidad.py ] && curl -sL -o mercado_ultima_oportunidad.py "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/poly/codigo/bot-polymarket-elon/mercado_ultima_oportunidad.py?bust=${TS_NOW}"
chmod +x mercado_ultima_oportunidad.py
python3 mercado_ultima_oportunidad.py --user elonmusk --bankroll 303.55
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
