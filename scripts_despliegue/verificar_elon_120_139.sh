#!/bin/bash
# Verificar operacion abierta de Elon: 120-139 tweets
# El bot dice 26 tweets. Tengo que ver:
# 1. Que CSV tiene el bot (cuenta propia)
# 2. Que tweets hay REALMENTE en Twitter/X de Elon
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/elon_120_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== VERIFICAR OPERACION 120-139 TWEETS - $(date) ==="
echo ""
echo "== 1. Estado del bot (CSV que cuenta) =="
echo "Ultimo parte del bot de Elon (48h, semanal, mensual):"
for logf in /var/log/poly-elon.log /var/log/poly-semanal.log /var/log/poly-mensual.log; do
  if [ -f "$logf" ]; then
    echo ""
    echo "--- $logf (ultimas 8 lineas) ---"
    tail -8 "$logf"
  fi
done

echo ""
echo "== 2. CSVs del bot =="
for csv in /opt/polymarket/bot-polymarket-elon/datos_elon.csv \
          /opt/polymarket/bot-polymarket-elon-semanal/datos_elon.csv \
          /opt/polymarket/bot-polymarket-elon-mensual/datos_elon.csv; do
  if [ -f "$csv" ]; then
    echo ""
    echo "--- $csv (ultimas 15 lineas) ---"
    tail -15 "$csv"
  fi
done

echo ""
echo "== 3. mercado_activo.json (prediccion actual del bot) =="
for jf in /opt/polymarket/bot-polymarket-elon/mercado_activo.json \
          /opt/polymarket/bot-polymarket-elon-semanal/mercado_activo.json \
          /opt/polymarket/bot-polymarket-elon-mensual/mercado_activo.json; do
  if [ -f "$jf" ]; then
    echo ""
    echo "--- $jf ---"
    cat "$jf" | python3 -m json.tool 2>&1 | head -80
  fi
done

echo ""
echo "== 4. Tweets del periodo (4 sept - ahora) segun el bot =="
python3 << 'PYEOF'
import csv
import os
from datetime import datetime, timedelta, timezone

# Periodo de la operacion: September 4 to September 11
# Leer CSVs
for csv_path in [
    "/opt/polymarket/bot-polymarket-elon/datos_elon.csv",
    "/opt/polymarket/bot-polymarket-elon-semanal/datos_elon.csv",
    "/opt/polymarket/bot-polymarket-elon-mensual/datos_elon.csv",
]:
    if not os.path.exists(csv_path):
        continue
    print(f"\n--- {csv_path} ---")
    try:
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # Filtrar por fechas
        print(f"Total rows: {len(rows)}")
        if rows:
            print(f"Headers: {rows[0].keys()}")
        # Sumar tweets del periodo
        total_periodo = 0
        tweets_por_dia = {}
        for r in rows:
            fecha = r.get("fecha") or r.get("date") or list(r.values())[0]
            tweets = r.get("tweets") or r.get("count") or list(r.values())[1] if len(r) > 1 else "0"
            try:
                t = int(tweets)
            except:
                continue
            if "2026-09-0" in fecha or "2026-09-1" in fecha[:10]:
                # Solo del 4 al 11 sept
                dia = fecha[:10]
                if "2026-09-04" <= dia <= "2026-09-11":
                    tweets_por_dia[dia] = t
                    total_periodo += t
        print(f"Tweets del 4 al 11 sept: {total_periodo}")
        for dia in sorted(tweets_por_dia.keys()):
            print(f"  {dia}: {tweets_por_dia[dia]} tweets")
    except Exception as e:
        print(f"Error: {e}")
PYEOF

# Publicar
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/elon_120_${TS}.log"
  CONTenido=$(cat "$LOG")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'elon120 ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'elon120 ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo ""
  echo "Publicado en $RUTA"
fi
