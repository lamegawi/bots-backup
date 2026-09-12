#!/usr/bin/env bash
# fix_proxy_no_inyectado.sh — diagnosticar y arreglar inyección de proxy en bot_semanal.py
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/fix_proxy_inj_${TS}.log

NEW_DIR=/opt/polymarket/bot-polymarket-elon-semanal

{
echo "=== FIX PROXY NO INYECTADO — ${TS} UTC ==="
echo
echo "== 1. Ver el service file =="
cat /etc/systemd/system/poly-elon-semanal.service
echo
echo "== 2. Ver /etc/polymarket.env (proxy) =="
grep -E "HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY" /etc/polymarket.env
echo
echo "== 3. Ver el process bot_semanal y sus env vars =="
PID=$(pgrep -f "bot_semanal.py --loop" | head -1)
echo "  PID: $PID"
if [ -n "$PID" ]; then
    echo "  env vars relevantes:"
    tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | grep -iE "HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY" | sort
fi
echo
echo "== 4. ¿Cómo lee bot_semanal.py el proxy? =="
grep -nE "HTTP_PROXY|proxy" "$NEW_DIR/bot_semanal.py" | head -10
echo
echo "== 5. ¿Está leyendo os.environ correctamente? =="
grep -nE "os\.environ|getenv" "$NEW_DIR/bot_semanal.py" | head -5
echo
echo "== 6. Si NO lee el proxy, arreglar el código para usar requests/httpx con proxy =="
# Backup
cp "$NEW_DIR/bot_semanal.py" "$NEW_DIR/bot_semanal.py.bak_proxy_${TS}"

python3 <<'PYEOF'
p = '/opt/polymarket/bot-polymarket-elon-semanal/bot_semanal.py'
with open(p) as f:
    t = f.read()

# Ver si ya importa os y lee proxy
if 'os.environ.get' in t and 'HTTP_PROXY' in t:
    print('  ya lee HTTP_PROXY del entorno')
else:
    # añadir import os al principio
    if 'import os' not in t:
        t = t.replace('import sys', 'import os\nimport sys', 1)
        print('  ✅ añadido import os')

    # En la sección de lectura del proxy (en try_ejecutar_orden), mejorar
    # Reemplazar la lectura simple por una configuración explícita
    old = "log(f\"   proxy configurado: {os.environ.get('HTTP_PROXY', 'no')[:50]}\")"
    new = """http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    if http_proxy:
        log(f"   ✅ proxy configurado: {http_proxy}")
    else:
        log(f"   ⚠️ NO HAY PROXY CONFIGURADO en el entorno")"""
    if old in t:
        t = t.replace(old, new)
        print('  ✅ mejorada lectura de proxy')

with open(p, 'w') as f:
    f.write(t)
PYEOF
echo
echo "== 7. Añadir configuración explícita de proxy al ClobClient =="
python3 <<'PYEOF'
p = '/opt/polymarket/bot-polymarket-elon-semanal/bot_semanal.py'
with open(p) as f:
    t = f.read()

# Buscar la sección de creación del ClobClient y añadir proxy
# El ClobClient no tiene parámetro proxy directo, pero usa httpx internamente
# Solución: configurar HTTPS_PROXY ANTES de instanciar
# Esto hace que httpx use el proxy automáticamente

# Añadir antes de la creación del cliente
old = "client = ClobClient("
if 'http_proxy = os.environ.get' not in t or 'os.environ.copy()' not in t:
    # Inyectar vars de proxy al entorno del proceso si no están
    # Ya están en el service file, pero por si acaso
    insert_before = "        from py_clob_client.client import ClobClient"
    proxy_setup = """        # Asegurar que las variables de proxy están en el entorno
        for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY']:
            val = os.environ.get(var)
            if not val:
                # leer de /etc/polymarket.env
                try:
                    with open('/etc/polymarket.env') as f:
                        for line in f:
                            if line.strip().startswith(var + '='):
                                val = line.split('=', 1)[1].strip().strip('"').strip("'")
                                os.environ[var] = val
                                break
                except Exception:
                    pass

        """ + insert_before
    if insert_before in t and 'Asegurar que las variables de proxy' not in t:
        t = t.replace(insert_before, proxy_setup, 1)
        print('  ✅ añadido setup de proxy antes de import ClobClient')
    else:
        print('  ya tiene setup de proxy o no se encontró el patrón')

with open(p, 'w') as f:
    f.write(t)
PYEOF
echo
echo "== 8. Validar =="
python3 -m py_compile "$NEW_DIR/bot_semanal.py" 2>&1 && echo "  ✅ compila OK"
echo
echo "== 9. Borrar caches =="
find "$NEW_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo "  ✅ caches borrados"
echo
echo "== 10. Probar pasada única con proxy =="
cd "$NEW_DIR"
timeout 30 python3 bot_semanal.py 2>&1 | tail -25
echo
echo "== 11. Reiniciar servicio =="
systemctl restart poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -8
echo
echo "== 12. Verificar log =="
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
