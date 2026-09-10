#!/usr/bin/env bash
# arrancar_v4.sh — bootstrap limpio para auto_exit_v4
set -u

# Crear dirs primero
mkdir -p /tmp/auto_exit_elon

# Matar solo el v4 específico (por PID file o por coincidencia exacta)
for p in $(pgrep -f "auto_exit_v[34]"); do
  kill "$p" 2>/dev/null
done
sleep 2

# Limpiar lockfile
rm -f /tmp/auto_exit_elon.lock

# Descargar
curl -sL -o /tmp/auto.sh https://raw.githubusercontent.com/lamegawi/bots-backup/892f9fa5/scripts_despliegue/auto_exit_v4.sh
chmod +x /tmp/auto.sh
echo "[download] $(wc -c </tmp/auto.sh) bytes"

# Arrancar
DRY_RUN=1 INTERVALO_S=900 AUTO_BANKROLL_USD=20 \
  nohup setsid bash /tmp/auto.sh > /tmp/auto_exit_elon/main.log 2>&1 < /dev/null &
echo "PID: $!"
disown
sleep 25
echo "--- main.log (primer 80) ---"
head -80 /tmp/auto_exit_elon/main.log
echo "--- archivos publicados ---"
ls -la /tmp/auto_exit_elon/ | tail -10
