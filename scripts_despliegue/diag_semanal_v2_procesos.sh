#!/usr/bin/env bash
# diag_semanal_v2_procesos.sh — diagnosticar los 3 procesos colgados
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_semanal_v2_procesos_${TS}.log

{
echo "=== DIAG PROCESOS SEMANAL V2 — $TS UTC ==="
echo
echo "== 1. Los 3 procesos con detalles =="
ps auxf | grep -E "bot_semanal|poly-semanal" | grep -v grep
echo
echo "== 2. ¿Qué ficheros tienen abiertos los procesos? =="
for PID in 1498655 1498670 1498672; do
    echo "--- PID $PID ---"
    ls -la /proc/$PID/fd 2>/dev/null | grep -vE "socket|pipe|anon" | head -10
    cat /proc/$PID/status 2>/dev/null | head -3
done
echo
echo "== 3. real_semanal.json completo =="
cat /opt/polymarket/bot-polymarket-elon-semanal-v2/real_semanal.json | python3 -m json.tool
echo
echo "== 4. ¿A dónde escriben los 3 procesos? =="
ls -la /proc/1498655/fd/1 /proc/1498655/fd/2 2>/dev/null
ls -la /proc/1498670/fd/1 /proc/1498670/fd/2 2>/dev/null
ls -la /proc/1498672/fd/1 /proc/1498672/fd/2 2>/dev/null
echo
echo "== 5. ¿Quién los lanzó? =="
for PID in 1498655 1498670 1498672; do
    cat /proc/$PID/cmdline 2>/dev/null | tr '\0' ' '
    echo
done
echo
echo "== 6. ¿Cuánto tiempo llevan corriendo? =="
for PID in 1498655 1498670 1498672; do
    echo "PID $PID:"
    ps -o pid,etime,cmd -p $PID 2>/dev/null
done
echo
echo "== 7. ¿El servicio poly-semanal.service está activo? =="
systemctl status poly-semanal.service 2>&1 | head -10
systemctl status poly-semanal-v2.service 2>&1 | head -10
echo
echo "== 8. ¿Algún screen/tmux del semanal v2? =="
screen -ls 2>&1 | head -10
tmux ls 2>&1 | head -10
echo
echo "== 9. ¿Hay algún log nuevo en /root/ ? =="
ls -la /root/*.log 2>/dev/null | head -10
tail -30 /root/semanal.log 2>/dev/null
echo
echo "== 10. ¿Hay procesos 'seguimiento_semanal.py'? =="
ps aux | grep seguimiento | grep -v grep
echo
echo "== 11. ¿Qué versión de los .py está corriendo? =="
md5sum /opt/polymarket/bot-polymarket-elon-semanal-v2/bot_semanal.py
ls -la /opt/polymarket/bot-polymarket-elon-semanal-v2/bot_semanal.py
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
