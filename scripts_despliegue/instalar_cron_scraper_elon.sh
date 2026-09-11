#!/usr/bin/env bash
# instalar_cron_scraper_elon.sh — instala un cron cada 5 min que ejecuta
# el scraper de Polymarket con el usuario root (que SÍ llega a polymarket.com).
# El bot (servicio systemd) lee el CSV actualizado por el cron.
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/instalar_cron_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== INSTALAR CRON SCRAPER ELON — $TS UTC ==="
echo
echo "== 1. Descargando scraper_tweets_pm.py =="
TS_NOW=$(date +%s%N)
curl -sL -o scraper_tweets_pm.py "https://raw.githubusercontent.com/lamegawi/bots-backup/arena/01a058fe-bots-backup/poly/codigo/bot-polymarket-elon/scraper_tweets_pm.py?bust=${TS_NOW}"
echo "  $(wc -c < scraper_tweets_pm.py) bytes"
chmod +x scraper_tweets_pm.py

echo
echo "== 2. Creando script wrapper del cron =="
cat > /opt/polymarket/scraper_cron_elon.sh <<'WRAP'
#!/usr/bin/env bash
# Ejecuta el scraper de Polymarket y guarda TWEET_COUNT en
# polymarket_oficial.json (NO toca datos_elon.csv porque el TWEET_COUNT
# es el TOTAL del periodo, no el conteo diario).
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/var/log/poly/scraper_elon_${TS}.log
cd /opt/polymarket/bot-polymarket-elon
python3 scraper_tweets_pm.py --user elonmusk >> "$LOG" 2>&1
# limpiar logs de más de 7 días
find /var/log/poly/scraper_elon_*.log -mtime +7 -delete 2>/dev/null
WRAP
chmod +x /opt/polymarket/scraper_cron_elon.sh
mkdir -p /var/log/poly
echo "  /opt/polymarket/scraper_cron_elon.sh creado"

echo
echo "== 3. Instalando cron (cada 5 min) =="
# guardar cron actual por seguridad
crontab -l > /tmp/cron_backup_${TS}.txt 2>/dev/null || true
# añadir línea nueva
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/polymarket/scraper_cron_elon.sh") | crontab -
echo "  crontab actualizado:"
crontab -l | grep scraper

echo
echo "== 4. Probando el wrapper =="
/opt/polymarket/scraper_cron_elon.sh
sleep 2
echo "  último log:"
ls -t /var/log/poly/scraper_elon_*.log 2>/dev/null | head -1 | xargs tail -10

echo
echo "== 5. Estado del bot =="
systemctl status poly-elon --no-pager -n 5 | head -10
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
