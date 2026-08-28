#!/bin/bash
# RECOLECTOR POLY - junta todo el diagnostico de bot-poly en un solo archivo
# Solo LEE (no cambia nada).
BASE="${POLY_BASE:-/opt/polymarket}"
F="${POLY_OUT:-/root/diagnostico_poly.txt}"
export POLY_BASE="$BASE"

{
echo "###############################################"
echo "# DIAGNOSTICO POLYMARKET - $(date)"
echo "###############################################"

echo ""
echo "===== 1. SISTEMA ====="
date
uptime
hostname
timedatectl 2>/dev/null | head -4

echo ""
echo "===== 2. SERVICIOS Y TIMERS ====="
for s in poly-elon poly-gestor poly-mensual poly-semanal poly-telegram poly-telegram-zelen poly-zelenskyy; do
    echo "$s: $(systemctl is-active $s.service 2>/dev/null)"
done
systemctl list-timers --no-pager 2>/dev/null | grep -i poly | head -8

echo ""
echo "===== 3. PROCESOS PYTHON ====="
ps aux | grep python | grep -v grep | head -12

echo ""
echo "===== 4. RECOGIDA DE TWEETS ====="
echo "parche v3 (x-no-cache): $(grep -c 'x-no-cache' $BASE/bot-polymarket-elon/recoger_tweets.py 2>/dev/null)"
echo "parche v2 (x_hasta):    $(grep -c 'x_hasta' $BASE/bot-polymarket-elon/recoger_tweets.py 2>/dev/null)"
python3 - <<'PYEOF'
import json, os
_pb = os.environ.get("POLY_BASE", "/opt/polymarket")
try:
    d = json.load(open(_pb + "/bot-polymarket-elon/estado_tweets.json"))
    print("estado_tweets actualizado:", d.get("actualizado"),
          "| tweets unicos:", len(d.get("tweets", {})))
except Exception as e:
    print("estado_tweets ERROR:", e)
PYEOF
echo "--- datos_elon.csv (ultimos 40 dias) ---"
tail -40 $BASE/bot-polymarket-elon/datos_elon.csv 2>/dev/null
echo "--- otros CSV de datos (zelenskyy etc.) ---"
for f in $BASE/*/datos_*.csv; do
    [ "$f" = "$BASE/bot-polymarket-elon/datos_elon.csv" ] && continue
    echo "--- $f ---"
    tail -12 "$f" 2>/dev/null
done
echo "--- ultimas recogidas (jina-tw en bot.log) ---"
grep "jina-tw" $BASE/bot-polymarket-elon/bot.log 2>/dev/null | tail -10

echo ""
echo "===== 5. MOTOR EMPIRICO (senal en vivo) ====="
echo "parche SENAL-EMP: $(grep -c 'SENAL_EMP_ARENA' $BASE/bot-polymarket-elon/senal.py 2>/dev/null)"
cd $BASE/bot-polymarket-elon && timeout 150 python3 senal_vivo.py --actualizar 2>&1 | head -70
cd /root

echo ""
echo "===== 6. POSICIONES POLYMARKET (API publica) ====="
python3 - <<'PYEOF'
import json, re, glob, urllib.request, os
_pb = os.environ.get("POLY_BASE", "/opt/polymarket")
dirs = set()
for f in glob.glob(_pb + "/*.py"):
    try:
        src = open(f, encoding="utf-8", errors="replace").read()
        dirs.update(re.findall(r"0x[a-fA-F0-9]{40}", src))
    except Exception:
        pass
dirs = sorted(dirs)[:4]
print("carteras detectadas en configs:", dirs)
for addr in dirs:
    try:
        url = "https://data-api.polymarket.com/positions?user=" + addr + "&limit=30"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
        print("--- cartera", addr[:12], "---")
        n = 0
        for p in data:
            try:
                cur = float(p.get("currentValue", 0) or 0)
            except Exception:
                cur = 0
            if cur <= 0.001:
                continue
            n += 1
            print("  ", p.get("title"), "|", p.get("outcome"),
                  "| size", p.get("size"),
                  "| invertido $", p.get("initialValue"),
                  "| valor $", round(cur, 2))
        if n == 0:
            print("   (sin posiciones con valor)")
    except Exception as e:
        print("  ERROR cartera", addr[:12], ":", str(e)[:70])
PYEOF

echo ""
echo "===== 7. REGISTROS ====="
for f in $BASE/cierres_anticipados.json $BASE/motores/motores.json $BASE/bot-polymarket-elon/mercado_activo.json; do
    echo "--- $f ---"
    head -c 5000 "$f" 2>/dev/null
    echo ""
done
echo "--- estado de cada bot (estado*.json) ---"
for f in $BASE/*/estado*.json; do
    echo "--- $f ---"
    head -c 2500 "$f" 2>/dev/null
    echo ""
done

echo ""
echo "===== 8. CODIGO senal.py ====="
cat -n $BASE/bot-polymarket-elon/senal.py 2>/dev/null

echo ""
echo "===== 9. CODIGO senal_vivo.py ====="
cat -n $BASE/bot-polymarket-elon/senal_vivo.py 2>/dev/null

echo ""
echo "===== 10. CODIGO recoger_tweets.py ====="
cat -n $BASE/bot-polymarket-elon/recoger_tweets.py 2>/dev/null

echo ""
echo "===== 11. CODIGO gestionar_posiciones.py ====="
cat -n $BASE/gestionar_posiciones.py 2>/dev/null

echo ""
echo "===== 12. CODIGO check_integral.py ====="
cat -n $BASE/check_integral.py 2>/dev/null

echo ""
echo "===== 13. MAPAS DE LOS OTROS MOTORES ====="
for r in bot-polymarket-elon-semanal bot-polymarket-elon-mensual bot-polymarket-zelenskyy bot-polymarket-elon-v2; do
    echo "--- $r ---"
    grep -n "def \|_ARENA\|ENTRADA_MAX" $BASE/$r/senal*.py $BASE/$r/bot*.py 2>/dev/null | head -25
done

echo ""
echo "===== 14. LOGS ====="
echo "--- bot.log (elon, ultimas 150 lineas) ---"
tail -150 $BASE/bot-polymarket-elon/bot.log 2>/dev/null
for r in bot-polymarket-elon-semanal bot-polymarket-elon-mensual bot-polymarket-zelenskyy; do
    echo "--- logs de $r ---"
    find $BASE/$r -name "*.log" 2>/dev/null | while read lg; do
        echo "[$lg]"
        tail -40 "$lg" 2>/dev/null
    done
done

echo ""
echo "===== FIN ====="
} > "$F" 2>&1

echo ""
echo "=== RECOLECTOR POLY TERMINADO ==="
echo "Archivo: $F ($(wc -c < "$F") bytes)"
