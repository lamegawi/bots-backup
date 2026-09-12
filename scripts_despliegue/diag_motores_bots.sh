#!/usr/bin/env bash
# diag_motores_bots.sh — analiza qué motor (lógica) usa cada bot
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_motores_${TS}.log

{
echo "════════════════════════════════════════════"
echo "  DIAGNÓSTICO DE MOTORES — $TS UTC"
echo "════════════════════════════════════════════"
echo

echo "########################################"
echo "# BOT 1: ELON"
echo "########################################"
echo
echo "== 1. Archivos principales de Elon =="
ls -la /opt/polymarket/bot-polymarket-elon/*.py 2>&1 | head -20
echo
echo "== 2. ¿Qué motor usa senal.py? =="
grep -nE "motor|MOTOR|motor_v" /opt/polymarket/bot-polymarket-elon/senal.py 2>&1 | head -15
echo
echo "== 3. ¿Qué motor usa senal_vivo.py? =="
grep -nE "motor|MOTOR|motor_v" /opt/polymarket/bot-polymarket-elon/senal_vivo.py 2>&1 | head -15
echo
echo "== 4. ¿Qué motor usa bot.py? =="
grep -nE "motor|MOTOR|motor_v" /opt/polymarket/bot-polymarket-elon/bot.py 2>&1 | head -15
echo
echo "== 5. Funciones definidas en senal.py (motor principal) =="
grep -nE "^def |motor_" /opt/polymarket/bot-polymarket-elon/senal.py 2>&1 | head -20
echo
echo "== 6. ¿Qué variables/filtros activos? =="
grep -nE "^(CUOTA_MINIMA|EDGE_MIN|PRECIO_MAX|P_FLOOR|STAKE|VENTANA|LAMBDA|FACTOR|UMBRAL)" /opt/polymarket/bot-polymarket-elon/senal.py 2>&1 | head -25
echo
echo "== 7. ¿Qué se ejecuta realmente? (de bot.log reciente) =="
grep -E "motor|MOTOR|motor_v" /opt/polymarket/bot-polymarket-elon/bot.log 2>&1 | tail -10
echo
echo "== 8. ¿Filtros anti-long-shot activos? =="
grep -nE "anti.long.shot|CUOTA_MINIMA|UMBRAL_LONGSHOT" /opt/polymarket/bot-polymarket-elon/senal.py 2>&1 | head -10
echo
echo "== 9. ¿Qué tipo de ventana usa? =="
grep -nE "semanal|48h|diario|mensual|VENTANA_TIPO" /opt/polymarket/bot-polymarket-elon/senal.py 2>&1 | head -10

echo
echo "########################################"
echo "# BOT 2: ZELENSKYY"
echo "########################################"
echo
echo "== 1. Archivos principales de Zelenskyy =="
ls -la /opt/polymarket/bot-polymarket-zelenskyy/*.py 2>&1 | head -20
echo
echo "== 2. ¿Qué motor usa senal.py? =="
grep -nE "motor|MOTOR|motor_v" /opt/polymarket/bot-polymarket-zelenskyy/senal.py 2>&1 | head -15
echo
echo "== 3. ¿Qué motor usa senal_vivo.py? =="
grep -nE "motor|MOTOR|motor_v" /opt/polymarket/bot-polymarket-zelenskyy/senal_vivo.py 2>&1 | head -15
echo
echo "== 4. Funciones definidas en senal.py =="
grep -nE "^def |motor_" /opt/polymarket/bot-polymarket-zelenskyy/senal.py 2>&1 | head -20
echo
echo "== 5. ¿Qué variables/filtros activos? =="
grep -nE "^(CUOTA_MINIMA|EDGE_MIN|PRECIO_MAX|P_FLOOR|STAKE|VENTANA|LAMBDA|FACTOR|UMBRAL)" /opt/polymarket/bot-polymarket-zelenskyy/senal.py 2>&1 | head -25
echo
echo "== 6. ¿Qué se ejecuta realmente? (de bot.log reciente) =="
grep -E "motor|MOTOR|motor_v" /opt/polymarket/bot-polymarket-zelenskyy/bot.log 2>&1 | tail -10
echo
echo "== 7. ¿Filtros activos? =="
grep -nE "anti.long|CUOTA_MINIMA|PRECIO_MAX" /opt/polymarket/bot-polymarket-zelenskyy/senal.py 2>&1 | head -10
echo
echo "== 8. ¿Qué tipo de ventana usa? =="
grep -nE "semanal|48h|diario|mensual" /opt/polymarket/bot-polymarket-zelenskyy/senal.py 2>&1 | head -10

echo
echo "########################################"
echo "# BOT 3: TRUMP"
echo "########################################"
echo
echo "== 1. Archivos principales de Trump =="
ls -la /opt/polymarket/bot-polymarket-trump/*.py 2>&1 | head -20
echo
echo "== 2. ¿Qué motor usa senal.py? =="
grep -nE "motor|MOTOR|motor_v" /opt/polymarket/bot-polymarket-trump/senal.py 2>&1 | head -15
echo
echo "== 3. ¿Qué motor usa bot_semanal.py? =="
grep -nE "motor|MOTOR|motor_v" /opt/polymarket/bot-polymarket-trump/bot_semanal.py 2>&1 | head -15
echo
echo "== 4. Funciones definidas en senal.py =="
grep -nE "^def |motor_" /opt/polymarket/bot-polymarket-trump/senal.py 2>&1 | head -20
echo
echo "== 5. ¿Qué variables/filtros activos? =="
grep -nE "^(CUOTA_MINIMA|EDGE_MIN|PRECIO_MAX|P_FLOOR|STAKE|VENTANA|LAMBDA|FACTOR|UMBRAL)" /opt/polymarket/bot-polymarket-trump/senal.py 2>&1 | head -25
echo
echo "== 6. ¿Qué se ejecuta realmente? =="
grep -E "motor|MOTOR|motor_v" /opt/polymarket/bot-polymarket-trump/bot_trump.log 2>&1 | tail -10
echo
echo "== 7. ¿Filtros activos? =="
grep -nE "anti.long|CUOTA_MINIMA|PRECIO_MAX" /opt/polymarket/bot-polymarket-trump/senal.py 2>&1 | head -10
echo
echo "== 8. ¿Qué tipo de ventana usa? =="
grep -nE "semanal|48h|diario|mensual|truth.social" /opt/polymarket/bot-polymarket-trump/senal.py 2>&1 | head -10

echo
echo "########################################"
echo "# COMPARATIVA DE FILTROS"
echo "########################################"
echo
echo "== Valores de los filtros en los 3 bots =="
for bot in elon zelenskyy trump; do
    echo "--- $bot ---"
    grep -E "^(CUOTA_MINIMA|EDGE_MIN|PRECIO_MAX|P_FLOOR|STAKE_PCT|STAKE_MIN|STAKE_MAX|LAMBDA|VENTANA_MIN|VENTANA_MAX)" \
        /opt/polymarket/bot-polymarket-$bot/senal.py 2>/dev/null | head -10
    echo
done

echo
echo "########################################"
echo "# ESTADÍSTICAS DE OPERACIONES"
echo "########################################"
echo
for bot in elon zelenskyy trump; do
    echo "--- $bot ---"
    python3 -c "
import json, os
files = ['real.json', 'real_zelen.json']
for f in files:
    p = f'/opt/polymarket/bot-polymarket-$bot/{f}'
    if os.path.exists(p):
        d = json.load(open(p))
        hist = d.get('historial', [])
        # contar motores usados
        motores = {}
        for op in hist:
            m = op.get('motor', 'sin_motor')
            motores[m] = motores.get(m, 0) + 1
        print(f'  {f}: {len(hist)} ops')
        for m, c in motores.items():
            print(f'    {m}: {c} ops')
        break
"
done
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/diag_motores_*.log'))
LOG = logs[-1] if logs else '/tmp/diag_motores.log'
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
