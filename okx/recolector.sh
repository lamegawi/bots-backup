#!/bin/bash
# RECOLECTOR - junta todo el diagnostico en un archivo y lo manda por Telegram
F=/root/diagnostico_completo.txt

{
echo "###############################################"
echo "# DIAGNOSTICO COMPLETO - $(date)"
echo "###############################################"

echo ""
echo "===== 1. SISTEMA ====="
uptime
timedatectl 2>/dev/null | head -4

echo ""
echo "===== 2. SERVICIOS ====="
for s in okx-real-bot okx-demo-bot okx-signal-bot empatebot bolsa-bot; do
    echo "$s: $(systemctl is-active $s.service 2>/dev/null)"
done

echo ""
echo "===== 3. PARCHES Y ESTADO ====="
echo "FIX5 real: $(grep -c FIX5_ARENA /root/okx_real_bot.py 2>/dev/null)"
echo "FIX5 demo: $(grep -c FIX5_ARENA /root/okx_demo_bot.py 2>/dev/null)"
echo "FIXPAUSA: $(grep -c FIXPAUSA_ARENA /root/salud_bots.py 2>/dev/null)"
echo "bandera pausa: $(ls /root/.okx_real_pausado 2>/dev/null || echo NO)"
echo "crontab: $(crontab -l 2>/dev/null | tr '\n' ' ')"

echo ""
echo "===== 4. CUENTA REAL ====="
python3 - <<'PY1'
import sys, json
sys.path.insert(0, "/root")
e = {}
for l in open("/root/.okx_real_env"):
    l = l.strip()
    if "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1)
        e[k.replace("export","").strip()] = v.strip().strip('"').strip("'")
import okx_client as OKX
c = OKX.Cliente(e.get("OKX_REAL_KEY",""), e.get("OKX_REAL_SECRET",""), e.get("OKX_REAL_PASSPHRASE",""), demo=False)
for nombre, fn in (("SALDO", "saldo"), ("POSICIONES", "posiciones"), ("ALGOS", "algo_pendientes")):
    try:
        r = getattr(c, fn)() or []
        print(nombre + ":", len(r) if isinstance(r, list) else "")
        items = r if isinstance(r, list) else [r]
        for it in items[:40]:
            print(" ", json.dumps(it, ensure_ascii=False)[:400])
    except Exception as ex:
        print(nombre, "ERROR:", ex)
PY1

echo ""
echo "===== 5. CUENTA DEMO (+ LIMPIEZA DE ZOMBIS) ====="
python3 - <<'PY2'
import sys, json, time
sys.path.insert(0, "/root")
e = {}
for l in open("/root/.okx_demo_env"):
    l = l.strip()
    if "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1)
        e[k.replace("export","").strip()] = v.strip().strip('"').strip("'")
import okx_client as OKX
c = OKX.Cliente(e.get("OKX_DEMO_KEY",""), e.get("OKX_DEMO_SECRET",""), e.get("OKX_DEMO_PASSPHRASE",""), demo=True)
pos = set()
try:
    for p in c.posiciones() or []:
        if float(p.get("pos") or 0) != 0:
            pos.add((p.get("instId") or "?").split("-")[0])
            print("POSICION:", json.dumps(p, ensure_ascii=False)[:300])
except Exception as ex:
    print("posiciones ERROR:", ex)
ahora = time.time() * 1000
try:
    pend = c.algo_pendientes() or []
    print("ALGOS PENDIENTES:", len(pend))
    n = 0
    for a in pend:
        base = (a.get("instId") or "?").split("-")[0]
        try:
            ct = float(a.get("cTime") or 0)
        except Exception:
            ct = 0
        vieja = (ahora - ct) > 2 * 3600 * 1000
        print("  ", a.get("instId"), "| vieja:" , "si" if vieja else "no",
              "| tiene posicion:", "si" if base in pos else "NO")
        if base not in pos and vieja:
            try:
                c.cancelar_algo(a.get("instId"), a.get("algoId"))
                n += 1
                print("    -> ZOMBI CANCELADA")
            except Exception as ex:
                print("    -> fallo al cancelar:", str(ex)[:60])
    print("ZOMBIS CANCELADAS:", n)
except Exception as ex:
    print("algos ERROR:", ex)
PY2

echo ""
echo "===== 6. CODIGO okx_client.py (COMPLETO) ====="
cat -n /root/okx_client.py

echo ""
echo "===== 7. CODIGO okx_real_bot.py (COMPLETO) ====="
cat -n /root/okx_real_bot.py

echo ""
echo "===== 8. MAPA okx_demo_bot.py ====="
grep -n "def \|_ARENA" /root/okx_demo_bot.py | head -60

echo ""
echo "===== 9. LOG REAL (ultimas 250 lineas) ====="
tail -250 /var/log/okx-real-bot.log

echo ""
echo "===== 10. ORDENES Y STOPS DEL LOG REAL ====="
grep -E "ORDEN REAL|SL @|SL fallo|CRITICO|-> TP|TP:" /var/log/okx-real-bot.log | tail -60

echo ""
echo "===== 11. LOG DEMO (ultimas 80 lineas) ====="
tail -80 /var/log/okx-demo-bot.log

echo ""
echo "===== 12. SIGNAL BOT (sin ruido) ====="
grep -viE "getUpdates|timed out|reset by peer|name resolution" /root/okx_signal.log | tail -50

echo ""
echo "===== 13. NOCTURNO (log) ====="
tail -80 /root/salud_bots.log 2>/dev/null

echo ""
echo "===== 14. REGISTROS JSON ====="
for f in okx_real_journal.json okx_real_managed.json okx_real_protecciones.json okx_demo_journal.json okx_demo_managed.json okx_demo_protecciones.json okx_demo_blacklist.json; do
    echo "--- $f ---"
    head -c 6000 "/root/$f" 2>/dev/null
    echo ""
done

echo ""
echo "===== FIN ====="
} > "$F" 2>&1

echo "Archivo creado: $F ($(wc -c < "$F") bytes)"
echo "Enviando por Telegram..."
python3 - <<'PY3'
import urllib.request
e = {}
for l in open("/root/.okx_real_env"):
    l = l.strip()
    if "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1)
        e[k.replace("export","").strip()] = v.strip().strip('"').strip("'")
token = e.get("TELEGRAM_BOT_TOKEN", "")
chat = e.get("TELEGRAM_CHAT_ID", "")
if not (token and chat):
    print("sin token/chat de Telegram")
    raise SystemExit(0)
data = open("/root/diagnostico_completo.txt", "rb").read()
b = "XxDiagBoundaryxX"
head = ("--" + b + "\r\n" +
        'Content-Disposition: form-data; name="chat_id"\r\n\r\n' + chat + "\r\n" +
        "--" + b + "\r\n" +
        'Content-Disposition: form-data; name="document"; filename="diagnostico_completo.txt"\r\n' +
        "Content-Type: text/plain\r\n\r\n").encode()
body = head + data + ("--" + b + "--\r\n").encode()
req = urllib.request.Request("https://api.telegram.org/bot" + token + "/sendDocument",
                             data=body,
                             headers={"Content-Type": "multipart/form-data; boundary=" + b})
r = urllib.request.urlopen(req, timeout=40)
print("Telegram OK:", r.read()[:80])
PY3
echo ""
echo "Si no llego por Telegram, descargalo en tu PC con:"
echo "  scp root@49.13.84.168:/root/diagnostico_completo.txt ."
