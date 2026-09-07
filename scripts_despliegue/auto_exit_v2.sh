#!/usr/bin/env bash
# auto_exit_v2.sh — versión robusta con lockfile, logs siempre, y heartbeat
set -u
LOCK=/tmp/auto_exit_elon.lock
if [ -f "$LOCK" ]; then
  PID=$(cat "$LOCK")
  if kill -0 "$PID" 2>/dev/null; then
    echo "[ya corriendo PID $PID]"
    exit 0
  fi
  rm -f "$LOCK"
fi
echo $$ > "$LOCK"
trap "rm -f $LOCK" EXIT

API_MERCADO="https://gamma-api.polymarket.com/markets?slug=elon-musk-of-tweets-september-4-september-11-2026"
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")
BANKROLL=${AUTO_BANKROLL_USD:-20}
INTERVALO_S=${INTERVALO_S:-900}
DRY_RUN=${DRY_RUN:-1}

LOG_DIR="/tmp/auto_exit_elon"
mkdir -p "$LOG_DIR"

POS_FILE="$LOG_DIR/posicion.json"
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

publicar() {
  local f="$1"; local msg="$2"
  local name=$(basename "$f")
  [ -z "$TOK" ] && { echo "[no-token]"; return 1; }
  [ ! -f "$f" ] && { echo "[no-file $f]"; return 1; }
  local b64=$(base64 -w0 "$f")
  local payload=$(python3 -c "import json,sys;print(json.dumps({'message':sys.argv[1],'branch':'diag-public','content':sys.argv[2]}))" "$msg" "$b64")
  local code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X PUT \
    -H "Authorization: token ${TOK}" \
    -H "Content-Type: application/json" \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${name}?ref=diag-public" \
    -d "$payload")
  echo "[pub $code] $name"
}

leer_mercado() {
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
    p120=None; no160=None
    for o, p in zip(outs, pris):
        try: v = float(p)
        except: continue
        if '120-139' in o and 'less' not in o.lower() and 'more' not in o.lower():
            p120 = v
        if '160-179' in o and 'less' not in o.lower() and 'more' not in o.lower():
            no160 = v
    print('CONTAJE', m.get('tweetCount') or m.get('tweet_count') or 0)
    print('P_YES_120_139', p120)
    print('P_NO_160_179', no160)
    print('CERRADO', m.get('closed'))
except Exception as e:
    print('ERROR', e)
" 2>&1
}

while true; do
  TS=$(date -u +%Y%m%d_%H%M%S)
  TS_H=$(date -u "+%Y-%m-%d %H:%M:%S UTC")
  CYCLE="$LOG_DIR/ciclo_${TS}.log"
  {
    echo "=== Chequeo $TS_H ==="
    RAW=$(leer_mercado)
    echo "$RAW"

    CONTAJE=$(echo "$RAW" | grep "^CONTAJE " | awk '{print $2}')
    P_YES=$(echo "$RAW" | grep "^P_YES_120_139 " | awk '{print $2}')
    P_NO=$(echo "$RAW" | grep "^P_NO_160_179 " | awk '{print $2}')
    CERRADO=$(echo "$RAW" | grep "^CERRADO " | awk '{print $2}')

    RESTANTE=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_yes']-p['vendido_yes'])")
    NO_CUB=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_no_cubierta'])")
    echo "Pos: restante=$RESTANTE  no_cub=$NO_CUB  bankroll=\$$BANKROLL  dry_run=$DRY_RUN"

    DECISION="ninguna"

    # Venta escalonada por precio YES
    if [ -n "$P_YES" ] && [ "$P_YES" != "None" ]; then
      if python3 -c "import sys; sys.exit(0 if float('$P_YES') >= 0.30 else 1)" 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE,2))")
        echo "DECISION: vender TODO ($N) YES @ $P_YES (precio >= 0.30)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES @ $P_YES (>=0.30)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_todo_precio"
      elif python3 -c "import sys; sys.exit(0 if float('$P_YES') >= 0.20 else 1)" 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE/2,2))")
        echo "DECISION: vender MITAD ($N) YES @ $P_YES (precio >= 0.20)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES @ $P_YES (>=0.20)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_mitad_precio"
      elif python3 -c "import sys; sys.exit(0 if float('$P_YES') >= 0.10 else 1)" 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE/3,2))")
        echo "DECISION: vender TERCIO ($N) YES @ $P_YES (precio >= 0.10)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES @ $P_YES (>=0.10)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_tercio_precio"
      fi
    fi

    # Venta por contaje (emergencia)
    if [ -n "$CONTAJE" ] && [ "$CONTAJE" != "0" ] && [ "$DECISION" = "ninguna" ]; then
      if [ "$CONTAJE" -ge 140 ] 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE,2))")
        echo "DECISION: vender TODO ($N) YES (contaje=$CONTAJE >= 140)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES (count>=140)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_todo_count"
      elif [ "$CONTAJE" -ge 120 ] 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE/2,2))")
        echo "DECISION: vender MITAD ($N) YES (contaje=$CONTAJE >= 120)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES (count>=120)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_mitad_count"
      elif [ "$CONTAJE" -ge 100 ] 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE/3,2))")
        echo "DECISION: vender TERCIO ($N) YES (contaje=$CONTAJE >= 100)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES (count>=100)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_tercio_count"
      fi
    fi

    # Cobertura con NO 160-179
    if [ -n "$P_NO" ] && [ "$P_NO" != "None" ] && python3 -c "import sys; sys.exit(0 if float('$NO_CUB')==0 else 1)" 2>/dev/null; then
      if python3 -c "import sys; sys.exit(0 if float('$P_NO') <= 0.10 else 1)" 2>/dev/null; then
        USD=$(python3 -c "print(round($BANKROLL*0.33,2))")
        echo "DECISION: comprar \$$USD NO 160-179 @ $P_NO (cobertura)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['shares_no_cubierta']+=$USD/float('$P_NO');p['ultima_accion']='compra \$$USD NO 160-179 @ $P_NO';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="cubrir_no"
      fi
    fi

    echo "Decision final: $DECISION"
    echo "Posicion:"
    cat "$POS_FILE"
  } > "$CYCLE" 2>&1

  # Publicar ciclo + estado
  publicar "$CYCLE" "auto_exit ciclo $TS"
  cp "$POS_FILE" "$LOG_DIR/estado_${TS}.log"
  publicar "$LOG_DIR/estado_${TS}.log" "auto_exit estado $TS"

  if [ "$CERRADO" = "True" ]; then
    echo "[mercado cerrado]"
    break
  fi
  RESTANTE=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_yes']-p['vendido_yes'])")
  if python3 -c "import sys; sys.exit(0 if float('$RESTANTE') <= 0.1 else 1)" 2>/dev/null; then
    echo "[posicion liquidada]"
    break
  fi

  sleep "$INTERVALO_S"
done
