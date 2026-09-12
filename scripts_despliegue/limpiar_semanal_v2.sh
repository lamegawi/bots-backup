#!/usr/bin/env bash
# limpiar_semanal_v2.sh — matar procesos, archivar directorio, desactivar servicio
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/limpiar_semanal_v2_${TS}.log

{
echo "=== LIMPIEZA SEMANAL V2 — $TS UTC ==="
echo
echo "== 1. Backup completo del bot semanal v2 =="
BACKUP_DIR="/opt/polymarket/_archivado"
mkdir -p "$BACKUP_DIR/bot-polymarket-elon-semanal-v2_${TS}"
echo "destino: $BACKUP_DIR/bot-polymarket-elon-semanal-v2_${TS}"
# copiar pero sin .git ni logs pesados
rsync -a --exclude='.git' --exclude='__pycache__' \
    /opt/polymarket/bot-polymarket-elon-semanal-v2/ \
    "$BACKUP_DIR/bot-polymarket-elon-semanal-v2_${TS}/" 2>&1
echo "tamaño backup:"
du -sh "$BACKUP_DIR/bot-polymarket-elon-semanal-v2_${TS}/"
echo
echo "== 2. Matar los 3 procesos del semanal v2 =="
echo "--- procesos antes ---"
ps aux | grep bot_semanal | grep -v grep
echo
# matar PIDs identificados: 1498655, 1498670, 1498672 (cualquier bot_semanal.py activo)
for PID in $(ps aux | grep "bot_semanal.py" | grep -v grep | awk '{print $2}'); do
    echo "  matando PID $PID..."
    kill -15 $PID 2>&1
done
sleep 3
# forzar si quedan
for PID in $(ps aux | grep "bot_semanal.py" | grep -v grep | awk '{print $2}'); do
    echo "  forzando PID $PID..."
    kill -9 $PID 2>&1
done
echo "--- procesos después ---"
ps aux | grep bot_semanal | grep -v grep || echo "  (ninguno)"
echo
echo "== 3. Desactivar servicio poly-semanal.service =="
systemctl stop poly-semanal.service 2>&1
systemctl disable poly-semanal.service 2>&1
systemctl status poly-semanal.service 2>&1 | head -5
echo
echo "== 4. Eliminar definición del servicio systemd =="
ls -la /etc/systemd/system/poly-semanal.service
mv /etc/systemd/system/poly-semanal.service /etc/systemd/system/poly-semanal.service.disabled_${TS}
systemctl daemon-reload 2>&1
echo
echo "== 5. Mover directorio del bot a /opt/polymarket/_archivado/ =="
mv /opt/polymarket/bot-polymarket-elon-semanal-v2 "$BACKUP_DIR/"
echo "movido a: $BACKUP_DIR/bot-polymarket-elon-semanal-v2/"
echo
echo "== 6. Verificación final =="
echo "--- procesos del semanal ---"
ps aux | grep bot_semanal | grep -v grep || echo "  ✅ ninguno"
echo "--- servicio poly-semanal ---"
systemctl status poly-semanal.service 2>&1 | head -3
echo "--- directorio origen ---"
ls /opt/polymarket/ | grep semanal || echo "  ✅ directorio eliminado"
echo "--- backup ---"
ls -la "$BACKUP_DIR/"
echo
echo "== 7. Verificar que el bot de Elon principal sigue corriendo =="
systemctl status poly-elon 2>&1 | head -5
ps aux | grep "bot.py" | grep -v grep
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
