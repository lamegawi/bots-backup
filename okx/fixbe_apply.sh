#!/bin/bash
# FIXBE - solo el indicador de BE en el panel de posiciones.
# Marca "SL en BE" segun el SL vivo del exchange (vale tambien para fantasmas).
ROOT="${ROOT:-/root}"

echo "=== FIXBE: indicador BE en el panel ==="

for BOTF in "$ROOT/okx_real_bot.py" "$ROOT/okx_demo_bot.py"; do
    NOMBRE=$(basename "$BOTF")
    if [ ! -f "$BOTF" ]; then
        echo "[$NOMBRE] no existe, me lo salto"
        continue
    fi
    if grep -q "FIXBE_ARENA" "$BOTF"; then
        echo "[$NOMBRE] ya parcheado"
        continue
    fi
    cp "$BOTF" "$BOTF.bakB"

    python3 - "$BOTF" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()

bloque_be = (
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
    '            pass\n')

aA = ('        m = managed.get(p["base"] + ": " + d)\n'
      '        if m and m.get("state") == "breakeven":\n'
      '            linea += " | SL en BE"\n'
      '        lineas.append(linea)\n')
aB = ('        m = managed.get(f"{p[\'base\']}:{d}")\n'
      '        if m and m.get("state") == "breakeven":\n'
      '            linea += " · \U0001F512 SL en BE"\n'
      '        lineas.append(linea)\n')

for nombre, ancla in (("A", aA), ("B", aB)):
    n = s.count(ancla)
    if n == 1:
        s = s.replace(ancla, ancla.replace("        lineas.append(linea)\n",
                                           bloque_be + "        lineas.append(linea)\n"), 1)
        open(p, "w", encoding="utf-8").write(s)
        print("  parcheado con variante %s" % nombre)
        raise SystemExit(0)
    if n > 1:
        print("  [aviso] variante %s aparece %d veces" % (nombre, n))

print("  no encontre el bloque. Contexto de cada lineas.append(linea):")
lineas = s.split("\n")
for i, l in enumerate(lineas):
    if "lineas.append(linea)" in l:
        print("  --- linea %d ---" % (i + 1))
        for j in range(max(0, i - 4), min(len(lineas), i + 1)):
            print("   ", lineas[j])
raise SystemExit(1)
PYEOF

    if [ $? -ne 0 ]; then
        cp "$BOTF.bakB" "$BOTF" 2>/dev/null
        echo "[$NOMBRE] no se pudo parchear -> sin cambios"
        continue
    fi
    if python3 -m py_compile "$BOTF"; then
        echo "[$NOMBRE] OK"
    else
        cp "$BOTF.bakB" "$BOTF"
        echo "[$NOMBRE] ERROR sintaxis -> restaurado"
    fi
done

if systemctl restart okx-demo-bot.service 2>/dev/null; then
    echo "okx-demo-bot: reiniciado"
fi
echo "=== FIXBE terminado ==="
