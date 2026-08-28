#!/bin/bash
# FIXG - Paquete anti-fantasmas + indicador BE
ROOT="${ROOT:-/root}"

echo "=== FIXG: paquete anti-fantasmas ==="

for BOTF in "$ROOT/okx_real_bot.py" "$ROOT/okx_demo_bot.py"; do
    NOMBRE=$(basename "$BOTF")
    if [ ! -f "$BOTF" ]; then
        echo "[$NOMBRE] no existe, me lo salto"
        continue
    fi
    cp "$BOTF" "$BOTF.bakG"

    python3 - "$BOTF" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
hechos = []

a1 = '        p = pos_map.get(key)\n        if not p:\n'
if s.count(a1) == 1:
    if 'FIXW_ARENA' not in s:
        s = s.replace(a1, a1 +
            '            # FIXW_ARENA: exigir 2 pasadas consecutivas sin verla (evita borrados por fallo de API)\n'
            '            m["ausente"] = int(m.get("ausente", 0)) + 1\n'
            '            if m["ausente"] < 2:\n'
            '                changed = True\n'
            '                continue\n', 1)
        hechos.append("anti-borrado")
else:
    print("  [aviso] ancla W1 no unica (%d)" % s.count(a1))

a2 = '        qty = p["qty"]; unreal = p["pnl"]\n'
if s.count(a2) == 1:
    if 'm["ausente"] = 0' not in s:
        s = s.replace(a2,
            '        if m.get("ausente"):\n'
            '            m["ausente"] = 0\n'
            '            changed = True\n' + a2, 1)
        hechos.append("reset-contador")
else:
    print("  [aviso] ancla W2 no unica (%d)" % s.count(a2))

a3 = ('        m = managed.get(p["base"] + ": " + d)\n'
      '        if m and m.get("state") == "breakeven":\n'
      '            linea += " | SL en BE"\n'
      '        lineas.append(linea)\n')
if s.count(a3) == 1:
    if 'FIXBE_ARENA' not in s:
        nuevo = ('        m = managed.get(p["base"] + ": " + d)\n'
                 '        if m and m.get("state") == "breakeven":\n'
                 '            linea += " | SL en BE"\n'
                 '        # FIXBE_ARENA: BE real segun el SL vivo del exchange (vale tambien para fantasmas)\n'
                 '        try:\n'
                 '            _g = globals()\n'
                 '            if _g.get("_FIXBE_TS") is None or time.time() - _g["_FIXBE_TS"] > 60:\n'
                 '                _slm = {}\n'
                 '                for _a in client.algo_pendientes() or []:\n'
                 '                    if _a.get("slTriggerPx"):\n'
                 '                        _slm[_a.get("instId", "")] = float(_a["slTriggerPx"])\n'
                 '                _g["_FIXBE_SL"] = _slm\n'
                 '                _g["_FIXBE_TS"] = time.time()\n'
                 '            _slp = (_g.get("_FIXBE_SL") or {}).get(sym)\n'
                 '            if _slp and ((d == "LONG" and _slp >= p["entry"]) or (d == "SHORT" and _slp <= p["entry"])):\n'
                 '                if "BE" not in linea:\n'
                 '                    linea += " | \U0001F512 BE"\n'
                 '        except Exception:\n'
                 '            pass\n'
                 '        lineas.append(linea)\n')
        s = s.replace(a3, nuevo, 1)
        hechos.append("indicador-BE")
else:
    print("  [aviso] ancla BE no encontrada (%d). Lineas con lineas.append:" % s.count(a3))
    for n, l in enumerate(s.split("\n"), 1):
        if "lineas.append(linea)" in l:
            print("    %d: %s" % (n, l.strip()))

open(p, "w", encoding="utf-8").write(s)
print("  parches aplicados:", ", ".join(hechos) if hechos else "NINGUNO")
PYEOF

    if python3 -m py_compile "$BOTF"; then
        echo "[$NOMBRE] OK"
    else
        cp "$BOTF.bakG" "$BOTF"
        echo "[$NOMBRE] ERROR de sintaxis -> restaurado"
    fi
done

F="$ROOT/salud_bots.py"
if grep -q "FIXADOPT_ARENA" "$F"; then
    echo "[salud_bots] adopcion ya parcheada"
else
    cp "$F" "$F.bakG"
    python3 - "$F" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
ancla = ('        side_cierre = "sell" if direccion == "LONG" else "buy"\n'
         '        if direccion == "LONG":\n'
         '            sl_px = ref * (1 - SL_PROTECTOR_PCT)\n'
         '        else:\n'
         '            sl_px = ref * (1 + SL_PROTECTOR_PCT)\n')
if s.count(ancla) != 1:
    print("  [aviso] ancla ADOPT no unica (%d)" % s.count(ancla))
    raise SystemExit(1)
nuevo = ('        side_cierre = "sell" if direccion == "LONG" else "buy"\n'
         '        # FIXADOPT_ARENA: capar el riesgo del adoptado a ~12 USD (antes 4% fijo = ~20 USD)\n'
         '        _pct_sl = SL_PROTECTOR_PCT\n'
         '        try:\n'
         '            _notional = abs(float(p.get("notionalUsd", 0) or 0))\n'
         '            if _notional > 0:\n'
         '                _pct_sl = min(SL_PROTECTOR_PCT, 12.0 / _notional)\n'
         '        except Exception:\n'
         '            pass\n'
         '        if direccion == "LONG":\n'
         '            sl_px = ref * (1 - _pct_sl)\n'
         '        else:\n'
         '            sl_px = ref * (1 + _pct_sl)\n')
open(p, "w", encoding="utf-8").write(s.replace(ancla, nuevo, 1))
print("  adopcion con tope aplicada")
PYEOF
    if [ $? -ne 0 ] || ! python3 -m py_compile "$F"; then
        cp "$F.bakG" "$F" 2>/dev/null
        echo "[salud_bots] ERROR -> restaurado"
        exit 1
    fi
    echo "[salud_bots] adopcion OK"
fi

if systemctl restart okx-demo-bot.service 2>/dev/null; then
    echo "okx-demo-bot: reiniciado"
else
    echo "okx-demo-bot: AVISO, no se pudo reiniciar"
fi
echo "okx-real-bot: sigue PARADO (pausa manual)"

echo ""
echo "=== FIXG terminado ==="
