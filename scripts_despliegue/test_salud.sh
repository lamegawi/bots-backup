#!/bin/bash
# ============================================================
# TEST DE SALUD — poly-combos-bot (Hetzner)
# Comprueba servicio, versión/integridad del código, estado,
# proxy Tailscale, APIs públicas, wallet, disco y errores.
# Publica el informe en GitHub (rama diag-public) para leerlo
# sin SSH. USO:  bash test_salud.sh
# ============================================================
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/salud_combos_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

BOT="/opt/polymarket/poly_combos_bot.py"
ESTADO="/opt/polymarket/combos_estado.json"
LOG="/var/log/poly-combos-bot.log"
SERVICE="poly-combos-bot"
WALLET="0xb0e1197098e6d427c01720f1631cad24ce740fa0"
PROXY="http://100.83.57.99:8888"
IP_ESPERADA="85.85.41.76"
FALLOS=0
falla() { echo "  ❌ $1"; FALLOS=$((FALLOS+1)); }
ok()    { echo "  ✅ $1"; }
info()  { echo "  ·  $1"; }

echo "=== TEST DE SALUD poly-combos-bot — $(date -u '+%Y-%m-%d %H:%M:%S') UTC ==="

echo ""
echo "== 1) SERVICIO =="
if systemctl is-active --quiet "$SERVICE"; then
  ok "servicio active"
  systemctl status "$SERVICE" --no-pager 2>&1 | grep -E "Active:|Main PID:|Memory:" | sed 's/^/     /'
else
  falla "servicio NO activo: $(systemctl is-active "$SERVICE" 2>&1)"
  systemctl status "$SERVICE" --no-pager 2>&1 | head -12 | sed 's/^/     /'
fi
pgrep -af "poly_combos_bot.py" | head -3 | sed 's/^/     proc: /'

echo ""
echo "== 2) CÓDIGO (versión e integridad) =="
if [ -f "$BOT" ]; then
  TAM=$(wc -c < "$BOT")
  info "tamaño: $TAM bytes"
  info "md5:    $(md5sum "$BOT" | cut -d' ' -f1)"
  info "banner: $(grep -m1 'POLY COMBOS BOT' "$BOT")"
  if [ "$TAM" -lt 30000 ]; then falla "archivo demasiado pequeño (descarga fallida / 404)"; else ok "tamaño plausible"; fi
  if python3 -m py_compile "$BOT" 2>/dev/null; then ok "sintaxis OK (py_compile)"; else falla "SINTAXIS ROTA"; fi
  info "v12.4 (PIN fijo):   $(grep -c 'PIN_FIJO_OPS' "$BOT") menciones"
  info "v12.3 (prob/cierre): $(grep -c 'v12\.3' "$BOT") menciones"
else
  falla "no existe $BOT"
fi

echo ""
echo "== 3) ESTADO (combos_estado.json) =="
if [ -f "$ESTADO" ]; then
  info "tamaño: $(wc -c < "$ESTADO") bytes · modificado: $(date -u -r "$ESTADO" '+%H:%M:%S UTC')"
  python3 - "$ESTADO" <<'PY'
import json,sys
from datetime import datetime,timezone
try:
    e=json.load(open(sys.argv[1]))
except Exception as ex:
    print("  ❌ JSON ilegible:",ex); sys.exit()
hoy=datetime.now(timezone.utc).date().isoformat()
rf=e.get("combos_rfq",{}) or {}
hist=rf.get("historial",[]) or []
ops=e.get("trades_copiados",[]) or []
pagadas=[r for r in hist if str(r.get("fecha","")).startswith(hoy) and r.get("status") in ("filled","pendiente")]
print(f"  ·  max_ops_dia={e.get('max_ops_dia')} · prob_min_auto={e.get('prob_min_auto')} · stake_mode={e.get('stake_mode')} · stake={e.get('stake')}")
print(f"  ·  intervalo={e.get('intervalo_min')} min · modo={e.get('modo')} · chat_id={'sí' if e.get('chat_id') else 'NO'}")
print(f"  ·  historial RFQ: {len(hist)} registros · fills hoy: {len(pagadas)}")
print(f"  ·  trades_copiados (panel): {len(ops)} · huellas dedup: {len(rf.get('huellas',{}) or {})}")
nx=e.get("proximo_paso_ts") or 0
try:
    nx=float(nx)
    if nx>0:
        d=(nx-datetime.now(timezone.utc).timestamp())/60
        print(f"  ·  próxima pasada AUTO en {d:.1f} min")
except Exception: pass
PY
  [ -f "${ESTADO%.json}.bak.json" ] && info "backup de estado: $(wc -c < /opt/polymarket/combos_estado.bak.json) bytes"
else
  falla "no existe $ESTADO"
fi

echo ""
echo "== 4) PROXY TAILSCALE (obligatorio para operar) =="
IP=$(curl -s --max-time 15 -x "$PROXY" https://api.ipify.org 2>/dev/null || echo "")
if [ -z "$IP" ]; then
  falla "sin respuesta a través del proxy $PROXY (¿PC apagado o Tailscale caído?)"
elif [ "$IP" = "$IP_ESPERADA" ]; then
  ok "IP de salida correcta: $IP (PC del user)"
else
  falla "IP de salida $IP ≠ esperada $IP_ESPERADA"
fi

echo ""
echo "== 5) APIs PÚBLICAS =="
chk() { # nombre url [json_campo]
  local n="$1" u="$2"
  local c=$(curl -s -o /tmp/_s.json -w "%{http_code}" --max-time 20 "$u" 2>/dev/null)
  local t=$(wc -c < /tmp/_s.json 2>/dev/null || echo 0)
  if [ "$c" = "200" ] && [ "$t" -gt 2 ]; then ok "$n → 200 ($t bytes)"; else falla "$n → HTTP $c ($t bytes)"; fi
}
# midpoint con un token REAL (el primero de las posiciones de la wallet) para que el 200 signifique algo
TOK=$(python3 -c "
import json
try:
    p=json.load(open('/tmp/_pos.json'))
    t=[str(x.get('asset','')) for x in p if str(x.get('asset','')).isdigit()]
    print(t[0] if t else '')
except Exception: print('')
" 2>/dev/null)
if [ -n "$TOK" ]; then
  chk "CLOB midpoint (token real ${TOK:0:10}…)" "https://clob.polymarket.com/midpoint?token_id=${TOK}"
else
  info "CLOB midpoint: sin token real disponible, se omite"
fi
curl -s --max-time 25 "https://data-api.polymarket.com/positions?user=${WALLET}&limit=200" > /tmp/_pos.json 2>/dev/null
chk "Gamma markets"     "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=1"
chk "Catálogo combos"   "https://combos-rfq-api.polymarket.com/v1/rfq/combo-markets?limit=1"
chk "Data-API trades"   "https://data-api.polymarket.com/trades?user=${WALLET}&limit=1"
chk "Data-API positions" "https://data-api.polymarket.com/positions?user=${WALLET}&limit=1"
# El gateway RFQ exige cabeceras L2: sin ellas debe responder 401/403/405 = está vivo
C=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 "https://combos-rfq-gateway-requester-api.polymarket.com/v1/requester/rfq/requests" 2>/dev/null)
case "$C" in 200|400|401|403|404|405|422) ok "Gateway RFQ alcanzable (HTTP $C sin credenciales L2, es lo esperado)";; *) falla "Gateway RFQ → HTTP $C";; esac
# A través del proxy (así opera el bot de verdad)
C2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 -x "$PROXY" "https://clob.polymarket.com/midpoint?token_id=1" 2>/dev/null)
if [ "$C2" = "200" ]; then ok "CLOB a través del proxy → 200"; else falla "CLOB a través del proxy → HTTP $C2"; fi

echo ""
echo "== 6) WALLET (posición y actividad) =="
echo "  ·  OJO: en data-api 'size' son SHARES; el coste en $ = size x price"
python3 - <<'PY'
import json,time
try:
    p=json.load(open("/tmp/_pos.json"))
except Exception:
    print("  ·  sin datos de posiciones"); raise SystemExit
if not isinstance(p,list): print("  ·  respuesta inesperada"); raise SystemExit
act=[x for x in p if float(x.get("size",0) or 0)>0.01]
val=sum(float(x.get("currentValue",0) or 0) for x in act)
print(f"  ·  posiciones con tamaño: {len(act)} · valor actual ≈ ${val:.2f}")
for x in sorted(act,key=lambda y:-float(y.get("currentValue",0) or 0))[:5]:
    print(f"     - {str(x.get('title',''))[:58]} | {float(x.get('size',0)):.1f} sh | ${float(x.get('currentValue',0) or 0):.2f}")
PY
curl -s --max-time 25 "https://data-api.polymarket.com/trades?user=${WALLET}&limit=5" > /tmp/_tr.json 2>/dev/null
python3 - <<'PY'
import json,time
try: t=json.load(open("/tmp/_tr.json"))
except Exception: print("  ·  sin trades"); raise SystemExit
if not isinstance(t,list) or not t: print("  ·  sin trades recientes"); raise SystemExit
ahora=time.time()
print("  ·  últimos fills:")
for x in t[:5]:
    ts=x.get("timestamp") or 0
    sh=float(x.get("size",0) or 0); pr=float(x.get("price",0) or 0)
    print(f"     - hace {(ahora-ts)/60:7.1f} min | {x.get('side','?'):4} | {sh:.2f} sh x {pr:.4f} = ${sh*pr:.2f} | {str(x.get('title',''))[:40]}")
PY

echo ""
echo "== 7) RECURSOS =="
info "disco /: $(df -h / | awk 'NR==2{print $4" libres ("$5" usado)"}')"
USO=$(df -h / | awk 'NR==2{gsub("%","",$5); print $5}')
[ "${USO:-0}" -ge 90 ] && falla "disco al ${USO}%" || ok "disco al ${USO:-?}%"
info "memoria: $(free -m | awk '/Mem:/{printf "%d MB usados de %d MB (%.0f%%)", $3, $2, $3/$2*100}')"
info "log: $(wc -l < "$LOG" 2>/dev/null || echo 0) líneas · $(wc -c < "$LOG" 2>/dev/null || echo 0) bytes"

echo ""
echo "== 8) ERRORES EN EL LOG =="
if [ -f "$LOG" ]; then
  TB=$(grep -c "Traceback" "$LOG" 2>/dev/null); TB=${TB:-0}
  ER=$(tail -400 "$LOG" | grep -icE "error|excepci|fall" 2>/dev/null); ER=${ER:-0}
  info "Tracebacks totales en el log: $TB"
  info "líneas con error en las últimas 400: $ER (el 'read operation timed out' es ruido benigno)"
  tail -400 "$LOG" | grep -iE "traceback|error" | grep -v "read operation timed out" | tail -6 | sed 's/^/     ! /'
  TB_REC=$(tail -200 "$LOG" | grep -c "Traceback" 2>/dev/null); TB_REC=${TB_REC:-0}
  [ "${TB_REC:-0}" -gt 0 ] && falla "$TB_REC traceback(s) en las últimas 200 líneas" || ok "sin tracebacks recientes"
else
  falla "no existe $LOG"
fi

echo ""
echo "== 9) ÚLTIMAS 25 LÍNEAS DEL LOG =="
tail -25 "$LOG" 2>&1 | sed 's/^/   /'

echo ""
echo "=============================================="
if [ "$FALLOS" -eq 0 ]; then echo "RESULTADO: ✅ SALUD OK (0 fallos)"; else echo "RESULTADO: ⚠️ $FALLOS FALLO(S) — revisar arriba"; fi
echo "=============================================="

# ---------- Publicar en diag-public ----------
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/salud_combos_${TS}.log"
  B64=$(base64 -w0 "$RESULT_FILE")
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'salud ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'salud ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en diag-public/$RUTA"
else
  echo "Sin token en /root/diag_token.txt: informe solo local en $RESULT_FILE"
fi
