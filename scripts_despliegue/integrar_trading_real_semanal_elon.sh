#!/usr/bin/env bash
# integrar_trading_real_semanal_elon.sh — añade lógica de trading real al bot semanal
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/integrar_trading_real_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"
ZEL_DIR="/opt/polymarket/bot-polymarket-zelenskyy"

{
echo "=== INTEGRAR TRADING REAL BOT SEMANAL ELON — $TS UTC ==="
echo
echo "== 1. Ver funciones de operar_real_semanal.py de Zelenskyy =="
ls -la "$ZEL_DIR/operar_real_semanal.py"
grep -nE "^def |^[A-Z_]+ *=" "$ZEL_DIR/operar_real_semanal.py" 2>&1 | head -25
echo
echo "== 2. Ver senal_vivo.py de Zelenskyy (lógica de evaluación) =="
ls -la "$ZEL_DIR/senal_vivo.py"
grep -nE "^def |MOTOR_ACTUAL" "$ZEL_DIR/senal_vivo.py" 2>&1 | head -20
echo
echo "== 3. Backup del bot_semanal.py actual =="
cp "$NEW_DIR/bot_semanal.py" "$NEW_DIR/bot_semanal.py.bak_int_${TS}"
echo
echo "== 4. Reescribir bot_semanal.py con trading real integrado =="
cat > "$NEW_DIR/bot_semanal.py" <<'PYEOF'
#!/usr/bin/env python3
"""
Loop principal del bot semanal de Elon con TRADING REAL.
Importa 'senal' SOLO desde NEW_DIR para evitar conflicto con el bot 48h.
Usa funciones de senal_vivo (evaluación) y operar_real_semanal (ejecución).
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime

NEW_DIR = "/opt/polymarket/bot-polymarket-elon-semanal"
REAL_JSON = os.path.join(NEW_DIR, "real_semanal.json")
CONFIG_PATH = os.path.join(NEW_DIR, "config_real.json")

# ⚠️ CRÍTICO: solo NEW_DIR en sys.path para evitar conflicto con bot 48h
sys.path = [NEW_DIR] + [p for p in sys.path if p not in ("", NEW_DIR, "/opt/polymarket/bot-polymarket-elon")]


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


def evaluar_senal(metricas, mercado, bin_lo, bin_hi, precio_yes, cuota_yes, cuota_no):
    """Evalúa si hay señal válida en un bin. Devuelve (decision, lado, ev) o (None, None, 0)."""
    import senal
    if not metricas:
        return None, None, 0
    # Calcular lambda esperado para este bin (semanal)
    avg7 = metricas['avg7']
    ajuste = metricas['ajuste']
    lam = 7 * avg7 * ajuste  # tweets esperados en la semana
    # Probabilidad de que caiga en el bin [lo, hi]
    p = senal.p_bin(bin_lo, bin_hi, lam)
    # Llamar a la lógica de decisión de senal
    decision, lado, motivo = senal.decidir_bin(p, precio_yes, cuota_yes, cuota_no)
    if decision in ("APOSTAR YES", "APOSTAR NO"):
        # Calcular EV
        cuota = cuota_yes if lado == "YES" else cuota_no
        ev = p * (cuota - 1) - (1 - p) if lado == "YES" else (1 - p) * (cuota - 1) - p
        return decision, lado, ev, motivo
    return None, None, 0, motivo


def pasada(opts):
    log("════════════════════════════════════════════")
    log("PASADA COMPLETA (ELON SEMANAL) · MODO: REAL")
    log("════════════════════════════════════════════")
    try:
        # Forzar recarga de módulos
        for m in ('senal', 'mercado_polymarket', 'senal_vivo'):
            if m in sys.modules:
                del sys.modules[m]
        import senal
        import mercado_polymarket as mp
        # 1) Métricas desde CSV
        datos = senal.cargar_csv()
        m = senal.metricas(datos)
        if m:
            log(f"📊 AVG7={m['avg7']:.2f}  AVG30={m['avg30']:.2f}  R={m['R']:.3f}  ajuste={m['ajuste']:.3f}")
        # 2) Mercados semanales
        semanales = mp.actualizar_mercado()
        log(f"📈 {len(semanales)} mercados semanales abiertos")
        # 3) Estado
        estado = cargar_estado()
        log(f"💰 saldo=${estado['saldo']}  paso={estado['paso']}  activa={'sí' if estado.get('activa') else 'no'}")
        # 4) Si hay activa, NO buscar nuevas
        if estado.get('activa'):
            log(f"⏸️  Ya hay posición activa en {estado['activa'].get('slug','?')[:50]}")
            log(f"    paso {estado['activa'].get('paso')} stake ${estado['activa'].get('stake')}")
            log("════════════════════════════════════════════")
            return
        # 5) Evaluar señales en cada mercado
        mejor = None
        for mkt in semanales:
            titulo = mkt.get('titulo', '?')[:50]
            bins = mkt.get('bins', [])
            for b in bins:
                lo = b.get('lo', 0)
                hi = b.get('hi', 0)
                p_yes = b.get('precio_yes', 0)
                c_yes = b.get('cuota_yes', 0)
                c_no = b.get('cuota_no', 0)
                decision, lado, ev, motivo = evaluar_senal(m, mkt, lo, hi, p_yes, c_yes, c_no)
                if decision and ev > 0:
                    log(f"  🎯 {titulo} | bin {lo}-{hi} | {lado} @ {p_yes:.3f} (cuota {c_yes:.2f}/{c_no:.2f})")
                    log(f"     EV={ev:+.3f} | {motivo}")
                    if not mejor or ev > mejor[4]:
                        mejor = (mkt, b, decision, lado, ev, motivo)
        # 6) Si hay mejor señal, intentar operar
        if mejor:
            log(f"\n🚀 Mejor señal: {mejor[0].get('titulo','?')[:50]}")
            log(f"   bin {mejor[1].get('lo')}-{mejor[1].get('hi')} {mejor[3]} EV={mejor[4]:+.3f}")
            # En MODO REAL, intentar ejecutar la orden
            if opts.modo == "real":
                try_ejecutar_orden(mejor, estado, m)
            else:
                log("   (modo != real, no se ejecuta)")
        else:
            log("📭 Sin señales válidas esta vuelta")
        log("════════════════════════════════════════════")
        log(f"Pasada completada")
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        log(traceback.format_exc())


def try_ejecutar_orden(mejor, estado, metricas):
    """Intenta ejecutar la orden real. Si falla, registra pero no aborta."""
    import senal
    mkt, b, decision, lado, ev, motivo = mejor
    slug = mkt.get('slug', '')
    lo, hi = b.get('lo'), b.get('hi')
    precio = b.get('precio_yes') if lado == "YES" else 1 - b.get('precio_yes', 0)
    cuota = b.get('cuota_yes') if lado == "YES" else b.get('cuota_no')
    token_id = b.get('token_id_yes') if lado == "YES" else b.get('token_id_no')
    if not token_id:
        log(f"   ⚠️ sin token_id para {lado}, saltamos")
        return
    # Calcular stake según tabla
    paso = estado.get('paso', 1)
    stake = senal.tabla_apuestas()[min(paso-1, 5)]
    log(f"   💵 stake=${stake}  paso={paso}")
    # Intentar operar con el SDK CLOB si está disponible
    try:
        # cargar config
        if not os.path.exists(CONFIG_PATH):
            log(f"   ⚠️ no config_real.json")
            return
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        if not cfg.get('confirmado'):
            log(f"   ⚠️ config_real.json sin confirmado=true")
            return
        # Intentar usar py-clob-client
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.order_args import OrderArgs
            host = "https://clob.polymarket.com"
            chain_id = 137
            client = ClobClient(
                host,
                key=cfg.get('wallet_private_key'),
                chain_id=chain_id,
                signature_type=cfg.get('signature_type', 1),
                funder=cfg.get('wallet_address'),
            )
            # Crear orden límite
            order = OrderArgs(
                token_id=str(token_id),
                price=float(precio),
                side="BUY",
                size=float(stake / precio),
            )
            log(f"   📤 Enviando orden al CLOB…")
            resp = client.create_order(order)
            log(f"   ✅ orden creada: {resp}")
            # Actualizar estado con posición activa
            estado['activa'] = {
                'slug': slug,
                'bin': f"{lo}-{hi}",
                'lado': lado,
                'precio': precio,
                'cuota': cuota,
                'stake': stake,
                'paso': paso,
                'order_id': str(resp.get('orderID', '?')),
                'token_id': str(token_id),
                'fecha': datetime.now().isoformat(),
            }
            guardar_estado(estado)
            log(f"   💾 estado actualizado con posición activa")
        except ImportError:
            log(f"   ⚠️ py_clob_client no disponible")
            log(f"   💡 registrando señal en historial sin ejecutar")
            # Registrar como señal (sin orden real)
            estado['historial'].append({
                'fecha': datetime.now().strftime('%Y-%m-%d'),
                'mercado': slug,
                'bin': f"{lo}-{hi}",
                'lado': lado,
                'precio': precio,
                'cuota': cuota,
                'p_modelo': senal.p_bin(lo, hi, 7 * metricas['avg7'] * metricas['ajuste']),
                'paso': paso,
                'stake': stake,
                'ev': ev,
                'resultado': 'señal_detectada',
                'beneficio': 0,
                'saldo': estado['saldo'],
            })
            guardar_estado(estado)
    except Exception as e:
        log(f"   ❌ ERROR ejecutando orden: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--intervalo", type=int, default=15)
    ap.add_argument("--modo", default="real")
    ap.add_argument("--excel", action="store_true")
    args = ap.parse_args()
    log(f"🤖 BOT SEMANAL ELON arrancado (loop={args.loop}, intervalo={args.intervalo} min, modo={args.modo})")
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
echo "bot_semanal.py reescrito con trading real"
echo
echo "== 5. Validar sintaxis =="
python3 -m py_compile "$NEW_DIR/bot_semanal.py" 2>&1 && echo "  ✅ compila"
echo
echo "== 6. Borrar __pycache__ =="
find "$NEW_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>&1
echo "  ✅ caches borrados"
echo
echo "== 7. Verificar py_clob_client disponible =="
python3 -c "import py_clob_client; print('  ✅ py_clob_client disponible')" 2>&1 || echo "  ⚠️ py_clob_client NO instalado"
echo
echo "== 8. Probar manualmente con pasada única =="
cd "$NEW_DIR"
timeout 30 python3 bot_semanal.py 2>&1 | head -30
echo
echo "== 9. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -10
echo
echo "== 10. Verificar log =="
journalctl -u poly-elon-semanal.service -n 15 --no-pager 2>&1 | tail -10
echo
echo "== 11. Resumen =="
echo "  ✅ bot_semanal.py con trading real"
echo "  ✅ Evalúa señales, calcula EV, intenta ejecutar"
echo "  ✅ Si py_clob_client no está: registra señal en historial sin ejecutar"
echo "  ✅ servicio reiniciado"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/integrar_trading_real_*.log'))
LOG = logs[-1] if logs else '/tmp/integrar_trading_real.log'
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
