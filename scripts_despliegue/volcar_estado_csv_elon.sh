#!/usr/bin/env bash
# volcar_estado_csv_elon.sh — vuelca estado_tweets.json al CSV en Hetzner
#   0) descarga volcar_estado_a_csv.py desde GitHub (no estaba en Hetzner)
#   1) dry-run mostrando lo que cambiaría
#   2) ejecuta real
#   3) muestra el CSV final
#   4) publica el log a diag-public
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/volcar_estado_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

# 0) descargar el .py desde la misma rama (no estaba desplegado)
BRANCH="arena/01a058fe-bots-backup"
curl -sL -o volcar_estado_a_csv.py "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/poly/codigo/bot-polymarket-elon/volcar_estado_a_csv.py"
echo "  descargado: $(wc -c < volcar_estado_a_csv.py) bytes"
head -1 volcar_estado_a_csv.py
chmod +x volcar_estado_a_csv.py

{
echo "=== VOLCAR ESTADO A CSV — $TS UTC ==="
echo
echo "== 1. DRY-RUN (no modifica nada) =="
python3 volcar_estado_a_csv.py --dry-run --periodo 2026-09-04 2026-09-11
echo
echo "== 2. EJECUCIÓN REAL =="
python3 volcar_estado_a_csv.py --periodo 2026-09-04 2026-09-11
echo
echo "== 3. CSV FINAL =="
cat datos_elon.csv
echo
echo "== 4. TOTAL 4-11 sept =="
awk -F, 'NR>1 && $1>="2026-09-04" && $1<="2026-09-11" {s+=$2} END {print s}' datos_elon.csv
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
