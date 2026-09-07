#!/usr/bin/env bash
# auto_exit_elon_4_11.sh
#   Vigila el mercado "Will Elon Musk post 120-139 tweets Sep 4-11, 2026"
#   Cada 15 min consulta la API de Polymarket y:
#
#   CONDICIONES DE VENTA (YES 120-139):
#     - precio YES >= 0.10  → vender 1/3 de la posición
#     - precio YES >= 0.20  → vender 1/2 de lo que quede
#     - precio YES >= 0.30  → vender TODO lo que quede
#     - tweet_count >= 100  → vender 1/3 (emergencia, ya no llegaremos)
#     - tweet_count >= 120  → vender 1/2
#     - tweet_count >= 140  → vender TODO
#   CONDICIONES DE COMPRA (NO 160-179 si quieres cubrir):
#     - precio NO 160-179 <= 0.30  → no compra (mercado en contra)
#     - precio NO 160-179 <= 0.10  → comprar 1/3 del bankroll
#
#   Cada acción se publica a diag-public con detalle de la decisión.
#
# Uso:
#   AUTO_BANKROLL_USD=20 bash auto_exit_elon_4_11.sh
#
# Variables de entorno:
#   AUTO_BANKROLL_USD  capital total a arriesgar (default 20)
#   INTERVALO_S        segundos entre chequeos (default 900 = 15min)
#   DRY_RUN            si "1" no opera, solo publica
#   POLY_KEY           API key Polymarket (si está)
set -u

API_MERCADO="https://gamma-api.polymarket.com/markets?slug=elon-musk-of-tweets-september-4-september-11-2026"
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")
BANKROLL=${AUTO_BANKROLL_USD:-20}
INTERVALO_S=${INTERVALO_S:-900}
DRY_RUN=${DRY_RUN:-0}

LOG_DIR="/tmp/auto_exit_elon"
mkdir -p "$LOG_DIR"

# Estado de la posición
POS_FILE="/tmp/auto_exit_elon/posicion.json"
if [ ! -f "$POS_FILE" ]; then
  cat > "$POS_FILE" <<JSON
{
  "shares_yes": 230.8,
  "precio_entrada": 0.0260,
  "vendido_yes": 0,
  "shares_no_cubierta": 0,
  "ultima_accion": null
}
JSON
fi

leer_precio_y_conteo() {
  curl -s --max-time 20 "$API_MERCADO" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if not data: sys.exit(0)
    m = data[0] if isinstance(data, list) else data
    outs = m.get('outcomes', '[]')
    pris = m.get('outcomePrices', '[]')
    if isinstance(outs, str): outs = json.loads(outs)
    if isinstance(pris, str): pris = json.loads(pris)
    p120_139 = None
    no_160_179 = None
    for o, p in zip(outs, pris):
        try:
            v = float(p)
        except Exception:
            continue
        if '120-139' in o and 'less' not in o.lower() and 'more' not in o.lower():
            p120_139 = v
        if '160-179' in o and 'less' not in o.lower() and 'more' not in o.lower():
            no_160_179 = v
    print('CONTAJE:', m.get('tweetCount') or m.get('tweet_count') or 0)
    print('P_YES_120_139:', p120_139)
    print('P_NO_160_179:', no_160_179)
    print('CERRADO:', m.get('closed'))
    print('END:', m.get('endDate'))
except Exception as e:
    print('ERROR:', e)
" 2>/dev/null
}

vender_yes() {
  local n_shares="$1"
  local motivo="$2"
  local precio_actual="$3"
  local ts=$(date -u +%Y%m%d_%H%M%S)
  local log="$LOG_DIR/sell_${ts}.log"
  {
    echo "=== VENTA YES 120-139 @ $(date -u) ==="
    echo "Motivo: $motivo"
    echo "Shares: $n_shares"
    echo "Precio estimado: $precio_actual"
    echo "DRY_RUN=$DRY_RUN"
  } > "$log"

  if [ "$DRY_RUN" = "1" ]; then
    echo "[DRY] vendería $n_shares YES @ $precio_actual"
  else
    # Aquí iría la llamada real a la CLOB de Polymarket.
    # Placeholder: registramos la decisión y marcamos en POS_FILE
    python3 -c "
import json
p = json.load(open('$POS_FILE'))
p['vendido_yes'] += $n_shares
p['ultima_accion'] = 'venta $n_shares YES @ $precio_actual ($motivo)'
json.dump(p, open('$POS_FILE','w'), indent=2)
print('OK vendido_yes=', p['vendido_yes'])
"
  fi
  publicar_log "$log" "auto_exit sell $ts"
}

comprar_no() {
  local usd="$1"
  local motivo="$2"
  local precio_no="$3"
  local ts=$(date -u +%Y%m%d_%H%M%S)
  local log="$LOG_DIR/buy_${ts}.log"
  {
    echo "=== COMPRA NO 160-179 @ $(date -u) ==="
    echo "Motivo: $motivo"
    echo "USD: $usd"
    echo "Precio NO: $precio_no"
    echo "DRY_RUN=$DRY_RUN"
  } > "$log"

  if [ "$DRY_RUN" = "1" ]; then
    echo "[DRY] compraría \$usd NO @ $precio_no"
  else
    python3 -c "
import json
p = json.load(open('$POS_FILE'))
p['shares_no_cubierta'] += $usd / $precio_no
p['ultima_accion'] = 'compra NO 160-179 por \$$usd @ $precio_no ($motivo)'
json.dump(p, open('$POS_FILE','w'), indent=2)
print('OK no_shares=', p['shares_no_cubierta'])
"
  fi
  publicar_log "$log" "auto_exit buy $ts"
}

publicar_log() {
  local f="$1"
  local msg="$2"
  local name=$(basename "$f")
  [ -z "$TOK" ] && { echo "[no-token] $f"; return; }
  local b64=$(base64 -w0 "$f")
  local payload=$(python3 -c "import json,sys;print(json.dumps({'message':sys.argv[1],'branch':'diag-public','content':sys.argv[2]}))" "$msg" "$b64")
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X PUT \
    -H "Authorization: token ${TOK}" \
    -H "Content-Type: application/json" \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${name}?ref=diag-public" \
    -d "$payload"
}

publicar_estado() {
  local ts=$(date -u +%Y%m%d_%H%M%S)
  local log="$LOG_DIR/estado_${ts}.log"
  cp "$POS_FILE" "$log"
  publicar_log "$log" "auto_exit estado $ts"
}

# ===== LOOP =="
echo "[auto_exit] bankroll=\$$BANKROLL  intervalo=${INTERVALO_S}s  dry_run=$DRY_RUN"
while true; do
  TS=$(date -u +%Y%m%d_%H%M%S)
  TS_H=$(date -u "+%Y-%m-%d %H:%M:%S UTC")
  echo
  echo "=== Chequeo $TS_H ==="

  RAW=$(leer_precio_y_conteo)
  echo "$RAW"

  CONTAJE=$(echo "$RAW" | grep "^CONTAJE:" | awk '{print $2}')
  P_YES=$(echo "$RAW" | grep "^P_YES_120_139:" | awk '{print $2}')
  P_NO=$(echo "$RAW" | grep "^P_NO_160_179:" | awk '{print $2}')
  CERRADO=$(echo "$RAW" | grep "^CERRADO:" | awk '{print $2}')

  # Cargar posición
  POS=$(cat "$POS_FILE")
  VENDIDO=$(echo "$POS" | python3 -c "import json,sys; print(json.load(sys.stdin)['vendido_yes'])")
  RESTANTE=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_yes'] - p['vendido_yes'])")
  NO_CUBIERTA=$(echo "$POS" | python3 -c "import json,sys; print(json.load(sys.stdin)['shares_no_cubierta'])")

  echo "Pos: total=230.8  vendido=$VENDIDO  restante=$RESTANTE  no_cubierta=$NO_CUBIERTA"
  echo "Mercado: contaje=$CONTAJE  yes_120_139=$P_YES  no_160_179=$P_NO  cerrado=$CERRADO"

  DECISION="ninguna"

  # Si ya vendimos todo, parar
  if python3 -c "import sys; sys.exit(0 if float('$RESTANTE') <= 0.1 else 1)"; then
    echo "[fin] posición liquidada"
    publicar_estado
    break
  fi

  # Condiciones de precio YES
  if [ -n "$P_YES" ] && [ "$P_YES" != "None" ]; then
    if python3 -c "import sys; sys.exit(0 if float('$P_YES') >= 0.30 else 1)"; then
      vender_yes "$RESTANTE" "precio YES >= 0.30 (emergencia)" "$P_YES"
      DECISION="vender_todo"
    elif python3 -c "import sys; sys.exit(0 if float('$P_YES') >= 0.20 else 1)"; then
      MITAD=$(python3 -c "print(round($RESTANTE / 2, 2))")
      vender_yes "$MITAD" "precio YES >= 0.20" "$P_YES"
      DECISION="vender_mitad"
    elif python3 -c "import sys; sys.exit(0 if float('$P_YES') >= 0.10 else 1)"; then
      TERCIO=$(python3 -c "print(round($RESTANTE / 3, 2))")
      vender_yes "$TERCIO" "precio YES >= 0.10" "$P_YES"
      DECISION="vender_tercio"
    fi
  fi

  # Condiciones de contaje
  if [ -n "$CONTAJE" ] && [ "$CONTAJE" != "0" ]; then
    if [ "$CONTAJE" -ge 140 ] 2>/dev/null; then
      vender_yes "$RESTANTE" "tweet_count >= 140 (perdido)" "0"
      DECISION="vender_todo_emergencia"
    elif [ "$CONTAJE" -ge 120 ] 2>/dev/null; then
      MITAD=$(python3 -c "print(round($RESTANTE / 2, 2))")
      vender_yes "$MITAD" "tweet_count >= 120" "0"
      DECISION="vender_mitad_emergencia"
    elif [ "$CONTAJE" -ge 100 ] 2>/dev/null; then
      TERCIO=$(python3 -c "print(round($RESTANTE / 3, 2))")
      vender_yes "$TERCIO" "tweet_count >= 100" "0"
      DECISION="vender_tercio_emergencia"
    fi
  fi

  # Cobertura con NO 160-179 si el precio NO es muy bajo (mercado en contra)
  if [ -n "$P_NO" ] && [ "$P_NO" != "None" ] && [ "$NO_CUBIERTA" = "0" ]; then
    if python3 -c "import sys; sys.exit(0 if float('$P_NO') <= 0.10 else 1)"; then
      USD_INVERTIR=$(python3 -c "print(round($BANKROLL * 0.33, 2))")
      comprar_no "$USD_INVERTIR" "cobertura con NO 160-179 (precio <= 0.10)" "$P_NO"
      DECISION="cubrir_no"
    fi
  fi

  echo "Decisión: $DECISION"
  publicar_estado

  # Si está cerrado el mercado, parar
  if [ "$CERRADO" = "True" ]; then
    echo "[fin] mercado cerrado"
    break
  fi

  sleep "$INTERVALO_S"
done
