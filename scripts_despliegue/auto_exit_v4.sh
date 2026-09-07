#!/usr/bin/env bash
# auto_exit_v4.sh — extracción completa de jina, MD largo + CLOB
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

# Scrape con jina, devuelve el MD completo y extrae info
scrape_mercado() {
  local url="https://polymarket.com/event/elon-musk-of-tweets-september-4-september-11-2026"
  local out
  out=$(curl -s --max-time 30 -x "$PROXY" -H "Accept: text/plain" -H "x-no-cache: true" \
    -A "Mozilla/5.0" "https://r.jina.ai/${url}" 2>&1)
  # Guardar el MD completo a un archivo temporal
  echo "$out" > "$LOG_DIR/_last_jina.md"
  echo "$out" | python3 -c "
import sys, re, json
md = sys.stdin.read()
# TWEET COUNT
m_tc = re.search(r'TWEET\s*COUNT\s*\n?\s*(\d+)', md, re.IGNORECASE)
print('CONTAJE', m_tc.group(1) if m_tc else 0)
# Tiempo restante
m_t = re.search(r'(\d+)\s*DAYS?\s*(\d+)\s*HOURS?\s*(\d+)\s*MIN', md, re.IGNORECASE)
if m_t:
    print('DIAS', m_t.group(1))
    print('HORAS', m_t.group(2))
    print('MIN', m_t.group(3))
# Bins: buscar rangos '120-139' seguidos de porcentaje
# Típico formato: '120-139 0.5%' o '120-139\n0.5%'
bins = ['120-139','140-159','160-179','180-199','200-219']
for b in bins:
    m = re.search(re.escape(b) + r'[\s\S]{0,40}?(\d+(?:\.\d+)?)\s*%', md)
    if m:
        print(f'PCT_{b}', m.group(1))
# Buscar conditionId en el HTML
m_c = re.search(r'conditionId[\"\\'\s:=]+(0x[0-9a-fA-F]{40,64})', md)
if m_c:
    print('COND', m_c.group(1))
" 2>&1
}

# CLOB directo
clob_precio() {
  local cond="$1"
  if [ -z "$cond" ]; then echo "NO_COND"; return; fi
  curl -s --max-time 20 \
    "https://clob.polymarket.com/markets/${cond}" \
    | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print('CLOSED', d.get('closed'))
    print('ACCEPTING', d.get('accepting_orders'))
    toks = d.get('tokens', [])
    for t in toks:
        o = t.get('outcome','')
        if '120' in o or '160' in o or '180' in o or '200' in o or '140' in o:
            print(f\"P_{o}\", t.get('price'))
except Exception as e:
    print('ERR', e)
" 2>&1
}

while true; do
  TS=$(date -u +%Y%m%d_%H%M%S)
  TS_H=$(date -u "+%Y-%m-%d %H:%M:%S UTC")
  CYCLE="$LOG_DIR/ciclo_${TS}.log"
  JINA_MD="$LOG_DIR/jina_${TS}.md"
  {
    echo "=== Chequeo $TS_H ==="
    echo
    echo "== jina scrap =="
    SCRAPE=$(scrape_mercado)
    echo "$SCRAPE"

    CONTAJE=$(echo "$SCRAPE" | grep "^CONTAJE " | awk '{print $2}')
    DIAS=$(echo "$SCRAPE" | grep "^DIAS " | awk '{print $2}')
    COND=$(echo "$SCRAPE" | grep "^COND " | awk '{print $2}')
    P120=$(echo "$SCRAPE" | grep "^PCT_120-139 " | awk '{print $2}')
    P160=$(echo "$SCRAPE" | grep "^PCT_160-179 " | awk '{print $2}')

    echo
    echo "== clob probe =="
    if [ -n "$COND" ]; then
      CLOB=$(clob_precio "$COND")
      echo "$CLOB"
      C_P120=$(echo "$CLOB" | grep "^P_120-139 " | awk '{print $2}')
    else
      echo "no hay condition_id del jina"
    fi

    RESTANTE=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_yes']-p['vendido_yes'])")
    NO_CUB=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_no_cubierta'])")
    echo
    echo "Pos: restante=$RESTANTE  no_cub=$NO_CUB  bankroll=\$$BANKROLL  dry_run=$DRY_RUN"
    echo "Mercado: contaje=$CONTAJE  pct_120-139=$P120  pct_160-179=$P160  clob_120=$C_P120  cond=$COND"

    DECISION="ninguna"

    # Si CLOB dio precio, usarlo
    P_USAR="$C_P120"
    [ -z "$P_USAR" ] && P_USAR="$P120"

    if [ -n "$P_USAR" ] && [ "$P_USAR" != "None" ]; then
      if python3 -c "import sys; sys.exit(0 if float('$P_USAR') >= 0.30 else 1)" 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE,2))")
        echo "DECISION: vender TODO ($N) YES @ $P_USAR (>=0.30)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES @ $P_USAR (>=0.30)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_todo_precio"
      elif python3 -c "import sys; sys.exit(0 if float('$P_USAR') >= 0.20 else 1)" 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE/2,2))")
        echo "DECISION: vender MITAD ($N) YES @ $P_USAR (>=0.20)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES @ $P_USAR (>=0.20)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_mitad_precio"
      elif python3 -c "import sys; sys.exit(0 if float('$P_USAR') >= 0.10 else 1)" 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE/3,2))")
        echo "DECISION: vender TERCIO ($N) YES @ $P_USAR (>=0.10)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES @ $P_USAR (>=0.10)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_tercio_precio"
      fi
    fi

    if [ -n "$CONTAJE" ] && [ "$CONTAJE" != "0" ] && [ "$DECISION" = "ninguna" ]; then
      if [ "$CONTAJE" -ge 140 ] 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE,2))")
        echo "DECISION: vender TODO ($N) YES (count=$CONTAJE >= 140)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES (count>=140)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_todo_count"
      elif [ "$CONTAJE" -ge 120 ] 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE/2,2))")
        echo "DECISION: vender MITAD ($N) YES (count=$CONTAJE >= 120)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES (count>=120)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_mitad_count"
      elif [ "$CONTAJE" -ge 100 ] 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE/3,2))")
        echo "DECISION: vender TERCIO ($N) YES (count=$CONTAJE >= 100)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES (count>=100)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_tercio_count"
      fi
    fi

    echo
    echo "Decision final: $DECISION"
    echo "Posicion:"
    cat "$POS_FILE"
  } > "$CYCLE" 2>&1

  # Publicar el MD completo para análisis
  cp "$LOG_DIR/_last_jina.md" "$JINA_MD"
  if [ -f "$JINA_MD" ] && [ -s "$JINA_MD" ]; then
    publicar "$JINA_MD" "auto_exit jina md $TS"
  fi
  publicar "$CYCLE" "auto_exit ciclo $TS"
  cp "$POS_FILE" "$LOG_DIR/estado_${TS}.log"
  publicar "$LOG_DIR/estado_${TS}.log" "auto_exit estado $TS"

  RESTANTE=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_yes']-p['vendido_yes'])")
  if python3 -c "import sys; sys.exit(0 if float('$RESTANTE') <= 0.1 else 1)" 2>/dev/null; then
    echo "[posicion liquidada]"
    break
  fi
  sleep "$INTERVALO_S"
done
