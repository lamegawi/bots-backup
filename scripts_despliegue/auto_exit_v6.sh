#!/usr/bin/env bash
# auto_exit_v6.sh — usa scripts/parse_jina.py externo (sin heredoc problemático)
set -u
LOCK=/tmp/auto_exit_elon.lock
if [ -f "$LOCK" ]; then
  PID=$(cat "$LOCK")
  if kill -0 "$PID" 2>/dev/null; then echo "[ya corriendo PID $PID]"; exit 0; fi
  rm -f "$LOCK"
fi
echo $$ > "$LOCK"
trap "rm -f $LOCK" EXIT

TS_IP=${TS_IP:-100.83.57.99}
PROXY="http://${TS_IP}:8888"
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

# Asegurar parse_jina.py disponible
PARSE_PY="/tmp/parse_jina.py"
if [ ! -f "$PARSE_PY" ]; then
  curl -sL -o "$PARSE_PY" https://raw.githubusercontent.com/lamegawi/bots-backup/HEAD/scripts_despliegue/parse_jina.py
fi

publicar_uno() {
  local f="$1"; local msg="$2"
  local name=$(basename "$f")
  [ -z "$TOK" ] && return 1
  [ ! -f "$f" ] && return 1
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

scrape_mercado() {
  local url="https://polymarket.com/event/elon-musk-of-tweets-september-4-september-11-2026"
  curl -s --max-time 30 -x "$PROXY" -H "Accept: text/plain" -H "x-no-cache: true" \
    -A "Mozilla/5.0" "https://r.jina.ai/${url}" > "$LOG_DIR/_last_jina.md" 2>/dev/null
  python3 "$PARSE_PY" "$LOG_DIR/_last_jina.md" 2>&1
}

clob_precio() {
  local cond="$1"
  [ -z "$cond" ] && { echo "NO_COND"; return; }
  curl -s --max-time 20 "https://clob.polymarket.com/markets/${cond}" \
    | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    toks = d.get('tokens', [])
    for t in toks:
        o = t.get('outcome','')
        if any(x in o for x in ['120','140','160','180','200']):
            print('P_' + o, t.get('price'))
except Exception as e: print('ERR', e)
" 2>&1
}

while true; do
  TS=$(date -u +%Y%m%d_%H%M%S)
  CYCLE="$LOG_DIR/ciclo_${TS}.log"
  SCRAPE=$(scrape_mercado)
  CONTAJE=$(echo "$SCRAPE" | grep "^CONTAJE " | awk '{print $2}')
  COND=$(echo "$SCRAPE" | grep "^COND " | awk '{print $2}')
  P120=$(echo "$SCRAPE" | grep "^PCT_120-139 " | awk '{print $2}')

  CLOB=""
  C_P120=""
  if [ -n "$COND" ]; then
    CLOB=$(clob_precio "$COND")
    C_P120=$(echo "$CLOB" | grep "^P_120-139 " | awk '{print $2}')
  fi

  P_USAR="${C_P120:-${P120:-}}"

  RESTANTE=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_yes']-p['vendido_yes'])")
  NO_CUB=$(python3 -c "import json; print(json.load(open('$POS_FILE'))['shares_no_cubierta'])")

  DECISION="ninguna"
  if [ -n "$P_USAR" ] && [ "$P_USAR" != "None" ]; then
    if python3 -c "import sys; sys.exit(0 if float('$P_USAR') >= 0.30 else 1)" 2>/dev/null; then
      N=$(python3 -c "print(round($RESTANTE,2))")
      DECISION="VENDER_TODO $N YES @ $P_USAR (>=0.30)"
    elif python3 -c "import sys; sys.exit(0 if float('$P_USAR') >= 0.20 else 1)" 2>/dev/null; then
      N=$(python3 -c "print(round($RESTANTE/2,2))")
      DECISION="VENDER_MITAD $N YES @ $P_USAR (>=0.20)"
    elif python3 -c "import sys; sys.exit(0 if float('$P_USAR') >= 0.10 else 1)" 2>/dev/null; then
      N=$(python3 -c "print(round($RESTANTE/3,2))")
      DECISION="VENDER_TERCIO $N YES @ $P_USAR (>=0.10)"
    fi
  fi
  if [ "$DECISION" = "ninguna" ] && [ -n "$CONTAJE" ] && [ "$CONTAJE" != "0" ]; then
    if [ "$CONTAJE" -ge 140 ] 2>/dev/null; then
      N=$(python3 -c "print(round($RESTANTE,2))")
      DECISION="VENDER_TODO $N YES (count=$CONTAJE >=140)"
    elif [ "$CONTAJE" -ge 120 ] 2>/dev/null; then
      N=$(python3 -c "print(round($RESTANTE/2,2))")
      DECISION="VENDER_MITAD $N YES (count=$CONTAJE >=120)"
    elif [ "$CONTAJE" -ge 100 ] 2>/dev/null; then
      N=$(python3 -c "print(round($RESTANTE/3,2))")
      DECISION="VENDER_TERCIO $N YES (count=$CONTAJE >=100)"
    fi
  fi
  if [ -n "$DECISION" ] && [ "$DECISION" != "ninguna" ]; then
    python3 -c "
import json
p = json.load(open('$POS_FILE'))
if 'TODO' in '''$DECISION''':
    p['vendido_yes'] += $RESTANTE
elif 'MITAD' in '''$DECISION''':
    p['vendido_yes'] += $RESTANTE/2
elif 'TERCIO' in '''$DECISION''':
    p['vendido_yes'] += $RESTANTE/3
p['ultima_accion'] = '''$DECISION'''
json.dump(p, open('$POS_FILE','w'), indent=2)
"
  fi

  {
    echo "=== Chequeo $(date -u "+%Y-%m-%d %H:%M:%S UTC") ==="
    echo "Pos: restante=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_yes']-p['vendido_yes'])")  no_cub=$(python3 -c "import json; print(json.load(open('$POS_FILE'))['shares_no_cubierta'])")  bankroll=\$$BANKROLL  dry_run=$DRY_RUN"
    echo
    echo "-- jina scrap --"
    echo "$SCRAPE"
    echo
    echo "-- CLOB --"
    echo "$CLOB"
    echo
    echo "P_USAR = $P_USAR"
    echo
    echo "DECISION: $DECISION"
    echo
    cat "$POS_FILE"
  } > "$CYCLE"
  publicar_uno "$CYCLE" "auto_exit v6 ciclo $TS"

  RESTANTE_NOW=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_yes']-p['vendido_yes'])")
  if python3 -c "import sys; sys.exit(0 if float('$RESTANTE_NOW') <= 0.1 else 1)" 2>/dev/null; then
    echo "[posicion liquidada]"; break
  fi
  sleep "$INTERVALO_S"
done
