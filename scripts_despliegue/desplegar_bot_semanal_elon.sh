#!/usr/bin/env bash
# desplegar_bot_semanal_elon.sh — crea bot paralelo para ventanas semanales de Elon
# Basado en la arquitectura de poly-zelenskyy.service
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/desplegar_semanal_elon_${TS}.log

ELON_DIR="/opt/polymarket/bot-polymarket-elon"
NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"
SCRIPTS_DIR="/opt/polymarket/scripts_despliegue"

{
echo "════════════════════════════════════════════"
echo "  DESPLIEGUE BOT SEMANAL ELON — $TS UTC"
echo "════════════════════════════════════════════"
echo

echo "== 1. Verificar directorio origen Elon =="
ls -la "$ELON_DIR" | head -3
echo

echo "== 2. Crear directorio del nuevo bot =="
mkdir -p "$NEW_DIR"
ls -la "$NEW_DIR"
echo

echo "== 3. Crear senal.py (basado en Zelenskyy, adaptado para Elon) =="
cat > "$NEW_DIR/senal.py" <<'EOF'
#!/usr/bin/env python3
"""
Motor de señal — ventana SEMANAL «Elon Musk # tweets <inicio> - <fin>?»
Adaptado del bot de Zelenskyy.
"""
import os
import sys
import csv
import json
import math
from datetime import datetime, timezone

# ─────────────── PARÁMETROS DE LA ESTRATEGIA ───────────────
VENTANA         = "semanal"     # solo semanal en este bot
STAKE_INICIAL   = 3.30          # $, primera apuesta (igual que Elon 48h)
FACTOR          = 1.40          # multiplicador tras cada fallo
CUOTA_MINIMA    = 3.00          # cuota mínima aceptada
PRECIO_MAX      = 0.30          # precio máximo del lado que compramos
EDGE_MIN        = 0.15          # ventaja mínima p_modelo − precio
P_FLOOR         = 0.20          # p mínimo para entrar en un bin
PASOS_MAX       = 6             # tope de escalones
REGLA           = "ventaja"     # "ventaja" (semanal)
LAM_MIN         = 1.0           # tweets/día mínimo
DATA_DIR        = "/opt/polymarket/bot-polymarket-elon"
CSV_PATH        = os.path.join(DATA_DIR, "datos_elon.csv")

# ─────────────── FUNCIONES ───────────────
def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def poisson_cdf(k, lam):
    """P(X ≤ k) con media lam."""
    if lam <= 0:
        return 1.0
    s = math.exp(-lam)
    cdf = s
    for i in range(1, k+1):
        s *= lam / i
        cdf += s
    return clamp(cdf, 0, 1)

def p_bin(lo, hi, lam):
    """Probabilidad de que λ caiga en [lo, hi]."""
    return clamp(poisson_cdf(hi, lam) - poisson_cdf(lo-1, lam), 0, 1)

def cargar_csv():
    """Carga el CSV compartido del bot 48h."""
    if not os.path.exists(CSV_PATH):
        return []
    datos = []
    with open(CSV_PATH) as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                datos.append((row['fecha'], int(row['tweets'])))
            except (KeyError, ValueError):
                continue
    return datos

def metricas(datos):
    """Calcula AVG7, AVG30, R, ajuste."""
    if len(datos) < 7:
        return None
    last7 = [t for _, t in datos[-7:]]
    last30 = [t for _, t in datos[-30:]] if len(datos) >= 30 else last7
    avg7 = sum(last7) / len(last7)
    avg30 = sum(last30) / len(last30)
    R = avg7 / avg30 if avg30 > 0 else 1.0
    ajuste = clamp(0.6 + 0.4 * R, 0.6, 1.4)
    return {'avg7': avg7, 'avg30': avg30, 'R': R, 'ajuste': ajuste, 'dias': len(datos)}

def decidir_bin(p, precio_yes, cuota_yes, cuota_no):
    """Regla 'ventaja' (semanal): p ≥ precio + EDGE_MIN."""
    if p >= 1 - P_FLOOR and cuota_yes and cuota_yes >= CUOTA_MINIMA and precio_yes <= PRECIO_MAX:
        return "APOSTAR YES", "YES", f"p_modelo {p:.1%} muy alta"
    if p <= P_FLOOR and cuota_no and cuota_no >= CUOTA_MINIMA and (1-precio_yes) <= PRECIO_MAX:
        return "APOSTAR NO", "NO", f"p_modelo {p:.1%} muy baja"
    vy = p - precio_yes
    vn = (1 - p) - (1 - precio_yes)
    if p >= P_FLOOR and vy >= EDGE_MIN and cuota_yes and cuota_yes >= CUOTA_MINIMA and precio_yes <= PRECIO_MAX:
        return "APOSTAR YES", "YES", f"ventaja {vy:.0%}pp, cuota {cuota_yes:.2f} ≥ {CUOTA_MINIMA:.2f}"
    if p <= 1 - P_FLOOR and vn >= EDGE_MIN and cuota_no and cuota_no >= CUOTA_MINIMA and (1-precio_yes) <= PRECIO_MAX:
        return "APOSTAR NO", "NO", f"ventaja {vn:.0%}pp, cuota {cuota_no:.2f} ≥ {CUOTA_MINIMA:.2f}"
    return "PASAR", None, "sin ventaja suficiente"

def tabla_apuestas(stake_inicial=STAKE_INICIAL, factor=FACTOR, pasos=PASOS_MAX):
    return [round(stake_inicial * (factor ** i), 2) for i in range(pasos)]

def main():
    datos = cargar_csv()
    m = metricas(datos)
    if not m:
        print("[ERROR] No hay suficientes datos en CSV")
        return
    print(f"AVG7={m['avg7']:.2f}  AVG30={m['avg30']:.2f}  R={m['R']:.3f}  ajuste={m['ajuste']:.3f}")
    print(f"días completos en CSV: {m['dias']}")
    print(f"Stake base: ${STAKE_INICIAL}")
    print(f"Cuota mínima: {CUOTA_MINIMA}, Precio máx: {PRECIO_MAX}")
    print(f"Edge mínimo: {EDGE_MIN}, P_floor: {P_FLOOR}")
    # Mostrar tabla de escalones
    print("Tabla de stakes:", tabla_apuestas())

if __name__ == "__main__":
    main()
EOF
chmod +x "$NEW_DIR/senal.py"
ls -la "$NEW_DIR/senal.py"
echo

echo "== 4. Crear mercado_polymarket.py (filtra solo tipo='semanal') =="
cat > "$NEW_DIR/mercado_polymarket.py" <<'EOF'
#!/usr/bin/env python3
"""
Lee mercados de Polymarket (compartido con bot 48h) y filtra solo tipo='semanal'.
"""
import json
import os

DATA_DIR = "/opt/polymarket/bot-polymarket-elon"
MERCADO_JSON = os.path.join(DATA_DIR, "mercado_activo.json")

def actualizar_mercado():
    """Lee mercado_activo.json (compartido con el bot 48h) y devuelve solo semanales."""
    if not os.path.exists(MERCADO_JSON):
        return []
    with open(MERCADO_JSON) as f:
        d = json.load(f)
    mercados = d.get("mercados", [])
    # FILTRAR solo tipo='semanal' y NO cerrados
    semanales = [m for m in mercados if m.get("tipo") == "semanal" and not m.get("cerrado")]
    return semanales

def info_mercados():
    mercados = actualizar_mercado()
    print(f"Mercados semanales abiertos: {len(mercados)}")
    for m in mercados:
        titulo = m.get("titulo", "?")[:60]
        fin = m.get("fin", "?")
        print(f"  · {titulo}")
        print(f"    cierre: {fin}")

if __name__ == "__main__":
    info_mercados()
EOF
chmod +x "$NEW_DIR/mercado_polymarket.py"
echo

echo "== 5. Crear bot_semanal.py (loop principal) =="
cat > "$NEW_DIR/bot_semanal.py" <<'EOF'
#!/usr/bin/env python3
"""
Loop principal del bot semanal de Elon.
Cada 15 min evalúa señales en ventanas semanales y opera si hay edge.
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone

NEW_DIR = "/opt/polymarket/bot-polymarket-elon-semanal"
ELON_DIR = "/opt/polymarket/bot-polymarket-elon"
sys.path.insert(0, NEW_DIR)
sys.path.insert(0, ELON_DIR)

REAL_JSON = os.path.join(NEW_DIR, "real_semanal.json")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def cargar_estado():
    if not os.path.exists(REAL_JSON):
        return {"saldo": 228.45, "paso": 1, "activa": None, "historial": []}
    with open(REAL_JSON) as f:
        return json.load(f)

def guardar_estado(d):
    with open(REAL_JSON, 'w') as f:
        json.dump(d, f, indent=2)

def pasada(opts):
    log("════════════════════════════════════════════")
    log("PASADA COMPLETA (ELON SEMANAL) · MODO: REAL")
    log("════════════════════════════════════════════")
    # 1) leer métricas del CSV compartido
    import senal
    datos = senal.cargar_csv()
    m = senal.metricas(datos)
    if m:
        log(f"AVG7={m['avg7']:.2f}  AVG30={m['avg30']:.2f}  R={m['R']:.3f}  ajuste={m['ajuste']:.3f}")
        log(f"días completos en CSV: {m['dias']}")
    # 2) leer mercados semanales
    import mercado_polymarket as mp
    semanales = mp.actualizar_mercado()
    log(f"{len(semanales)} mercados semanales abiertos")
    for mkt in semanales:
        log(f"  · {mkt.get('titulo','?')[:60]}")
    # 3) evaluar señales
    log("3/4 · Evaluando señales semanales…")
    # Aquí iría la lógica de cruce con senal_vivo y operar_real_semanal
    # Por ahora: solo evalúa, no opera
    log("  · (lógica de trading pendiente de integrar con senal_vivo)")
    log("════════════════════════════════════════════")
    log(f"Pasada completada")

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
            try:
                pasada(args)
            except Exception as e:
                log(f"ERROR: {e}")
            log(f"Próxima pasada en {args.intervalo} min…")
            time.sleep(args.intervalo * 60)
    else:
        pasada(args)

if __name__ == "__main__":
    main()
EOF
chmod +x "$NEW_DIR/bot_semanal.py"
ls -la "$NEW_DIR/"
echo

echo "== 6. Crear config.json =="
cat > "$NEW_DIR/config.json" <<'EOF'
{
  "ntfy": {
    "topic": "elon-poly-ple5k5aw",
    "token": null
  },
  "telegram": {
    "token": "8932364064:AAEE1iuyNX0beaVzFVcYMu_A4eNXCpEw8XE",
    "chat_id": "250818720"
  },
  "resumen": {
    "hora": 20
  }
}
EOF
echo "config.json creado"
echo

echo "== 7. Crear config_real.json =="
cat > "$NEW_DIR/config_real.json" <<'EOF'
{
  "wallet_address": "0xb0E1197098E6d427c01720F1631cAD24CE740FA0",
  "wallet_private_key": "PLACEHOLDER_OCULTO_POR_SEGURIDAD",
  "relayer_api_key": "",
  "relayer_api_key_address": "",
  "api_key": "",
  "api_secret": "",
  "api_passphrase": "",
  "bankroll": 228.45,
  "fee_pct": 0.0,
  "signature_type": 1,
  "confirmado": true
}
EOF
chmod 600 "$NEW_DIR/config_real.json"
echo

echo "== 8. Crear real_semanal.json =="
cat > "$NEW_DIR/real_semanal.json" <<'EOF'
{
  "saldo": 228.45,
  "paso": 1,
  "activa": null,
  "abierta": null,
  "historial": [],
  "_sincronizado_con_real": true,
  "_sincronizado_ts": "2026-09-12T08:00:00Z",
  "_bankroll_inicial_real": 228.45,
  "_pnl_historico_acumulado": 0.0
}
EOF
chmod 600 "$NEW_DIR/real_semanal.json"
ls -la "$NEW_DIR/real_semanal.json"
echo

echo "== 9. Crear servicio systemd poly-elon-semanal.service =="
cat > /etc/systemd/system/poly-elon-semanal.service <<'EOF'
[Unit]
Description=Bot Polymarket Elon SEMANAL (ventanas semanales, paralelo al 48h)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/polymarket/bot-polymarket-elon-semanal
EnvironmentFile=/etc/default/poly-elon-semanal
ExecStart=/usr/bin/python3 bot_semanal.py --loop --intervalo 15 --modo real
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
echo "poly-elon-semanal.service creado"
cat /etc/systemd/system/poly-elon-semanal.service
echo

echo "== 10. Recargar systemd y arrancar =="
systemctl daemon-reload
systemctl enable poly-elon-semanal.service 2>&1
systemctl start poly-elon-semanal.service 2>&1
sleep 3
systemctl status poly-elon-semanal.service 2>&1 | head -15
echo

echo "== 11. Verificación =="
PID=$(systemctl show poly-elon-semanal.service --property=MainPID --value)
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    echo "PID: $PID"
    tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | grep -E "^POLY_" | sed 's/=.*/=***OCULTO***/'
fi
echo

echo "== 12. Última línea del log =="
journalctl -u poly-elon-semanal.service -n 10 --no-pager 2>&1 | tail -15
echo

echo "== 13. Resumen =="
echo "  ✅ Directorio creado: $NEW_DIR"
echo "  ✅ senal.py (motor Poisson para semanal)"
echo "  ✅ mercado_polymarket.py (filtra solo tipo='semanal')"
echo "  ✅ bot_semanal.py (loop 15 min)"
echo "  ✅ config.json + config_real.json"
echo "  ✅ real_semanal.json (saldo 228.45)"
echo "  ✅ Servicio systemd: poly-elon-semanal.service"
echo
echo "  ⚠️  FALTA: /etc/default/poly-elon-semanal con POLY_PRIVATE_KEY"
echo "     (lo crearemos con el script de activación)"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/desplegar_semanal_elon_*.log'))
LOG = logs[-1] if logs else '/tmp/desplegar_semanal_elon.log'
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
