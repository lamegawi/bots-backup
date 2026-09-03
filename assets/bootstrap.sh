#!/bin/bash
# BOOTSTRAP: prepara Hetzner para ejecutar el diagnóstico
# 1. Descarga el script principal
# 2. Crea el archivo del token
# Ejecutar UNA VEZ como root: bash bootstrap.sh
set -e
TOKEN_FILE="/root/.diag_token"
SCRIPT="/root/diag_y_publica.sh"

# El token va embebido en este bootstrap (es el PAT del user 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)
# Si lo subes a Hetzner manualmente, puedes editar esta línea
TOKEN="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"

echo "=== 1. Guardando token ==="
echo -n "$TOKEN" > $TOKEN_FILE
chmod 600 $TOKEN_FILE
echo "  Token guardado en $TOKEN_FILE"

echo "=== 2. Descargando script de diagnóstico ==="
curl -sL https://raw.githubusercontent.com/lamegawi/bots-backup/arena/01a058fe-bots-backup/scripts_despliegue/diag_y_publica.sh -o $SCRIPT
chmod +x $SCRIPT
echo "  Script descargado en $SCRIPT"

echo ""
echo "=== Listo. Para ejecutar el diagnóstico: ==="
echo "  bash $SCRIPT"
echo ""
echo "El script subirá el resultado a:"
echo "  https://github.com/lamegawi/bots-backup/tree/diag-public/diag_hetzner/"
