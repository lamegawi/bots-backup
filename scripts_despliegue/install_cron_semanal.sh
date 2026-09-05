#!/bin/bash
# Instala los crons de seguimiento_semanal y reset_mensual.
# Reemplaza cualquier crontab anterior.

SCRIPT_SEM=/root/seguimiento_semanal.py
SCRIPT_RESET=/root/reset_mensual.py
LOG_SEM=/root/semanal.log
LOG_RESET=/root/reset.log

# Verificar que los scripts existen
for s in $SCRIPT_SEM $SCRIPT_RESET; do
  if [ ! -f "$s" ]; then
    echo "ERROR: $s no existe. Bajalo primero con:"
    echo "  curl -sL https://raw.githubusercontent.com/lamegawi/bots-backup/arena/01a058fe-bots-backup/scripts_despliegue/seguimiento_semanal.py -o $s"
    echo "  curl -sL https://raw.githubusercontent.com/lamegawi/bots-backup/arena/01a058fe-bots-backup/scripts_despliegue/reset_mensual_finalizadas.py -o $s"
    exit 1
  fi
done

# Crear las 2 lineas de cron
LINEA_SEM="0 9 * * 1 /usr/bin/python3 -u $SCRIPT_SEM >> $LOG_SEM 2>&1"
LINEA_RESET="1 0 1 * * /usr/bin/python3 -u $SCRIPT_RESET >> $LOG_RESET 2>&1"

# Instalar (reemplaza el crontab actual con las 2 lineas)
{
  echo "$LINEA_SEM"
  echo "$LINEA_RESET"
} | crontab -

echo "OK: crons instalados (2 lineas)"
echo ""
echo "Linea 1: $LINEA_SEM"
echo "Linea 2: $LINEA_RESET"
echo ""
echo "Para verificar:"
echo "  crontab -l"
echo ""
echo "Calendario:"
echo "  - Cada lunes 9:00  -> seguimiento_semanal.py"
echo "  - Cada dia 1, 0:01 -> reset_mensual.py"
echo ""
echo "Para desinstalar TODO:"
echo "  crontab -r"
