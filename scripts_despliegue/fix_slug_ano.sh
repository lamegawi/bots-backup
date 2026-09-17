#!/usr/bin/env bash
# fix_slug_ano.sh — añadir año al final de los slugs en mercado_polymarket.py
# PROBLEMA: Polymarket usa slugs tipo "september-17-september-19-2026" (con año)
#           pero el script generaba "september-17-september-19" (sin año)
#           Esto causaba que mercados nuevos no se detectaran.
# FIX: Añadir -{d2.year} al final de las f-strings de líneas 119 y 123.
# APLICADO A: bot-polymarket-elon, bot-polymarket-elon-semanal, bot-polymarket-elon-mensual
set -euo pipefail
TS=$(date -u +%Y%m%d_%H%M%S)

echo "=== FIX SLUG AÑO · ${TS} UTC ==="

DIRS=(
  /opt/polymarket/bot-polymarket-elon
  /opt/polymarket/bot-polymarket-elon-semanal
  /opt/polymarket/bot-polymarket-elon-mensual
)

for D in "${DIRS[@]}"; do
  F="$D/mercado_polymarket.py"
  if [ ! -f "$F" ]; then
    echo "  ⚠️  no existe $F, skip"
    continue
  fi
  echo
  echo "== $F =="

  # Backup
  cp "$F" "${F}.bak_slug_${TS}"
  echo "  backup: ${F}.bak_slug_${TS}"

  # Aplicar fix: añadir -{d2.year} al final
  sed -i 's|elon-musk-of-tweets-{MESES_NOMBRE\[d1.month\]}-{d1.day}-{MESES_NOMBRE\[d2.month\]}-{d2.day}|elon-musk-of-tweets-{MESES_NOMBRE[d1.month]}-{d1.day}-{MESES_NOMBRE[d2.month]}-{d2.day}-{d2.year}|g' "$F"

  # Verificar
  echo "  líneas modificadas:"
  grep -n "of-tweets-{MESES_NOMBRE" "$F" | head -3
  python3 -m py_compile "$F" && echo "  ✅ compila"
done

echo
echo "== Refrescar mercado_activo.json (bot 48h) =="
cd /opt/polymarket/bot-polymarket-elon
python3 mercado_polymarket.py 2>&1 | grep -E "September [0-9]+ - September [0-9]+" | grep "ABIERTO" || echo "  ⚠️ ningún 48h ABIERTO"

echo
echo "== Listo. El siguiente ciclo del bot detectará el nuevo mercado. =="
