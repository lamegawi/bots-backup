#!/usr/bin/env bash
# sincronizar_elon_saldo_v2.sh — sincroniza saldo del bot de Elon al real ($228.45) + publica log
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/sincronizar_elon_v2_${TS}.log

ELON_DIR="/opt/polymarket/bot-polymarket-elon"

{
echo "=== SINCRONIZACIÓN BOT ELON — $TS UTC ==="
echo
echo "== 1. Estado actual =="
ls -la "$ELON_DIR/real.json"
python3 -c "
import json
d = json.load(open('$ELON_DIR/real.json'))
print(f'  saldo: \${d.get(\"saldo\")}')
print(f'  bankroll_inicial_real: \${d.get(\"_bankroll_inicial_real\")}')
print(f'  pnl_historico_acumulado: \${d.get(\"_pnl_historico_acumulado\")}')
print(f'  activa: {d.get(\"activa\")}')
print(f'  historial: {len(d.get(\"historial\",[]))} ops')
print(f'  paso: {d.get(\"paso\")}')
"
echo
echo "== 2. ¿Existe service poly-elon.service? =="
cat /etc/systemd/system/poly-elon.service 2>&1
echo
echo "== 3. Backup del real.json =="
cp "$ELON_DIR/real.json" "$ELON_DIR/real.json.bak_${TS}"
echo "backup: $ELON_DIR/real.json.bak_${TS}"
echo
echo "== 4. Actualizar real.json con saldo real $228.45 =="
python3 << 'PYEOF'
import json
p = '/opt/polymarket/bot-polymarket-elon/real.json'
d = json.load(open(p))
old_saldo = d.get('saldo', 0)
old_bankroll = d.get('_bankroll_inicial_real', 0)
new_saldo = 228.45
# actualizar
d['saldo'] = new_saldo
d['_bankroll_inicial_real'] = new_saldo
d['_pnl_historico_acumulado'] = 0.0
d['_sincronizado_con_real'] = True
from datetime import datetime, timezone
d['_sincronizado_ts'] = datetime.now(timezone.utc).isoformat()
json.dump(d, open(p, 'w'), indent=2)
print(f'  actualizado:')
print(f'    saldo: ${old_saldo} -> ${new_saldo}')
print(f'    bankroll_inicial: ${old_bankroll} -> ${new_saldo}')
print(f'    pnl_acumulado: 0.0 (reset)')
print(f'    historial: {len(d.get("historial",[]))} ops (preservado)')
PYEOF
chmod 600 "$ELON_DIR/real.json"
ls -la "$ELON_DIR/real.json"
echo
echo "== 5. Verificación final =="
python3 -c "
import json
d = json.load(open('$ELON_DIR/real.json'))
print(f'  saldo final: \${d.get(\"saldo\")}')
print(f'  bankroll: \${d.get(\"_bankroll_inicial_real\")}')
print(f'  historial: {len(d.get(\"historial\",[]))} ops')
"
echo
echo "== 6. Servicio NO se reinicia =="
systemctl status poly-elon.service 2>&1 | head -8
echo
echo "== 7. Resumen =="
echo "  real.json: saldo sincronizado a \$228.45"
echo "  bankroll_inicial_real: \$228.45"
echo "  pnl_historico_acumulado: reset a 0.0"
echo "  historial: preservado"
echo "  backup: $ELON_DIR/real.json.bak_${TS}"
echo "  El bot leerá el nuevo saldo en la próxima pasada (5 min)"
} > "$LOG" 2>&1

cat "$LOG"

# publicar SIEMPRE
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
" || echo "[ERROR publicando]"
