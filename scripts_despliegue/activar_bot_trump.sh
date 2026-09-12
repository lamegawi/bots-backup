#!/usr/bin/env bash
# activar_bot_trump.sh — verificar saldo real, activar Trump, sincronizar bots
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/activar_trump_${TS}.log

WALLET="0xb0E1197098E6d427c01720F1631cAD24CE740FA0"

cd /opt/polymarket/bot-polymarket-trump

{
echo "=== ACTIVAR BOT TRUMP — $TS UTC ==="
echo "wallet: $WALLET"
echo
echo "== 1. Verificar saldo real on-chain con la wallet correcta =="
python3 -c "
import urllib.request, json
wallet = '$WALLET'
url = f'https://data-api.polymarket.com/value?user={wallet}'
try:
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    d = json.loads(urllib.request.urlopen(req, timeout=15).read())
    if isinstance(d, list) and d:
        for entry in d:
            print(f'  {entry.get(\"user\")}: \${entry.get(\"value\",0)}')
    else:
        print(f'  response: {d}')
except Exception as e:
    print(f'[ERROR] {e}')
"
echo
echo "== 2. Verificar posiciones existentes =="
python3 -c "
import urllib.request, json
wallet = '$WALLET'
url = f'https://data-api.polymarket.com/positions?user={wallet}'
try:
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    d = json.loads(urllib.request.urlopen(req, timeout=15).read())
    print(f'total posiciones: {len(d) if isinstance(d, list) else 0}')
    if isinstance(d, list):
        for p in d[:10]:
            t = p.get('title', '?')[:60]
            sz = p.get('size', 0)
            avg = p.get('avgPrice', 0)
            cur = p.get('curPrice', 0)
            pnl = p.get('pnl', 0)
            print(f'  {t} | size={sz} avg={avg} cur={cur} pnl={pnl}')
except Exception as e:
    print(f'[ERROR] {e}')
"
echo
echo "== 3. ¿Existe config_real.json en Trump? =="
ls -la config_real.json 2>&1
echo
echo "== 4. ¿Existe .env con la clave privada? =="
ls -la /opt/polymarket/.env /opt/polymarket/.env.trump /root/.env 2>&1
cat /opt/polymarket/.env 2>/dev/null | head -5
cat /opt/polymarket/bot-polymarket-trump/.env 2>/dev/null | head -5
echo
echo "== 5. ¿El servicio usa variables de entorno? =="
cat /etc/systemd/system/poly-trump.service
echo
echo "== 6. ¿Cómo carga POLY_PRIVATE_KEY? =="
grep -rE "POLY_PRIVATE_KEY|POLY_WALLET_ADDRESS" /etc/systemd/ 2>/dev/null | head -10
echo
echo "== 7. ¿Hay claves en /etc/default/poly-trump? =="
cat /etc/default/poly-trump 2>/dev/null
cat /etc/default/poly 2>/dev/null
echo
echo "== 8. ¿Qué env tiene el proceso activo? =="
PID=$(pgrep -f "bot_semanal.py.*trump" | head -1)
if [ -z "$PID" ]; then
    PID=$(systemctl show poly-trump.service --property=MainPID --value 2>/dev/null)
fi
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    echo "PID del bot: $PID"
    cat /proc/$PID/environ 2>/dev/null | tr '\0' '\n' | grep -E "POLY|WALLET|PRIVATE" | head -10
fi
echo
echo "== 9. ¿Qué saldo usan los demás bots? =="
echo "--- bot Elon (de real.json) ---"
python3 -c "
import json
try:
    d = json.load(open('/opt/polymarket/bot-polymarket-elon/real.json'))
    print(f'  saldo: \${d.get(\"saldo\")}  bankroll_inicial: \${d.get(\"_bankroll_inicial_real\")}  pnl: \${d.get(\"_pnl_historico_acumulado\")}')
except Exception as e:
    print(f'  [ERROR] {e}')
"
echo "--- bot Zelenskyy (de real_zelen.json) ---"
python3 -c "
import json
try:
    d = json.load(open('/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json'))
    print(f'  saldo: \${d.get(\"saldo\")}  bankroll_inicial: \${d.get(\"_bankroll_inicial_real\")}  pnl: \${d.get(\"_pnl_historico_acumulado\")}')
except Exception as e:
    print(f'  [ERROR] {e}')
"
echo
echo "== 10. CONFIGURACIÓN ACTUAL DEL SISTEMA =="
echo
echo "Variables de entorno del bot Trump:"
tr '\0' '\n' < /proc/$(systemctl show poly-trump.service --property=MainPID --value 2>/dev/null)/environ 2>/dev/null | grep -v "^$" | head -20
echo
echo "== 11. Resumen de la activación =="
cat <<'EOF'
Para ACTIVAR el bot de Trump completamente, hay que:
1. Crear /opt/polymarket/bot-polymarket-trump/config_real.json con:
   - wallet_address: 0xb0E1197098E6d427c01720F1631cAD24CE740FA0
   - confirmado: true
   - bankroll: 228.45 (el real de tu screenshot)
2. Crear /opt/polymarket/bot-polymarket-trump/real.json con:
   - saldo: 228.45
   - activa: null
   - historial: []
   - paso: 1
3. Reiniciar el servicio: systemctl restart poly-trump.service
EOF
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
