#!/usr/bin/env bash
# sincronizar_elon_saldo_v3.sh — versión mínima sin python anidado
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/sincronizar_elon_v3_${TS}.log

ELON_DIR="/opt/polymarket/bot-polymarket-elon"
NEW_SALDO="228.45"

{
echo "=== SINCRONIZACIÓN BOT ELON v3 — $TS UTC ==="
echo
echo "== 1. Estado actual =="
ls -la "$ELON_DIR/real.json"
echo "contenido actual:"
cat "$ELON_DIR/real.json" | head -20
echo
echo "== 2. Backup =="
cp "$ELON_DIR/real.json" "$ELON_DIR/real.json.bak_${TS}"
echo "backup: $ELON_DIR/real.json.bak_${TS}"
echo
echo "== 3. Actualizar con jq (más simple que python) =="
if command -v jq >/dev/null; then
    jq --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
       '.saldo = 228.45 | ._bankroll_inicial_real = 228.45 | ._pnl_historico_acumulado = 0.0 | ._sincronizado_con_real = true | ._sincronizado_ts = $ts' \
       "$ELON_DIR/real.json" > "$ELON_DIR/real.json.new" \
    && mv "$ELON_DIR/real.json.new" "$ELON_DIR/real.json"
    echo "  actualizado con jq"
else
    # fallback python inline (más simple)
    python3 -c "
import json
p='$ELON_DIR/real.json'
d=json.load(open(p))
d['saldo']=228.45
d['_bankroll_inicial_real']=228.45
d['_pnl_historico_acumulado']=0.0
d['_sincronizado_con_real']=True
from datetime import datetime, timezone
d['_sincronizado_ts']=datetime.now(timezone.utc).isoformat()
json.dump(d, open(p,'w'), indent=2)
print('actualizado con python')
"
fi
chmod 600 "$ELON_DIR/real.json"
echo
echo "== 4. Verificación =="
cat "$ELON_DIR/real.json" | head -20
echo
echo "== 5. Servicio =="
systemctl status poly-elon.service 2>&1 | head -8
echo
echo "== 6. Resumen =="
echo "saldo: \$$NEW_SALDO"
echo "backup: $ELON_DIR/real.json.bak_${TS}"
echo "historial: preservado"
echo "servicio: no reiniciado (lee nuevo saldo en 5 min)"
} > "$LOG" 2>&1

echo "log local: $LOG"
cat "$LOG"

# publicar SIEMPRE
python3 << 'PYEOF'
import base64, json, urllib.request
import os
LOG = os.environ.get('LOG_FILE', '')
if not LOG:
    # leer de la última variable
    pass
PYEOF

# versión simple del publish
python3 -c "
import base64, json, urllib.request, os
LOG = '$LOG'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG,'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message':f'diag: {name}','branch':'diag-public','content':b64}
try:
    req = urllib.request.urlopen(urllib.request.Request(
        'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/' + name,
        data=json.dumps(p).encode(),
        headers={'Authorization':'token '+tok,'Content-Type':'application/json','Accept':'application/vnd.github.v3+json'},
        method='PUT'), timeout=30)
    print('Publicado:', json.loads(req.read())['content']['path'])
except Exception as e:
    print('[ERROR publicando]', e)
"
