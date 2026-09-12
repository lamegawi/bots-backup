#!/bin/bash
# publicar_log_bot.sh — publica el log del bot de COMBOS + estado del servicio en
# la rama diag-public, para poder revisarlo sin SSH (mismo mecanismo que los
# actualizadores). No modifica NADA del bot ni del estado: sólo lee.
#
# Uso:   bash publicar_log_bot.sh [nº_de_líneas]      (por defecto 300)
# Salida: diag_hetzner/bot_log_<TS>.log en lamegawi/bots-backup (rama diag-public)
set -e
N="${1:-300}"
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/bot_log_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

REPO="lamegawi/bots-backup"
RUTA="diag_hetzner/bot_log_${TS}.log"
INSTALL_DIR="/opt/polymarket"
ESTADO="$INSTALL_DIR/combos_estado.json"

echo "=== BOT DE COMBOS · volcado de diagnóstico - $(date) ==="
echo ""
echo "--- servicio ---"
systemctl status poly-combos-bot --no-pager 2>&1 | head -8 || true
echo ""
echo "--- reinicios (historial real, no sólo el arranque actual) ---"
systemctl show poly-combos-bot -p NRestarts -p Result -p ExecMainPID \
        -p ExecMainStartTimestamp -p ActiveEnterTimestamp --no-pager 2>/dev/null || true
echo "   arranques/paradas que vio systemd (últimas 12 h):"
journalctl -u poly-combos-bot --since "12 hours ago" --no-pager 2>/dev/null \
  | grep -aiE "Started|Stopped|Stopping|Starting|Killing|Failed|oom|Main process exited|Scheduled restart|Consumed" \
  | tail -20 || echo "   (journalctl no disponible o sin líneas)"
echo "   arranques del bot según SU propio log (cada uno = un proceso nuevo):"
grep -a "cargado · modo=" /var/log/poly-combos-bot.log 2>/dev/null | tail -14 || true
echo "   reinicios por systemd (si el bot se cayera solo, se vería aquí):"
grep -ac "cargado · modo=" /var/log/poly-combos-bot.log 2>/dev/null || true
echo ""
echo "--- versión instalada ---"
grep -m1 "POLY COMBOS BOT" "$INSTALL_DIR/poly_combos_bot.py" 2>/dev/null || echo "   (sin fichero)"
md5sum "$INSTALL_DIR/poly_combos_bot.py" 2>/dev/null || true
echo ""
echo "--- estado (resumen) ---"
python3 - "$ESTADO" <<'PY' || true
import json, os, sys
p = sys.argv[1]
if not os.path.exists(p):
    print("   sin estado"); raise SystemExit(0)
d = json.load(open(p))
hi = d.get("historial", []) or []
ab = d.get("trades_copiados", []) or []
print(f"   {len(ab)} abiertas · {len(hi)} archivadas · "
      f"PnL archivadas ${sum(float(o.get('pnl') or 0) for o in hi):+.2f}")
print(f"   archivadas: ✅{sum(1 for o in hi if o.get('resultado')=='ganada')} "
      f"❌{sum(1 for o in hi if o.get('resultado')=='perdida')} "
      f"🔒manuales {sum(1 for o in hi if o.get('cerrada_manual'))}")
r = d.get("ultimo_auditoria_resumen") or {}
print(f"   última auditoría: {str(d.get('ultima_auditoria'))[:19]} · origen={r.get('origen')} "
      f"reabiertas={r.get('reabiertas')} corregidas={r.get('corregidas')} "
      f"confirmadas={r.get('confirmadas')} nuevas={r.get('nuevas_cerradas')} · "
      f"PnL {r.get('pnl_antes')}→{r.get('pnl_despues')}")
rc = d.get("reclamos_avisados") or {}
print(f"   💰 reclamos avisados: {len(rc)} · "
      f"${sum(float(v.get('importe') or 0) for v in rc.values() if isinstance(v, dict)):.2f}")
for k, v in list(rc.items())[:10]:
    if isinstance(v, dict):
        print(f"      {str(v.get('titulo') or v.get('nota') or k)[:52]:54} "
              f"${float(v.get('importe') or 0):7.2f} · {str(v.get('ts'))[:16]}")
print(f"   config: max_ops_día={d.get('max_ops_dia')} · prob_min_auto={d.get('prob_min_auto')} "
      f"· intervalo={d.get('intervalo_min') or int(d.get('intervalo_auto_s', 600)) // 60} min · "
      f"modo={d.get('modo') or d.get('modo_auto') or '?'} · "
      f"próxima pasada={str(d.get('proximo_paso_ts'))[:19]}")
# 📡 v12.9.0: estado del copy-trading EN PAPEL (sólo lectura, como todo este script)
cp = d.get("copy") or {}
se = d.get("copy_señales") or []
res = [x for x in se if x.get("resuelta") and not x.get("anulada")]
anu = [x for x in se if x.get("anulada")]
pnl = sum(float(x.get("pnl_papel_nuestro") or 0) for x in res)
tr = cp.get("traders") or []
print(f"   📡 copy en papel: {len(tr)} traders · {len(se)} señales ({len(res)} resueltas, "
      f"{len(anu)} anuladas) · dedup {len(cp.get('vistos') or {})} fills · "
      f"{int(cp.get('informes') or 0)} informes · gasto $0 (COPY_DINERO=False)")
for t in tr[:6]:
    print(f"      · {str(t.get('nombre'))[:22]:<22} #{t.get('puesto')} · "
          f"{t.get('compras48h')} compras/48h · {t.get('mercados')} mercados · "
          f"{t.get('deporte_pct')}% deporte")
for x in se[-8:]:
    estado_x = ("resuelta " + str(x.get("senal_acerto"))) if x.get("resuelta") else "ABIERTA"
    print(f"      {str(x.get('titulo'))[:44]:<44} {x.get('dia')} · él {x.get('precio_trader')} → "
          f"nosotros {x.get('precio_nuestro')} ({x.get('deriva_pts')} pts) · {estado_x} · "
          f"{x.get('escaladas')} escaladas · ${x.get('usd_trader')}")
if res:
    print(f"      acierto {sum(1 for x in res if x.get('senal_acerto')) / len(res) * 100:.1f}% · "
          f"PnL teórico al precio nuestro ${pnl:+.2f} "
          f"(ROI {pnl / (len(res) * 5.0) * 100:+.1f}%)")
ops = [o for o in hi if o.get('tags') and 'inyectada-agosto' in o.get('tags')]
if ops:
    print(f"   💉 inyectadas de agosto: {len(ops)} · "
          f"${sum(float(o.get('size_shares') or 0) for o in ops):.2f} por cobrar")
PY
echo ""
echo "--- últimas $N líneas de /var/log/poly-combos-bot.log ---"
tail -n "$N" /var/log/poly-combos-bot.log 2>&1 || echo "   (sin log)"
echo ""
echo "--- errores recientes (tracebacks / telegram / RPC) ---"
grep -a -n "Traceback\|telegram_api error\|Too Many Requests\|ERROR\|❌" /var/log/poly-combos-bot.log 2>/dev/null | tail -15 || echo "   (ninguno)"

# ---- publicación en diag-public ----
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -z "$PAT" ]; then
  echo ""
  echo "AVISO: sin diag_token.txt no se publica. El volcado queda en $RESULT_FILE"
  exit 0
fi
B64=$(base64 -w0 "$RESULT_FILE")
SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/${REPO}/contents/${RUTA}?ref=diag-public" \
      -H "Authorization: token ${PAT}" 2>/dev/null \
      | python3 -c "import json,sys
try:
    print(json.load(sys.stdin).get('sha') or '')
except Exception:
    print('')" 2>/dev/null || true)
if [ -n "$SHA" ]; then
  PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'bot log ${TS}','content':sys.argv[1],'branch':'diag-public','sha':sys.argv[2]}))" "$B64" "$SHA")
else
  PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'bot log ${TS}','content':sys.argv[1],'branch':'diag-public'}))" "$B64")
fi
curl -sL --max-time 60 -X PUT "https://api.github.com/repos/${REPO}/contents/${RUTA}" \
  -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" \
  | python3 -c "import json,sys
try:
    d=json.load(sys.stdin)
    print('Publicado en', (d.get('content') or {}).get('path') or d.get('message'))
except Exception as e:
    print('respuesta de GitHub no parseable:', e)"
echo ">>> Dime 'Hecho' y lo leo."
