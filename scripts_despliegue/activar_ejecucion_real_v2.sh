#!/usr/bin/env bash
# activar_ejecucion_real_v2.sh — instala py_clob_client + token_id correcto + ejecución
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/activar_ejec_v2_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"
ELON_DIR="/opt/polymarket/bot-polymarket-elon"

{
echo "=== ACTIVAR EJECUCIÓN REAL v2 — $TS UTC ==="
echo
echo "== 1. Instalar py_clob_client con --break-system-packages =="
pip install --break-system-packages py-clob-client 2>&1 | tail -5
echo
echo "== 2. Verificar instalación =="
python3 -c "
from py_clob_client.client import ClobClient
from py_clob_client.order_args import OrderArgs
print('  ✅ ClobClient + OrderArgs importados OK')
"
echo
echo "== 3. Reescribir mercado_polymarket.py (basado en Zelenskyy) =="
cat > "$NEW_DIR/mercado_polymarket.py" <<'PYEOF'
#!/usr/bin/env python3
"""
Lee mercados semanales de Polymarket y extrae token_id de cada bin
usando el método de Zelenskyy (events?slug=... + groupItemTitle).
"""
import json
import os
import subprocess

DATA_DIR = "/opt/polymarket/bot-polymarket-elon"
MERCADO_JSON = os.path.join(DATA_DIR, "mercado_activo.json")


def get_tokens_for_bin(slug, bin_titulo):
    """Devuelve (token_id_YES, token_id_NO) para un bin específico."""
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "40",
             f"https://gamma-api.polymarket.com/events?slug={slug}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            return None, None
        evs = json.loads(r.stdout)
        if not evs:
            return None, None
        ev = evs[0]
        for m in ev.get("markets", []):
            if (m.get("groupItemTitle") or "") == bin_titulo:
                tokens = json.loads(m.get("clobTokenIds") or "[]")
                if len(tokens) >= 2:
                    return tokens[0], tokens[1]
    except Exception as e:
        print(f"[ERROR get_tokens] {e}", flush=True)
    return None, None


def actualizar_mercado():
    """Lee mercado_activo.json (compartido con el bot 48h) y devuelve solo semanales."""
    if not os.path.exists(MERCADO_JSON):
        return []
    with open(MERCADO_JSON) as f:
        d = json.load(f)
    mercados = d.get("mercados", [])
    # filtrar solo semanales y NO cerrados
    semanales = [m for m in mercados if m.get("tipo") == "semanal" and not m.get("cerrado")]
    # para cada mercado, obtener token_ids de cada bin
    for m in semanales:
        slug = m.get("slug", "")
        bins = m.get("bins", [])
        for b in bins:
            bin_titulo = b.get("titulo", "")
            if not bin_titulo or not slug:
                continue
            # si ya tenemos el token_id, saltar
            if b.get("token_id_yes") and b.get("token_id_no"):
                continue
            yes_id, no_id = get_tokens_for_bin(slug, bin_titulo)
            if yes_id:
                b["token_id_yes"] = yes_id
            if no_id:
                b["token_id_no"] = no_id
    return semanales


def info_mercados():
    mercados = actualizar_mercado()
    print(f"Mercados semanales abiertos: {len(mercados)}")
    for m in mercados:
        titulo = m.get("titulo", "?")[:60]
        slug = m.get("slug", "?")
        print(f"  · {titulo} [{slug}]")
        bins = m.get("bins", [])
        for b in bins[:3]:
            tid_y = b.get("token_id_yes", "?")
            print(f"    bin {b.get('titulo','?')}: token_id_yes={tid_y[:25]}")


if __name__ == "__main__":
    info_mercados()
PYEOF
echo "  ✅ mercado_polymarket.py reescrito (método Zelenskyy)"
echo
echo "== 4. Probar mercado_polymarket.py =="
cd "$NEW_DIR"
timeout 60 python3 mercado_polymarket.py 2>&1 | head -30
echo
echo "== 5. Verificar mercado_activo.json actualizado =="
python3 -c "
import json
d = json.load(open('$ELON_DIR/mercado_activo.json'))
ms = d.get('mercados', [])
for m in ms[:1]:
    if m.get('tipo') == 'semanal':
        bins = m.get('bins', [])
        b = bins[5] if len(bins) > 5 else (bins[0] if bins else None)
        if b:
            print(f'bin {b.get(\"titulo\")}: token_id_yes={b.get(\"token_id_yes\",\"?\")[:30]}...')
"
echo
echo "== 6. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 7. Verificar log =="
journalctl -u poly-elon-semanal.service -n 20 --no-pager 2>&1 | tail -15
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/activar_ejec_v2_*.log'))
LOG = logs[-1] if logs else '/tmp/activar_ejec_v2.log'
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
