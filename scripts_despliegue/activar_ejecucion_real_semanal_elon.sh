#!/usr/bin/env bash
# activar_ejecucion_real_semanal_elon.sh — instala py_clob_client + token_id + ejecución real
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/activar_ejec_real_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"
ELON_DIR="/opt/polymarket/bot-polymarket-elon"
ZEL_DIR="/opt/polymarket/bot-polymarket-zelenskyy"

{
echo "=== ACTIVAR EJECUCIÓN REAL BOT SEMANAL ELON — $TS UTC ==="
echo
echo "== 1. ¿py_clob_client está instalado en otro bot? =="
ls -la /usr/lib/python3/dist-packages/py_clob_client 2>/dev/null | head -3
find /opt/polymarket -name "py_clob_client*" -type d 2>/dev/null | head -5
echo
echo "== 2. Ver cómo Zelenskyy obtiene token_id =="
grep -nA15 "def token_id_para_bin" "$ZEL_DIR/operar_real_semanal.py" 2>&1 | head -25
echo
echo "== 3. Instalar py_clob_client =="
pip install py-clob-client 2>&1 | tail -3
echo
echo "== 4. Verificar instalación =="
python3 -c "import py_clob_client; print(f'  versión: {py_clob_client.__version__ if hasattr(py_clob_client, \"__version__\") else \"OK\"}')" 2>&1
echo
echo "== 5. ¿Cómo Zelenskyy hace las llamadas? =="
grep -nA3 "create_order\|client.create" "$ZEL_DIR/operar_real_semanal.py" | head -20
echo
echo "== 6. Mercado activo JSON actual =="
python3 -c "
import json
d = json.load(open('$ELON_DIR/mercado_activo.json'))
ms = d.get('mercados', [])
for m in ms[:2]:
    print(f'  {m.get(\"titulo\",\"?\")[:50]}')
    bins = m.get('bins', [])
    if bins:
        b = bins[0]
        print(f'    bin: {b.get(\"lo\")}-{b.get(\"hi\")}')
        print(f'    keys: {list(b.keys())}')
"
echo
echo "== 7. Reescribir mercado_polymarket.py para obtener token_id desde Polymarket API =="
cat > "$NEW_DIR/mercado_polymarket.py" <<'PYEOF'
#!/usr/bin/env python3
"""
Lee mercados de Polymarket (compartido con bot 48h) y filtra solo tipo='semanal'.
Añade token_id consultando Gamma API si no está en el JSON.
"""
import json
import os
import urllib.request

DATA_DIR = "/opt/polymarket/bot-polymarket-elon"
MERCADO_JSON = os.path.join(DATA_DIR, "mercado_activo.json")
GAMMA_API = "https://gamma-api.polymarket.com/markets"


def get_token_ids(slug):
    """Consulta Gamma API para obtener token_id YES y NO de un mercado."""
    try:
        url = f"{GAMMA_API}?slug={slug}&active=true&closed=false"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if isinstance(data, list) and data:
            for m in data:
                tokens = m.get('tokens', [])
                if tokens:
                    yes_id = m.get('clobTokenIds', [''])[0] if m.get('clobTokenIds') else ''
                    # alternativa: tokens list
                    return yes_id, m.get('clobTokenIds', ['', ''])[1] if m.get('clobTokenIds') else ''
        elif isinstance(data, dict):
            tokens = data.get('clobTokenIds', [])
            if len(tokens) >= 2:
                return tokens[0], tokens[1]
    except Exception as e:
        print(f"[ERROR gamma API] {e}", flush=True)
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
    # para cada mercado, obtener token_ids si faltan
    for m in semanales:
        bins = m.get('bins', [])
        for b in bins:
            if not b.get('token_id_yes') or not b.get('token_id_no'):
                slug = m.get('slug', '')
                yes_id, no_id = get_token_ids(slug)
                if yes_id:
                    b['token_id_yes'] = yes_id
                if no_id:
                    b['token_id_no'] = no_id
    return semanales


def info_mercados():
    mercados = actualizar_mercado()
    print(f"Mercados semanales abiertos: {len(mercados)}")
    for m in mercados:
        titulo = m.get("titulo", "?")[:60]
        fin = m.get("fin", "?")
        slug = m.get("slug", "?")
        print(f"  · {titulo}")
        print(f"    cierre: {fin}")
        print(f"    slug: {slug}")
        bins = m.get('bins', [])
        if bins:
            b0 = bins[0]
            print(f"    primer bin: {b0.get('lo')}-{b0.get('hi')} token_id_yes={b0.get('token_id_yes','?')[:20]}")


if __name__ == "__main__":
    info_mercados()
PYEOF
echo "  ✅ mercado_polymarket.py reescrito con Gamma API"
echo
echo "== 8. Probar mercado_polymarket.py =="
cd "$NEW_DIR"
timeout 30 python3 mercado_polymarket.py 2>&1 | head -20
echo
echo "== 9. Verificar py_clob_client + test conexión =="
python3 -c "
try:
    from py_clob_client.client import ClobClient
    print('  ✅ ClobClient importado')
    client = ClobClient('https://clob.polymarket.com')
    print(f'  ✅ cliente creado (sin auth)')
except Exception as e:
    print(f'  ❌ ERROR: {e}')
"
echo
echo "== 10. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 11. Verificar log =="
journalctl -u poly-elon-semanal.service -n 20 --no-pager 2>&1 | tail -15
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/activar_ejec_real_*.log'))
LOG = logs[-1] if logs else '/tmp/activar_ejec_real.log'
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
