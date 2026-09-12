#!/usr/bin/env bash
# monitorear_bots.sh — verifica estado de los 3 bots (Elon/Zelenskyy/Trump)
# Salida compacta para diag-public
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/mon_bots_${TS}.log

WALLET="0xb0E1197098E6d427c01720F1631cAD24CE740FA0"

{
echo "════════════════════════════════════════════"
echo "  MONITOREO BOTS — $TS UTC"
echo "════════════════════════════════════════════"
echo
echo "== SALDO REAL ON-CHAIN =="
python3 << 'PYEOF'
import urllib.request, json
wallet = '0xb0E1197098E6d427c01720F1631cAD24CE740FA0'
try:
    req = urllib.request.Request(
        f'https://data-api.polymarket.com/value?user={wallet}',
        headers={'User-Agent':'Mozilla/5.0'}
    )
    d = json.loads(urllib.request.urlopen(req, timeout=15).read())
    if isinstance(d, list) and d:
        v = d[0].get('value', 0)
        print(f'  cartera on-chain: ${v:.2f}')
    else:
        print(f'  response: {d}')
except Exception as e:
    print(f'  [ERROR] {e}')
PYEOF
echo

echo "== SERVICIOS (systemd) =="
for svc in poly-elon poly-zelenskyy poly-trump; do
    state=$(systemctl is-active "$svc" 2>/dev/null)
    pid=$(systemctl show "$svc" --property=MainPID --value 2>/dev/null)
    if [ "$state" = "active" ]; then
        uptime=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')
        echo "  ✅ $svc: $state (PID $pid, uptime $uptime)"
    else
        echo "  ❌ $svc: $state"
    fi
done
echo

echo "== SALDOS INTERNOS =="
for bot in "Elon:bot-polymarket-elon:real.json" \
           "Zelenskyy:bot-polymarket-zelenskyy:real_zelen.json" \
           "Trump:bot-polymarket-trump:real.json"; do
    IFS=':' read -r nombre dir archivo <<< "$bot"
    if [ -f "/opt/polymarket/$dir/$archivo" ]; then
        python3 -c "
import json
d = json.load(open('/opt/polymarket/$dir/$archivo'))
saldo = d.get('saldo', 0)
bankroll = d.get('_bankroll_inicial_real', 0)
hist = len(d.get('historial', []))
activa = d.get('activa')
step = d.get('paso', '?')
print(f'  {nombre}:')
print(f'    saldo: \${saldo}')
print(f'    bankroll_inicial: \${bankroll}')
print(f'    ops: {hist} | paso: {step}')
if activa:
    slug = activa.get('slug', '?')[:40]
    bin_t = activa.get('bin_titulo', '?')
    lado = activa.get('lado', '?')
    precio = activa.get('precio', 0)
    p = activa.get('p_modelo', 0)
    print(f'    ACTIVA: {slug} | bin {bin_t} {lado} @ {precio} (p={p:.2%})')
"
    else
        echo "  ⚠️ $nombre: $archivo no existe"
    fi
done
echo

echo "== ÚLTIMAS PASADAS =="
for svc_log in "Elon:poly-elon" "Zelenskyy:poly-zelenskyy" "Trump:poly-trump"; do
    IFS=':' read -r nombre svc <<< "$svc_log"
    last=$(journalctl -u "$svc" --since '1 hour ago' --no-pager 2>/dev/null \
        | grep -E "PASADA COMPLETA|Pasada completada" | tail -1)
    if [ -n "$last" ]; then
        ts=$(echo "$last" | awk '{print $1, $2, $3}')
        msg=$(echo "$last" | sed 's/.*python3\[[0-9]*\]: //')
        echo "  $nombre: $ts"
        echo "    $msg"
    else
        echo "  $nombre: sin pasadas en la última hora"
    fi
done
echo

echo "== ERRORES RECIENTES (1h) =="
for svc in poly-elon poly-zelenskyy poly-trump; do
    errs=$(journalctl -u "$svc" --since '1 hour ago' --no-pager 2>/dev/null \
        | grep -iE "error|exception|traceback|fail" \
        | grep -vE "jina en pausa|jina no disponible|sin saldo" \
        | wc -l)
    name=$(echo "$svc" | sed 's/poly-//')
    if [ "$errs" -gt 0 ]; then
        echo "  ⚠️ $name: $errs errores"
    else
        echo "  ✅ $name: sin errores"
    fi
done
echo

echo "== POSICIONES ABIERTAS (data-api) =="
python3 << 'PYEOF'
import urllib.request, json
try:
    req = urllib.request.Request(
        f'https://data-api.polymarket.com/positions?user=0xb0E1197098E6d427c01720F1631cAD24CE740FA0',
        headers={'User-Agent':'Mozilla/5.0'}
    )
    d = json.loads(urllib.request.urlopen(req, timeout=15).read())
    if isinstance(d, list):
        open_pos = [p for p in d if p.get('size', 0) > 0 and p.get('curPrice', 0) > 0]
        print(f'  posiciones con valor: {len(open_pos)}')
        for p in open_pos[:5]:
            t = p.get('title', '?')[:50]
            sz = p.get('size', 0)
            avg = p.get('avgPrice', 0)
            cur = p.get('curPrice', 0)
            pnl = p.get('pnl', 0)
            print(f'    {t}')
            print(f'      {sz:.0f} @ avg {avg} → cur {cur} (pnl {pnl})')
except Exception as e:
    print(f'  [ERROR] {e}')
PYEOF
echo

echo "== VERIFICACIÓN DE CONSISTENCIA =="
python3 << 'PYEOF'
import json
real_saldo = 228.45
bots = {
    'Elon': '/opt/polymarket/bot-polymarket-elon/real.json',
    'Zelenskyy': '/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json',
    'Trump': '/opt/polymarket/bot-polymarket-trump/real.json',
}
for name, path in bots.items():
    try:
        d = json.load(open(path))
        s = d.get('saldo', 0)
        b = d.get('_bankroll_inicial_real', 0)
        if abs(s - real_saldo) < 0.01 and abs(b - real_saldo) < 0.01:
            print(f'  ✅ {name}: saldo=${s}, bankroll=${b} (consistente)')
        else:
            print(f'  ❌ {name}: saldo=${s}, bankroll=${b} (esperado ${real_saldo})')
    except Exception as e:
        print(f'  ❌ {name}: {e}')
PYEOF
echo

echo "════════════════════════════════════════════"
echo "  FIN MONITOREO"
echo "════════════════════════════════════════════"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os
LOG = os.environ.get('LOG_FILE', '/tmp/mon_bots.log')
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': f'diag: {name}', 'branch': 'diag-public', 'content': b64}
try:
    req = urllib.request.urlopen(urllib.request.Request(
        f'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/{name}',
        data=json.dumps(p).encode(),
        headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
        method='PUT'), timeout=30)
    print('Publicado:', json.loads(req.read())['content']['path'])
except Exception as e:
    print('[ERROR publicando]', e)
PYEOF
