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
echo "=== Paso 3b: Inyectar las 4 combos GANADAS de agosto SIN cobrar ($82.97) ==="
python3 - "$ESTADO" <<'PYEOF' || echo "   (inyeccion fallida: el bot arranca igual, sin esas 4 ops)"
import json, os, sys, tempfile
p = sys.argv[1]
OPS = json.loads(r'''[
 {
  "tipo": "combo_rfq",
  "copiado_en": "2026-08-03T19:20:06+00:00",
  "question": "Dota 2: Team Liquid vs Vici Gaming (BO3) - 1win Essence Playoffs + Dota 2: Rune Eaters vs LGD Gaming (BO3) - Games of the Future Playoffs",
  "n_legs": 2,
  "legs": [
   {
    "question": "Dota 2: Team Liquid vs Vici Gaming (BO3) - 1win Essence Playoffs",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x4a9befb06bc73f1227bbe2c3ad2ae71d4cc5a5f1770d43bcfd7194d3985be115",
    "outcome": "Team Liquid"
   },
   {
    "question": "Dota 2: Rune Eaters vs LGD Gaming (BO3) - Games of the Future Playoffs",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x2338f99dacc9238d9a1ee36c9e8e7451f263a51dbb1d8f84222513e91a06969d",
    "outcome": "Rune Eaters"
   }
  ],
  "rfq_id": "",
  "quote_id": "",
  "combo_condition_id": "0x033d7bbf065bdf8ccf1b2bc32295db4dee0000000000000000000000000000",
  "combo_yes_position_id": "1465570281521417484089349842073433359851434826329862370366262471336197619712",
  "precio_ejecutado": 0.779,
  "cuota_ejecutada": 1.2837,
  "cuota_estimada": 1.2837,
  "size_shares": 19.045017,
  "stake_dolares": 15.0,
  "order_id": "",
  "tx_hash": "0x166cd5b6a1755cad1ce610ab6a39cb8af905a507f06d201aeac96642ae5f1454",
  "status": "cerrado",
  "estado_rfq": "FILLED",
  "slug": "",
  "market_id": "",
  "condition_id": "0x033d7bbf065bdf8ccf1b2bc32295db4dee0000000000000000000000000000",
  "real_token": "1465570281521417484089349842073433359851434826329862370366262471336197619712",
  "volumen": 0,
  "tags": [
   "combo-rfq",
   "inyectada-agosto"
  ],
  "franja": "base",
  "extendida": false,
  "super": false,
  "resultado": "ganada",
  "pnl": 4.05,
  "fin_real": "",
  "cerrado_en": "2026-08-03T19:20:06+00:00",
  "fuente_verdad": "legs_ganadas",
  "cerrada_manual": false,
  "motivo_cierre": "resolucion_real",
  "nota": "Inyectada el 11-sep-2026 (v12.8.2): combo GANADO de agosto que Polymarket no autocobró; los tokens siguen en la cartera (saldo on-chain > 0)."
 },
 {
  "tipo": "combo_rfq",
  "copiado_en": "2026-08-03T19:29:35+00:00",
  "question": "Counter-Strike: Imperial vs Procyon Gaming (BO3) - BetBoom Storm Group Stage + Counter-Strike: QUINTESSÊNCIA vs BESTIA Academy (BO3) - Gamers Club Liga Série A Playoffs",
  "n_legs": 2,
  "legs": [
   {
    "question": "Counter-Strike: Imperial vs Procyon Gaming (BO3) - BetBoom Storm Group Stage",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x24a11994a0829cfde4ec8d190d67d3786212423f60331fac7aa03a14ea2ba953",
    "outcome": "Imperial"
   },
   {
    "question": "Counter-Strike: QUINTESSÊNCIA vs BESTIA Academy (BO3) - Gamers Club Liga Série A Playoffs",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0xaa09530d294cf484e2e0840a908e0db8e18714b59a1a300e1fe50980c1d9f24a",
    "outcome": "QUINTESSÊNCIA"
   }
  ],
  "rfq_id": "",
  "quote_id": "",
  "combo_condition_id": "0x0363b325260260a9ea31152e985e6e760b0000000000000000000000000000",
  "combo_yes_position_id": "1533092819279806577548982495808019581896059581058309727707081807910034997248",
  "precio_ejecutado": 0.767674,
  "cuota_ejecutada": 1.3026,
  "cuota_estimada": 1.3026,
  "size_shares": 19.315185,
  "stake_dolares": 15.0,
  "order_id": "",
  "tx_hash": "0x10d6dcaa5a0df4dfc7ed554e6fcbfd52efd42c411d2ff5d1bb580aaa67928893",
  "status": "cerrado",
  "estado_rfq": "FILLED",
  "slug": "",
  "market_id": "",
  "condition_id": "0x0363b325260260a9ea31152e985e6e760b0000000000000000000000000000",
  "real_token": "1533092819279806577548982495808019581896059581058309727707081807910034997248",
  "volumen": 0,
  "tags": [
   "combo-rfq",
   "inyectada-agosto"
  ],
  "franja": "base",
  "extendida": false,
  "super": false,
  "resultado": "ganada",
  "pnl": 4.32,
  "fin_real": "",
  "cerrado_en": "2026-08-03T19:29:35+00:00",
  "fuente_verdad": "legs_ganadas",
  "cerrada_manual": false,
  "motivo_cierre": "resolucion_real",
  "nota": "Inyectada el 11-sep-2026 (v12.8.2): combo GANADO de agosto que Polymarket no autocobró; los tokens siguen en la cartera (saldo on-chain > 0)."
 },
 {
  "tipo": "combo_rfq",
  "copiado_en": "2026-08-04T19:22:06+00:00",
  "question": "LoL: Baam Esports vs 3BL Esports (BO3) - Arabian League Group Stage + LoL: Croatian Flair x RLX  vs Lupus Esports (BO3) - EBL Regular Season",
  "n_legs": 2,
  "legs": [
   {
    "question": "LoL: Baam Esports vs 3BL Esports (BO3) - Arabian League Group Stage",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x121cd07691a328aa5d479afc2468ab52a329a742fac215e35c22086633aa2432",
    "outcome": "Baam Esports"
   },
   {
    "question": "LoL: Croatian Flair x RLX  vs Lupus Esports (BO3) - EBL Regular Season",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x3366af39100675e511b8d663f1b2aa74b058fb9d2135f28e540e4108af2ddf7b",
    "outcome": "Croatian Flair x RLX "
   }
  ],
  "rfq_id": "",
  "quote_id": "",
  "combo_condition_id": "0x03e8fbb9de7fc700d1ac768e1cf437385e0000000000000000000000000000",
  "combo_yes_position_id": "1768584414133455489888940688163027989874358868667303883292282436255504924672",
  "precio_ejecutado": 0.701842,
  "cuota_ejecutada": 1.4248,
  "cuota_estimada": 1.4248,
  "size_shares": 14.038948,
  "stake_dolares": 10.0,
  "order_id": "",
  "tx_hash": "0x0285c158f7624e405e9ff31879276f545d05e52f92c9777e196df3c84540a619",
  "status": "cerrado",
  "estado_rfq": "FILLED",
  "slug": "",
  "market_id": "",
  "condition_id": "0x03e8fbb9de7fc700d1ac768e1cf437385e0000000000000000000000000000",
  "real_token": "1768584414133455489888940688163027989874358868667303883292282436255504924672",
  "volumen": 0,
  "tags": [
   "combo-rfq",
   "inyectada-agosto"
  ],
  "franja": "base",
  "extendida": false,
  "super": false,
  "resultado": "ganada",
  "pnl": 4.04,
  "fin_real": "",
  "cerrado_en": "2026-08-04T19:22:06+00:00",
  "fuente_verdad": "legs_ganadas",
  "cerrada_manual": false,
  "motivo_cierre": "resolucion_real",
  "nota": "Inyectada el 11-sep-2026 (v12.8.2): combo GANADO de agosto que Polymarket no autocobró; los tokens siguen en la cartera (saldo on-chain > 0)."
 },
 {
  "tipo": "combo_rfq",
  "copiado_en": "2026-08-06T13:29:02+00:00",
  "question": "LoL: Dark Passage vs Team Phoenix (BO3) - TCL Play-Ins + LoL: Team WE vs Anyone's Legend (BO3) - LPL Group Ascend + LoL: G2 NORD vs Unicorns Of Love Sexy Edition (BO3) - Prime League 1st Division Group B + LoL: Ici Japon Corp. Esport vs Esp",
  "n_legs": 4,
  "legs": [
   {
    "question": "LoL: Dark Passage vs Team Phoenix (BO3) - TCL Play-Ins",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0xe9da2c806b4717975454ddc446937a785f6dbf2b6360557fa875461efe60578e",
    "outcome": "Dark Passage"
   },
   {
    "question": "LoL: Team WE vs Anyone's Legend (BO3) - LPL Group Ascend",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x24f18bdec315f767612d94e386bc60589185ab6a84e97b080a661a3fce1b2739",
    "outcome": "Team WE"
   },
   {
    "question": "LoL: G2 NORD vs Unicorns Of Love Sexy Edition (BO3) - Prime League 1st Division Group B",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0xffc355c1e352588af427f0e82061d63bba145f0a27efcf12436df32a89f7d220",
    "outcome": "G2 NORD"
   },
   {
    "question": "LoL: Ici Japon Corp. Esport vs Esprit Shōnen (BO1) - LFL Regular Season",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0xefe382db7be026073b08fbbe1e96a0bcd6a246c6ef69f9abc70b927202878f36",
    "outcome": "Ici Japon Corp. Esport"
   }
  ],
  "rfq_id": "",
  "quote_id": "",
  "combo_condition_id": "0x03db6d7b77e598cc1229347bba6c2f56810000000000000000000000000000",
  "combo_yes_position_id": "1744633671988118944301970785967107214763206080678570968048928890271939166208",
  "precio_ejecutado": 0.316261,
  "cuota_ejecutada": 3.1619,
  "cuota_estimada": 3.1619,
  "size_shares": 30.574245,
  "stake_dolares": 10.0,
  "order_id": "",
  "tx_hash": "0x3f05b81a6d44dec15bcdb2604bc7b1977f56e3d97951c7ab8c8502a01ce0b727",
  "status": "cerrado",
  "estado_rfq": "FILLED",
  "slug": "",
  "market_id": "",
  "condition_id": "0x03db6d7b77e598cc1229347bba6c2f56810000000000000000000000000000",
  "real_token": "1744633671988118944301970785967107214763206080678570968048928890271939166208",
  "volumen": 0,
  "tags": [
   "combo-rfq",
   "inyectada-agosto"
  ],
  "franja": "base",
  "extendida": false,
  "super": false,
  "resultado": "ganada",
  "pnl": 20.57,
  "fin_real": "",
  "cerrado_en": "2026-08-06T13:29:02+00:00",
  "fuente_verdad": "legs_ganadas",
  "cerrada_manual": false,
  "motivo_cierre": "resolucion_real",
  "nota": "Inyectada el 11-sep-2026 (v12.8.2): combo GANADO de agosto que Polymarket no autocobró; los tokens siguen en la cartera (saldo on-chain > 0)."
 }
]''')
if not os.path.exists(p):
    print("   sin estado: nada que inyectar"); raise SystemExit(0)
d = json.load(open(p))
hi = d.setdefault("historial", [])
ab = d.setdefault("trades_copiados", [])
toks = {str(o.get("combo_yes_position_id") or o.get("real_token") or "")
        for o in list(hi) + list(ab)}
nuevas = [o for o in OPS if o["combo_yes_position_id"] not in toks]
if not nuevas:
    print(f"   OK: las {len(OPS)} ops de agosto YA estan en el libro (nada que inyectar)")
    raise SystemExit(0)
hi.extend(nuevas)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p) or ".", suffix=".tmp")
with os.fdopen(fd, "w") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
os.replace(tmp, p)
tot = sum(float(o["size_shares"]) for o in nuevas)
st = sum(float(o["stake_dolares"]) for o in nuevas)
print(f"   INYECTADAS {len(nuevas)} ops GANADAS de agosto: pagado ${st:.2f} -> a cobrar ${tot:.2f} (+${tot-st:.2f})")
for o in nuevas:
    print(f"     {o['copiado_en'][:16]} · {o['n_legs']} legs · ${float(o['stake_dolares']):.2f} -> "
          f"${float(o['size_shares']):.2f} · token ...{o['combo_yes_position_id'][-8:]}")
print("   Con sus condition_id reales: la auditoria las CONFIRMA (fuente legs_ganadas)")
print("   y /reclamar las mostrara como ganadas SIN cobrar (saldo on-chain > 0).")
PYEOF

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
