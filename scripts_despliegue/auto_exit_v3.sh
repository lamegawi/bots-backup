#!/usr/bin/env bash
# auto_exit_v3.sh — usa jina (vía proxy PC) para scrapear polymarket.com
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

# Scrape con jina: pasa por el proxy PC
scrape_mercado() {
  local url="https://polymarket.com/event/elon-musk-of-tweets-september-4-september-11-2026"
  local out
  out=$(curl -s --max-time 30 -x "$PROXY" -H "Accept: text/plain" -A "Mozilla/5.0" \
    "https://r.jina.ai/${url}" 2>&1)
  echo "$out" | python3 -c "
import sys, re
md = sys.stdin.read()
# buscar 'TWEET COUNT' y el número
m_tc = re.search(r'TWEET\s*COUNT\s*\n?\s*(\d+)', md, re.IGNORECASE)
print('CONTAJE', m_tc.group(1) if m_tc else 0)
# buscar tiempo restante 'Xd Yh Zm'
m_t = re.search(r'(\d+)\s*DAYS?\s*(\d+)\s*HOURS?\s*(\d+)\s*MIN', md, re.IGNORECASE)
if m_t:
    print('TIEMPO_REST_DIAS', m_t.group(1))
    print('TIEMPO_REST_HORAS', m_t.group(2))
    print('TIEMPO_REST_MIN', m_t.group(3))
# buscar precios tipo 0.05
# Las cuotas YES aparecen como porcentaje implícito
print('MD_HEAD', md[:1500].replace('\n','|'))
" 2>&1
}

# Intento alternativo: API CLOB pública (que sí suele estar abierta)
clob_obtener_precios() {
  local slug="elon-musk-of-tweets-september-4-september-11-2026"
  # La CLOB API tiene un endpoint que devuelve el "midpoint" de cada token
  # Primero necesitamos el condition_id. Lo buscamos en la web de polymarket.
  local html
  html=$(curl -s --max-time 30 -x "$PROXY" -A "Mozilla/5.0" \
    "https://r.jina.ai/https://polymarket.com/event/${slug}" 2>&1)
  # Buscar conditionId en la respuesta
  local cond
  cond=$(echo "$html" | grep -oE '"conditionId"\s*:\s*"0x[0-9a-fA-F]{40,64}"' | head -1 | grep -oE '0x[0-9a-fA-F]+')
  echo "CONDITION_ID: ${cond:-NONE}"
  if [ -n "$cond" ] && [ "$cond" != "NONE" ]; then
    # Obtener precios con la CLOB
    curl -s --max-time 20 \
      "https://clob.polymarket.com/markets/${cond}" \
      | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    toks = d.get('tokens', [])
    for t in toks:
        o = t.get('outcome','')
        if '120' in o or '160' in o:
            print(f\"P_{o} {t.get('price','?')}\")
except Exception as e:
    print('ERROR', e)
" 2>&1
  fi
}

while true; do
  TS=$(date -u +%Y%m%d_%H%M%S)
  TS_H=$(date -u "+%Y-%m-%d %H:%M:%S UTC")
  CYCLE="$LOG_DIR/ciclo_${TS}.log"
  {
    echo "=== Chequeo $TS_H ==="
    echo
    echo "== jina scrap =="
    SCRAPE=$(scrape_mercado)
    echo "$SCRAPE"
    echo
    echo "== clob probe =="
    CLOB=$(clob_obtener_precios)
    echo "$CLOB"

    CONTAJE=$(echo "$SCRAPE" | grep "^CONTAJE " | awk '{print $2}')
    DIAS=$(echo "$SCRAPE" | grep "^TIEMPO_REST_DIAS " | awk '{print $2}')

    # precios del clob
    P_YES=$(echo "$CLOB" | grep "^P_120-139 " | awk '{print $2}')
    P_NO_160=$(echo "$CLOB" | grep "^P_160-179 " | awk '{print $2}')

    RESTANTE=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_yes']-p['vendido_yes'])")
    NO_CUB=$(python3 -c "import json; p=json.load(open('$POS_FILE')); print(p['shares_no_cubierta'])")
    echo
    echo "Pos: restante=$RESTANTE  no_cub=$NO_CUB  bankroll=\$$BANKROLL  dry_run=$DRY_RUN"

    DECISION="ninguna"

    if [ -n "$P_YES" ] && [ "$P_YES" != "None" ]; then
      if python3 -c "import sys; sys.exit(0 if float('$P_YES') >= 0.30 else 1)" 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE,2))")
        echo "DECISION: vender TODO ($N) YES @ $P_YES (>=0.30)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES @ $P_YES (>=0.30)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_todo_precio"
      elif python3 -c "import sys; sys.exit(0 if float('$P_YES') >= 0.20 else 1)" 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE/2,2))")
        echo "DECISION: vender MITAD ($N) YES @ $P_YES (>=0.20)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES @ $P_YES (>=0.20)';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="vender_mitad_precio"
      elif python3 -c "import sys; sys.exit(0 if float('$P_YES') >= 0.10 else 1)" 2>/dev/null; then
        N=$(python3 -c "print(round($RESTANTE/3,2))")
        echo "DECISION: vender TERCIO ($N) YES @ $P_YES (>=0.10)"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['vendido_yes']+=$N;p['ultima_accion']='venta $N YES @ $P_YES (>=0.10)';json.dump(p,open('$POS_FILE','w'),indent=2)"
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

    if [ -n "$P_NO_160" ] && python3 -c "import sys; sys.exit(0 if float('$NO_CUB')==0 else 1)" 2>/dev/null; then
      if python3 -c "import sys; sys.exit(0 if float('$P_NO_160') <= 0.10 else 1)" 2>/dev/null; then
        USD=$(python3 -c "print(round($BANKROLL*0.33,2))")
        echo "DECISION: comprar \$$USD NO 160-179 @ $P_NO_160"
        python3 -c "import json;p=json.load(open('$POS_FILE'));p['shares_no_cubierta']+=$USD/float('$P_NO_160');p['ultima_accion']='compra \$$USD NO 160-179';json.dump(p,open('$POS_FILE','w'),indent=2)"
        DECISION="cubrir_no"
      fi
    fi

    echo
    echo "Decision final: $DECISION"
    echo "Posicion:"
    cat "$POS_FILE"
  } > "$CYCLE" 2>&1

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
