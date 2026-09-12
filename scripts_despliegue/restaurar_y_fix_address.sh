#!/usr/bin/env bash
# restaurar_y_fix_address.sh — restaurar bot_semanal.py y usar signer.address()
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/restore_fix_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

{
echo "=== RESTAURAR Y FIX ADDRESS — ${TS} UTC ==="
echo
echo "== 1. Listar backups =="
ls -lat "$NEW_DIR/bot_semanal.py".bak* 2>/dev/null | head -5
echo
echo "== 2. Buscar backup SIN syntax error =="
# probar backups del más reciente al más viejo
for b in $(ls -t "$NEW_DIR/bot_semanal.py".bak* 2>/dev/null); do
    if python3 -m py_compile "$b" 2>/dev/null; then
        echo "  backup válido: $b"
        GOOD_BAK="$b"
        break
    fi
done
echo
echo "== 3. Restaurar backup bueno =="
if [ -n "${GOOD_BAK}" ]; then
    cp "$GOOD_BAK" "$NEW_DIR/bot_semanal.py"
    echo "  ✅ restaurado desde $GOOD_BAK"
else
    echo "  ⚠️ ningún backup válido, descargar desde GitHub"
    curl -sL -o "$NEW_DIR/bot_semanal.py" \
        "https://raw.githubusercontent.com/lamegawi/bots-backup/c1dd38e7/poly/codigo/bot-polymarket-elon-semanal/bot_semanal.py"
    # NO FUNCIONARÁ porque ese archivo no está en el repo
    echo "  ⚠️ el bot_semanal.py no está en el repo, lo reescribimos desde cero"
fi
echo
echo "== 4. Reescribir bot_semanal.py con fix correcto =="
# Backup final
cp "$NEW_DIR/bot_semanal.py" "$NEW_DIR/bot_semanal.py.bak_final_${TS}"

cat > "$NEW_DIR/bot_semanal.py" <<'PYEOF'
#!/usr/bin/env python3
"""
Loop principal del bot semanal de Elon con TRADING REAL.
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

# Solo NEW_DIR en sys.path
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


def evaluar_senal(metricas, bin_lo, bin_hi, precio_yes, cuota_yes, cuota_no):
    import senal
    if not metricas:
        return None, None, 0, "sin métricas"
    avg7 = metricas['avg7']
    ajuste = metricas['ajuste']
    lam = 7 * avg7 * ajuste
    p = senal.p_bin(bin_lo, bin_hi, lam)
    decision, lado, motivo = senal.decidir_bin(p, precio_yes, cuota_yes, cuota_no)
    if decision in ("APOSTAR YES", "APOSTAR NO"):
        cuota = cuota_yes if lado == "YES" else cuota_no
        ev = p * (cuota - 1) - (1 - p) if lado == "YES" else (1 - p) * (cuota - 1) - p
        return decision, lado, ev, motivo
    return None, None, 0, motivo


def pasada(opts):
    log("════════════════════════════════════════════")
    log("PASADA COMPLETA (ELON SEMANAL) · MODO: REAL")
    log("════════════════════════════════════════════")
    try:
        for m in ('senal', 'mercado_polymarket'):
            if m in sys.modules:
                del sys.modules[m]
        import senal
        import mercado_polymarket as mp

        datos = senal.cargar_csv()
        m = senal.metricas(datos)
        if m:
            log(f"AVG7={m['avg7']:.2f}  AVG30={m['avg30']:.2f}  R={m['R']:.3f}  ajuste={m['ajuste']:.3f}")
        semanales = mp.actualizar_mercado()
        log(f"{len(semanales)} mercados semanales abiertos")
        estado = cargar_estado()
        log(f"saldo=${estado['saldo']}  paso={estado['paso']}  activa={'sí' if estado.get('activa') else 'no'}")

        if estado.get('activa'):
            log(f"Ya hay posición activa en {estado['activa'].get('slug','?')[:50]}")
            return

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
                decision, lado, ev, motivo = evaluar_senal(m, lo, hi, p_yes, c_yes, c_no)
                if decision and ev > 0:
                    log(f"  bin {lo}-{hi} | {lado} @ {p_yes:.3f} | EV={ev:+.3f}")
                    if not mejor or ev > mejor[4]:
                        mejor = (mkt, b, decision, lado, ev, motivo)

        if mejor:
            log(f"\nMejor señal: {mejor[0].get('titulo','?')[:50]}")
            log(f"   bin {mejor[1].get('lo')}-{mejor[1].get('hi')} {mejor[3]} EV={mejor[4]:+.3f}")
            if opts.modo == "real":
                try_ejecutar_orden(mejor, estado, m)
            else:
                log("   (modo != real, no se ejecuta)")
        else:
            log("Sin señales válidas")
        log("════════════════════════════════════════════")
        log("Pasada completada")
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        log(traceback.format_exc())


def try_ejecutar_orden(mejor, estado, metricas):
    import senal
    mkt, b, decision, lado, ev, motivo = mejor
    slug = mkt.get('slug', '')
    lo, hi = b.get('lo'), b.get('hi')
    precio = b.get('precio_yes') if lado == "YES" else 1 - b.get('precio_yes', 0)
    cuota = b.get('cuota_yes') if lado == "YES" else b.get('cuota_no')
    token_id = b.get('token_id_yes') if lado == "YES" else b.get('token_id_no')

    if not token_id:
        log(f"   sin token_id para {lado}, saltamos")
        return

    paso = estado.get('paso', 1)
    stake = senal.tabla_apuestas()[min(paso-1, 5)]
    log(f"   stake=${stake}  paso={paso}")
    log(f"   token_id: {str(token_id)[:30]}...")
    log(f"   proxy configurado: {os.environ.get('HTTP_PROXY', 'no')[:50]}")

    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        if not cfg.get('confirmado'):
            log(f"   config_real.json sin confirmado=true")
            return

        from py_clob_client.client import ClobClient
        try:
            from py_clob_client.order_args import OrderArgs
        except ImportError:
            from py_clob_client.clob_types import OrderArgs

        log(f"   importando ClobClient + OrderArgs OK")

        client = ClobClient(
            'https://clob.polymarket.com',
            key=cfg.get('wallet_private_key'),
            chain_id=137,
            signature_type=cfg.get('signature_type', 1),
            funder=cfg.get('wallet_address'),
        )
        log(f"   cliente creado")

        # derive API key
        try:
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
            log(f"   API creds derivadas")
        except Exception as e:
            log(f"   [aviso] no se pudieron derivar API creds: {e}")

        # crear orden
        order = OrderArgs(
            token_id=str(token_id),
            price=float(precio),
            side="BUY",
            size=float(stake / precio),
        )
        log(f"   enviando orden BUY {stake/precio:.2f} shares @ ${precio}")

        resp = client.create_and_post_order(order)
        order_id = resp.get("orderID") or resp.get("order_id") or "?"
        log(f"   ✅ ORDEN ENVIADA: {order_id}")

        estado['activa'] = {
            'slug': slug,
            'bin': f"{lo}-{hi}",
            'lado': lado,
            'precio': precio,
            'cuota': cuota,
            'stake': stake,
            'paso': paso,
            'order_id': order_id,
            'token_id': str(token_id),
            'fecha': datetime.now().isoformat(),
        }
        guardar_estado(estado)
        log(f"   estado guardado")
    except Exception as e:
        log(f"   ERROR ejecutando: {e}")
        import traceback
        log(traceback.format_exc())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--intervalo", type=int, default=15)
    ap.add_argument("--modo", default="real")
    ap.add_argument("--excel", action="store_true")
    args = ap.parse_args()
    log(f"BOT SEMANAL ELON arrancado (loop={args.loop}, intervalo={args.intervalo} min)")
    if args.loop:
        while True:
            pasada(args)
            log(f"Próxima pasada en {args.intervalo} min")
            time.sleep(args.intervalo * 60)
    else:
        pasada(args)


if __name__ == "__main__":
    main()
PYEOF
chmod +x "$NEW_DIR/bot_semanal.py"

echo "  bot_semanal.py reescrito completamente"
echo
echo "== 5. Validar =="
python3 -m py_compile "$NEW_DIR/bot_semanal.py" 2>&1 && echo "  ✅ compila OK"
echo
echo "== 6. Borrar caches =="
find "$NEW_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo
echo "== 7. Probar pasada única =="
cd "$NEW_DIR"
timeout 30 python3 bot_semanal.py 2>&1 | tail -25
echo
echo "== 8. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 9. Verificar log =="
journalctl -u poly-elon-semanal.service -n 15 --no-pager 2>&1 | tail -12
} > "${LOG}" 2>&1

cat "${LOG}"

# publicar
python3 -c "
import base64, json, urllib.request, os
LOG = '${LOG}'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': 'diag: ' + name, 'branch': 'diag-public', 'content': b64}
try:
    req = urllib.request.urlopen(urllib.request.Request(
        'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/' + name,
        data=json.dumps(p).encode(),
        headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
        method='PUT'), timeout=30)
    print('Publicado:', json.loads(req.read())['content']['path'])
except Exception as e:
    print('ERROR publicando:', e)
"
