#!/bin/bash
# Diagnóstico v12.7 — vuelca combos_estado.json (ops archivadas + abiertas con sus legs)
# y lo publica en diag-public para contrastarlo desde fuera con la realidad on-chain.
# NO modifica nada: sólo lee.
set -e
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/diag_estado_v127_${TS}.json"
INSTALL_DIR="/opt/polymarket"
ESTADO="$INSTALL_DIR/combos_estado.json"

echo "=== DIAGNOSTICO ESTADO v12.7 - $(date) ==="
if [ ! -f "$ESTADO" ]; then echo "ERROR: no existe $ESTADO"; exit 1; fi
echo "Estado: $(wc -c < "$ESTADO") bytes"

python3 - "$ESTADO" "$RESULT_FILE" <<'PY'
import json, sys, datetime
estado = json.load(open(sys.argv[1]))
ab = estado.get("trades_copiados", []) or []
hi = estado.get("historial", []) or []

def recorte(o, con_legs=False):
    r = {
        "fecha": o.get("copiado_en") or o.get("cerrado_en"),
        "question": str(o.get("question", ""))[:200],
        "n_legs": o.get("n_legs"),
        "stake": o.get("stake_dolares"),
        "shares": o.get("size_shares"),
        "status": o.get("status"),
        "resultado": o.get("resultado"),
        "pnl": o.get("pnl"),
        "franja": o.get("franja"),
        "cerrada_manual": bool(o.get("cerrada_manual")),
        "motivo_cierre": o.get("motivo_cierre"),
        "cerrado_en": o.get("cerrado_en"),
        "fin_real": o.get("fin_real"),
        "fin_previsto": o.get("fin_previsto"),
        "token_combo": str(o.get("combo_yes_position_id") or o.get("real_token") or ""),
        "tx": str(o.get("tx_hash") or "")[:20],
        "fuente_verdad": o.get("fuente_verdad"),
        "cobro_real": o.get("cobro_real"),
        "resultado_antes": o.get("resultado_antes"),
        "pnl_antes": o.get("pnl_antes"),
    }
    if con_legs:
        r["legs"] = [{"q": str(l.get("question", ""))[:90],
                      "cid": l.get("condition_id"),
                      "pid": str(l.get("position_id") or "")[:24],
                      "outcome": l.get("outcome"),
                      "yes_price": l.get("yes_price")} for l in (o.get("legs") or [])]
    return {k: v for k, v in r.items() if v not in (None, "", [])}

salida = {
    "generado": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "version_bot": "v12.7-diag",
    "resumen": {
        "abiertas": len(ab),
        "archivadas": len(hi),
        "archivadas_ganadas": sum(1 for o in hi if o.get("resultado") == "ganada"),
        "archivadas_perdidas": sum(1 for o in hi if o.get("resultado") == "perdida"),
        "archivadas_manuales": sum(1 for o in hi if o.get("cerrada_manual")),
        "pnl_archivadas": round(sum(float(o.get("pnl") or 0) for o in hi), 2),
        "stake_abiertas": round(sum(float(o.get("stake_dolares") or 0) for o in ab), 2),
        "con_resultado_antes": sum(1 for o in hi if o.get("resultado_antes") is not None),
    },
    "config": {k: estado.get(k) for k in ("modo", "stake_mode", "stake", "max_ops_dia",
                                          "prob_min_auto", "intervalo_auto_s") if k in estado},
    "archivadas": [recorte(o) for o in hi],
    "abiertas": [recorte(o, con_legs=True) for o in ab],
}
json.dump(salida, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
r = salida["resumen"]
print(f"   abiertas {r['abiertas']} · archivadas {r['archivadas']} "
      f"(✅{r['archivadas_ganadas']} ❌{r['archivadas_perdidas']} 🔒{r['archivadas_manuales']}) "
      f"· PnL archivadas ${r['pnl_archivadas']:+.2f}")
print(f"   stake en abiertas ${r['stake_abiertas']:.2f} · re-auditadas antes: {r['con_resultado_antes']}")
print("   --- últimas 15 archivadas ---")
for o in salida["archivadas"][-15:]:
    print(f"     {str(o.get('cerrado_en') or o.get('fecha'))[:16]} {o.get('resultado','?'):8} "
          f"${float(o.get('pnl') or 0):+7.2f} · {str(o.get('question'))[:58]}")
PY

echo ""
echo "JSON generado: $RESULT_FILE ($(wc -c < "$RESULT_FILE") bytes)"

# Publicar en diag-public
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/estado_combos_v127_${TS}.json"
  B64=$(base64 -w0 "$RESULT_FILE")
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'estado v126 ${TS}','content':sys.argv[1],'branch':'diag-public','sha':sys.argv[2]}))" "$B64" "$SHA")
  else
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'estado v126 ${TS}','content':sys.argv[1],'branch':'diag-public'}))" "$B64")
  fi
  curl -sL --max-time 40 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
else
  echo "AVISO: sin diag_token.txt, no se publica"
fi
