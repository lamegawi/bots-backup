#!/bin/bash
# Instala el cron semanal para seguimiento_semanal.py
# Corre cada lunes a las 9:00 y guarda el log en /root/semanal.log

SCRIPT=/root/seguimiento_semanal.py
LOG=/root/semanal.log

# Verificar que el script existe
if [ ! -f "$SCRIPT" ]; then
    echo "ERROR: $SCRIPT no existe. Bajalo primero con:"
    echo "  curl -sL https://raw.githubusercontent.com/lamegawi/bots-backup/arena/01a058fe-bots-backup/scripts_despliegue/seguimiento_semanal.py -o $SCRIPT"
    exit 1
fi

# Crear la línea de cron
LINE="0 9 * * 1 /usr/bin/python3 -u $SCRIPT >> $LOG 2>&1"

# Instalar (reemplaza el crontab actual)
echo "$LINE" | crontab -

echo "OK: cron instalado"
echo "Linea: $LINE"
echo ""
echo "Para verificar:"
echo "  crontab -l"
echo ""
echo "Para desinstalar:"
echo "  crontab -r"
