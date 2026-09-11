#!/bin/bash
# Actualizador v12.8.2 — 🔒 el CIERRE de un combo vuelve a ser posible (cada leg
# se valora con su token REAL del CLOB, no con el position_id del catálogo, que
# daba 404 siempre) + anti-429 en /reclamar. Incluye todo lo de v12.6→v12.8.1.
# Incluye TODO lo de v12.6/v12.7 (resultados reales + auto-curación): es el
# mismo fichero del bot, parcheado encima.
set -e
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_v1282_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

HASH="e3af3dfc"
MD5_ESPERADO="829d3b335d993a205ef7453f0bec0eb8"
INSTALL_DIR="/opt/polymarket"
ESTADO="$INSTALL_DIR/combos_estado.json"

echo "=== ACTUALIZADOR v12.8.2 (🔒 cierre de combos + precios reales) - $(date) ==="
echo "HASH: $HASH · md5 esperado: $MD5_ESPERADO"

echo ""
echo "=== Paso 0: Copia de seguridad del estado ANTES de tocar nada ==="
if [ -f "$ESTADO" ]; then
  cp -a "$ESTADO" "$INSTALL_DIR/combos_estado.pre_v1282_${TS}.json"
  echo "OK: $INSTALL_DIR/combos_estado.pre_v1282_${TS}.json ($(wc -c < "$ESTADO") bytes)"
  python3 - "$ESTADO" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
ab=d.get("trades_copiados",[]) or []
hi=d.get("historial",[]) or []
print(f"   ANTES: {len(ab)} abiertas · {len(hi)} archivadas · "
      f"PnL archivadas ${sum(float(o.get('pnl') or 0) for o in hi):+.2f}")
print(f"   archivadas: ✅{sum(1 for o in hi if o.get('resultado')=='ganada')} "
      f"❌{sum(1 for o in hi if o.get('resultado')=='perdida')} "
      f"🔒manuales {sum(1 for o in hi if o.get('cerrada_manual'))}")
print(f"   ganadas SIN cobro real registrado: "
      f"{sum(1 for o in hi if o.get('resultado')=='ganada' and not o.get('cobro_real'))}")
PY
else
  echo "AVISO: no existe $ESTADO"
fi

echo ""
echo "=== Paso 1: Descargar v12.8.2 a un .new y VALIDAR (el bot sigue corriendo) ==="
mkdir -p "$INSTALL_DIR"
URL="https://raw.githubusercontent.com/lamegawi/bots-backup/${HASH}/scripts_despliegue/poly_combos_bot.py"
echo "URL: $URL"
curl -sL --max-time 60 -o "$INSTALL_DIR/poly_combos_bot.py.new" "$URL"
SIZE=$(wc -c < "$INSTALL_DIR/poly_combos_bot.py.new" 2>/dev/null || echo 0)
echo "Descargado: $SIZE bytes"
if [ "$SIZE" -lt 100000 ]; then
  echo "ERROR: tamano muy pequeno, no se descargo bien (el commit no esta en GitHub?)"
  head -5 "$INSTALL_DIR/poly_combos_bot.py.new"
  rm -f "$INSTALL_DIR/poly_combos_bot.py.new"
  echo ">>> NO se ha tocado el bot en marcha: sigue la version anterior."
  exit 1
fi
MD5=$(md5sum "$INSTALL_DIR/poly_combos_bot.py.new" | cut -d' ' -f1)
echo "md5 descargado: $MD5"
if [ "$MD5" == "$MD5_ESPERADO" ]; then
  echo "   OK md5 identico al del repo"
else
  echo "   AVISO: md5 distinto del esperado ($MD5_ESPERADO) - revisar que HASH es el bueno"
fi
if ! python3 -c "import py_compile; py_compile.compile('$INSTALL_DIR/poly_combos_bot.py.new', doraise=True)"; then
  echo "ERROR: el fichero descargado no compila. NO se toca el bot en marcha."
  rm -f "$INSTALL_DIR/poly_combos_bot.py.new"
  exit 1
fi
echo "   OK compila"

echo ""
echo "=== Paso 2: Copia del fichero actual + parada del bot ==="
[ -f "$INSTALL_DIR/poly_combos_bot.py" ] && cp -a "$INSTALL_DIR/poly_combos_bot.py" "$INSTALL_DIR/poly_combos_bot.pre_v1282_${TS}.py" && echo "backup del binario: poly_combos_bot.pre_v1282_${TS}.py"
systemctl stop poly-combos-bot 2>/dev/null || true
pkill -9 -f poly_combos_bot.py 2>/dev/null || true
sleep 2
mv "$INSTALL_DIR/poly_combos_bot.py.new" "$INSTALL_DIR/poly_combos_bot.py"
echo "instalado: $(wc -c < "$INSTALL_DIR/poly_combos_bot.py") bytes"

echo ""
echo "=== Paso 3: Verificar funciones v12.8.2 (+ v12.8.1 / v12.8 / v12.7 / v12.6) ==="
grep -m 1 "POLY COMBOS BOT" "$INSTALL_DIR/poly_combos_bot.py" | head -1
for fn in "def token_clob_de_leg" "def vivo_de" "ya_resuelta" "sin_valor" \
          "token_clob_de_leg(lg) or lg.get" "time.sleep(0.15)" "MOT = {" \
          "def saldo_token_op" "def _norm_titulo" "def _op_ts" "CTF_ERC1155" \
          "COBROS_PAGINAS" "type=REDEEM" "COBRO_TITULO_VENTANA_D" \
          "def cmd_reclamar" "def pendientes_reclamar" "def preflight_redeem" \
          "def calldata_redeem" "def reclamar_check" "def _rpc_eth_call_ex" \
          "def _texto_reclamar" "def _enlace_evento" "PARLAY_REDEEM_ADAPTER" \
          "OPERADOR_REDEEM_4337" "RECLAMO_PREFLIGHT_H" \
          "def reauditar_estado" "def programar_auditoria_inicial" "def cmd_reauditar" \
          "def verdad_real" "def estado_leg" "def cobros_wallet" "def saldo_combo_token" \
          "PARLAY_ERC1155" "AUDITORIA_CADA_H" "NEXT_AUDITORIA_TS"; do
  if grep -q "$fn" "$INSTALL_DIR/poly_combos_bot.py"; then echo "   OK    $fn"; else echo "   FALTA $fn"; fi
done
echo "   --- dispatch de /reclamar y del boton ---"
grep -n "reclamar" "$INSTALL_DIR/poly_combos_bot.py" | grep -E "startswith|💰 Reclamar\"|reclamar_check\(\)" | head -5 || true
echo "   --- RPC (fuera polygon-rpc.com, que da 401) ---"
grep -n -A2 "^RPCS_POLYGON" "$INSTALL_DIR/poly_combos_bot.py" | head -4


echo ""
echo "=== Paso 4: Reiniciar bot ==="
systemctl start poly-combos-bot
sleep 8
systemctl status poly-combos-bot --no-pager | head -10

echo ""
echo "=== Paso 5: Log (1ª auto-curación ~25s tras arrancar; 💰 si hay algo sin cobrar) ==="
sleep 35
tail -35 /var/log/poly-combos-bot.log 2>&1
echo ""
echo "   --- lineas de auditoria / reclamos / RPC ---"
grep -a "auditoria\|auto-curación\|verdad:\|💰\|reclamar\|pre-flight\|CIERRE" /var/log/poly-combos-bot.log 2>/dev/null | tail -10 || echo "   (aún ninguna)"

echo ""
echo "=== Paso 6: Estado tras el arranque ==="
python3 - "$ESTADO" <<'PY'
import json,sys,os
p=sys.argv[1]
if not os.path.exists(p): print("   sin estado"); raise SystemExit
d=json.load(open(p))
hi=d.get("historial",[]) or []; ab=d.get("trades_copiados",[]) or []
print(f"   AHORA: {len(ab)} abiertas · {len(hi)} archivadas · "
      f"PnL archivadas ${sum(float(o.get('pnl') or 0) for o in hi):+.2f}")
print(f"   archivadas: ✅{sum(1 for o in hi if o.get('resultado')=='ganada')} "
      f"❌{sum(1 for o in hi if o.get('resultado')=='perdida')} "
      f"🔒{sum(1 for o in hi if o.get('cerrada_manual'))}")
r=d.get("ultimo_auditoria_resumen") or {}
print(f"   ultima auditoria: {str(d.get('ultima_auditoria'))[:19]} · origen={r.get('origen')} "
      f"reabiertas={r.get('reabiertas')} corregidas={r.get('corregidas')} "
      f"nuevas={r.get('nuevas_cerradas')} · PnL {r.get('pnl_antes')}→{r.get('pnl_despues')}")
rc=d.get("reclamos_avisados") or {}
if rc:
    print(f"   💰 reclamos avisados: {len(rc)} · "
          f"${sum(float(v.get('importe') or 0) for v in rc.values()):.2f}")
    for k,v in list(rc.items())[:8]:
        print(f"      {str(v.get('titulo') or v.get('nota') or k)[:52]:54} ${float(v.get('importe') or 0):7.2f} · {str(v.get('ts'))[:16]}")
else:
    print("   💰 reclamos avisados: ninguno todavía (envía /reclamar en Telegram)")
PY

echo ""
echo "=== Paso 6b: Comprobacion EN VIVO del precio de las legs (el bug de v12.8.1) ==="
python3 - "$ESTADO" <<'PYEOF' || echo "   (comprobacion no disponible: sin red o sin estado)"
import json, sys, os, urllib.request
p = sys.argv[1]
if not os.path.exists(p):
    print("   sin estado"); raise SystemExit(0)
d = json.load(open(p))
UA = {"User-Agent": "poly-combos-bot"}
def http(u):
    try:
        q = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(q, timeout=12) as r:
            return r.getcode(), json.loads(r.read().decode())
    except Exception as e:
        return (getattr(e, "code", None) or 0), None
NUESTRO = {"yes", "over", "true", "si"}          # misma regla que estado_leg()
ab = d.get("trades_copiados", []) or []
con = [o for o in ab if o.get("legs")][:3]
print(f"   abiertas: {len(ab)} · combos con legs: {sum(1 for o in ab if o.get('legs'))} (se miran {len(con)})")
for o in con:
    print(f"\n   🎫 {str(o.get('question','?'))[:66]}")
    prod = 1.0
    for lg in (o.get("legs") or [])[:3]:
        pid = str(lg.get("position_id") or "")
        cid = str(lg.get("condition_id") or "")
        nuestro = str(lg.get("outcome") or "").strip().lower()
        c1, _ = http(f"https://clob.polymarket.com/midpoint?token_id={pid}")   # ← el bug: 404
        tok, mid, win, iwin, c3 = None, None, None, None, 0
        if cid.startswith("0x"):
            c2, m = http(f"https://clob.polymarket.com/markets/{cid}")
            toks = (m or {}).get("tokens") or []
            if toks:
                idx = 0
                if nuestro:
                    for i, t in enumerate(toks):
                        if str(t.get("outcome") or "").strip().lower() == nuestro:
                            idx = i; break
                tok = str(toks[idx].get("token_id") or "")
                for i, t in enumerate(toks):
                    if t.get("winner"):
                        win = str(t.get("outcome") or "").strip(); iwin = i
        if tok:
            c3, mp = http(f"https://clob.polymarket.com/midpoint?token_id={tok}")
            if c3 == 200:
                try:
                    v = float((mp or {}).get("mid"))
                    mid = v if 0 < v < 1 else None
                except Exception:
                    mid = None
        if mid is not None:
            txt = f"mid {mid:.3f}"
        elif win:
            gano = (nuestro == win.lower()) if nuestro else (iwin == 0 or win.lower() in NUESTRO)
            mid = 1.0 if gano else 0.0
            txt = f"leg decidida → {'GANADA' if gano else 'PERDIDA'} (ganó '{win}')"
        else:
            txt = "sin mid y sin ganador declarado (resolución pendiente)"
        print(f"      {str(lg.get('question','?'))[:38]:40} pid→{c1} · token real→{c3} · {txt}")
        prod = None if (prod is None or mid is None) else prod * mid
    sh = float(o.get("size_shares") or 0); st = float(o.get("stake_dolares") or 0)
    if prod is None:
        print("      ⇒ precio vivo: n/d (alguna leg sin cotización ni veredicto)")
    else:
        print(f"      ⇒ precio vivo {prod:.4f} · valor ≈ ${sh*prod:.2f} (pago ${st:.2f})")
print("\n   ANTES de v12.8.2 el bot sólo miraba 'pid→404' y decía 'sin precio vivo'.")
PYEOF

echo ""
echo "=== EN TELEGRAM ==="
echo "  📂 Abiertas      → AHORA sí muestra '📈 precio ahora' y el valor de los combos"
echo "  🧪 /testcerrar 1 → cotización de venta SIN vender ($0) — ya no dice 'sin precio vivo'"
echo "  🔒 /cerrar 1     → venta real; si la posición ya está resuelta lo dice en cristiano"
echo "  /reclamar        → ganadas SIN cobrar (confirmado on-chain, sin falsas alarmas)"
echo "  /status          → 🩺 auto-curación + 💰 sin cobrar"
echo "  /reauditar seco  → detalle de la re-auditoría sin modificar nada"

# Publicar en diag-public
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/combos_update_v1282_${TS}.log"
  B64=$(base64 -w0 "$RESULT_FILE")
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v1282 ${TS}','content':sys.argv[1],'branch':'diag-public','sha':sys.argv[2]}))" "$B64" "$SHA")
  else
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v1282 ${TS}','content':sys.argv[1],'branch':'diag-public'}))" "$B64")
  fi
  curl -sL --max-time 40 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
else
  echo "AVISO: sin diag_token.txt, no se publica el log"
fi
