#!/usr/bin/env bash
# parar_v7.sh — mata v7 y resetea posicion.json
set -u
for p in $(pgrep -f "auto_exit_v7"); do kill "$p" 2>/dev/null; done
sleep 2
rm -f /tmp/auto_exit_elon.lock
cat > /tmp/auto_exit_elon/posicion.json <<'JSON'
{
  "shares_yes": 0,
  "precio_entrada": 0,
  "vendido_yes": 0,
  "shares_no_cubierta": 0,
  "ultima_accion": null,
  "triggers_disparados": [],
  "nota": "reset por user (posicion 120-139 ya cerrada manualmente)"
}
JSON
echo "[parado] v7 detenido"
echo "[reset] /tmp/auto_exit_elon/posicion.json:"
cat /tmp/auto_exit_elon/posicion.json
echo
echo "[check] no hay procesos auto_exit_v7:"
pgrep -f "auto_exit_v7" || echo "  (ninguno)"
