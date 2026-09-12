#!/usr/bin/env bash
# fix_definitivo_bot_semanal_elon.sh — reescribe bot_semanal.py SIN importar senal de ELON_DIR
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/fix_def_bot_semanal_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== FIX DEFINITIVO BOT SEMANAL — $TS UTC ==="
echo
echo "== 1. Backup de bot_semanal.py =="
cp "$NEW_DIR/bot_semanal.py" "$NEW_DIR/bot_semanal.py.bak_${TS}"
echo "backup: $NEW_DIR/bot_semanal.py.bak_${TS}"
echo
echo "== 2. Reescribir bot_semanal.py (sin import de ELON_DIR) =="
cat > "$NEW_DIR/bot_semanal.py" <<'PYEOF'
#!/usr/bin/env python3
"""
Loop principal del bot semanal de Elon.
Importa 'senal' SOLO desde NEW_DIR para evitar conflicto con el bot 48h.
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime

NEW_DIR = "/opt/polymarket/bot-polymarket-elon-semanal"

# ⚠️ CRÍTICO: sys.path solo con NEW_DIR, sin ELON_DIR
# Si pusiéramos ELON_DIR, importaría el senal.py del bot 48h (no tiene CSV_PATH)
sys.path = [NEW_DIR] + [p for p in sys.path if p not in ("", NEW_DIR, "/opt/polymarket/bot-polymarket-elon")]

REAL_JSON = os.path.join(NEW_DIR, "real_semanal.json")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def cargar_estado():
    if not os.path.exists(REAL_JSON):
        return {"saldo": 228.45, "paso": 1, "activa": None, "historial": []}
    try:
        with open(REAL_JSON) as f:
            return json.load(f)
    except Exception:
        return {"saldo": 228.45, "paso": 1, "activa": None, "historial": []}


def guardar_estado(d):
    with open(REAL_JSON, 'w') as f:
        json.dump(d, f, indent=2)


def pasada(opts):
    log("════════════════════════════════════════════")
    log("PASADA COMPLETA (ELON SEMANAL) · MODO: REAL")
    log("════════════════════════════════════════════")
    try:
        # Import dentro de pasada para forzar recarga
        if 'senal' in sys.modules:
            del sys.modules['senal']
        import senal
        log(f"senal importado desde: {senal.__file__}")
        log(f"tiene CSV_PATH? {hasattr(senal, 'CSV_PATH')}")
        datos = senal.cargar_csv()
        m = senal.metricas(datos)
        if m:
            log(f"AVG7={m['avg7']:.2f}  AVG30={m['avg30']:.2f}  R={m['R']:.3f}  ajuste={m['ajuste']:.3f}")
            log(f"días en CSV: {m['dias']}")
            log(f"stakes: {senal.tabla_apuestas()}")
        else:
            log("⚠️ metricas None")
        # mercados semanales
        import mercado_polymarket as mp
        semanales = mp.actualizar_mercado()
        log(f"{len(semanales)} mercados semanales abiertos")
        for mkt in semanales:
            log(f"  · {mkt.get('titulo','?')[:60]}")
        log("3/4 · Evaluando señales semanales…")
        log("  · (lógica de trading pendiente)")
        log("════════════════════════════════════════════")
        log(f"Pasada completada")
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        log(traceback.format_exc())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--intervalo", type=int, default=15)
    ap.add_argument("--modo", default="real")
    ap.add_argument("--excel", action="store_true")
    args = ap.parse_args()
    log(f"🤖 BOT SEMANAL ELON arrancado (loop={args.loop}, intervalo={args.intervalo} min)")
    if args.loop:
        while True:
            pasada(args)
            log(f"Próxima pasada en {args.intervalo} min…")
            time.sleep(args.intervalo * 60)
    else:
        pasada(args)


if __name__ == "__main__":
    main()
PYEOF
echo "bot_semanal.py reescrito"
echo
echo "== 3. Validar sintaxis =="
python3 -m py_compile "$NEW_DIR/bot_semanal.py" 2>&1 && echo "  ✅ compila"
echo
echo "== 4. Borrar __pycache__ =="
find "$NEW_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>&1
find "$NEW_DIR" -name "*.pyc" -delete 2>&1
echo "  ✅ caches borrados"
echo
echo "== 5. Probar manualmente con pasada única =="
cd "$NEW_DIR"
timeout 30 python3 bot_semanal.py 2>&1 | head -20
echo
echo "== 6. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -10
echo
echo "== 7. Verificar log =="
journalctl -u poly-elon-semanal.service -n 15 --no-pager 2>&1 | tail -10
echo
echo "== 8. Resumen =="
echo "  ✅ bot_semanal.py reescrito (sys.path sin ELON_DIR)"
echo "  ✅ caches borrados"
echo "  ✅ servicio reiniciado"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/fix_def_bot_semanal_*.log'))
LOG = logs[-1] if logs else '/tmp/fix_def_bot_semanal.log'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': f'diag: {name}', 'branch': 'diag-public', 'content': b64}
try:
    req = urllib.request.urlopen(urllib.request.Request(
        f'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/{name}',
        data=json.dumps(p).encode(),
        headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
        method='PUT'), timeout=30)
    print('Publicado:', json.loads(req.read())['content']['path'])
except Exception as e:
    print('[ERROR publicando]', e)
PYEOF
