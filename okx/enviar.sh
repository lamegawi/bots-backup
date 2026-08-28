#!/bin/bash
# ENVIAR - ejecuta el recolector del OKX y sube el diagnostico.
bash /root/recolector.sh > /dev/null 2>&1
if [ ! -f /root/diagnostico_completo.txt ]; then
    echo "ERROR: no se genero el diagnostico"
    exit 1
fi
echo "Subiendo diagnostico ($(wc -c < /root/diagnostico_completo.txt) bytes)..."
RESP=$(curl -s -m 90 -F "file=@/root/diagnostico_completo.txt" https://tmpfiles.org/api/v1/upload)
URL=$(echo "$RESP" | grep -oE 'https://tmpfiles\.org/[^"]+')
if [ -z "$URL" ]; then
    echo "ERROR subiendo: $RESP"
    exit 1
fi
echo ""
echo "=================================================="
echo "  COPIA ESTA URL Y PEGASELA AL ASISTENTE EN EL CHAT:"
echo ""
echo "  $URL"
echo ""
echo "  (vale 60 minutos; luego caduca sola)"
echo "=================================================="
