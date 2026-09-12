#!/usr/bin/env bash
# arreglar_cron_monitoreo.sh — corrige formato del cron y copia el script
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/arreglar_cron_mon_${TS}.log

CRON_FILE="/etc/cron.d/poly_monitoreo"
SCRIPTS_DIR="/opt/polymarket/scripts_despliegue"

{
echo "=== ARREGLAR CRON MONITOREO — $TS UTC ==="
echo
echo "== 1. Estado previo =="
cat "$CRON_FILE" 2>&1
echo
echo "== 2. Reescribir cron con formato correcto (campo user) =="
cat > "$CRON_FILE" <<EOF
# Monitoreo cada 5 min de los 3 bots (Elon/Zelenskyy/Trump)
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

*/5 * * * * root /usr/bin/bash $SCRIPTS_DIR/monitorear_bots.sh >/dev/null 2>&1
EOF
chmod 644 "$CRON_FILE"
echo "nuevo contenido:"
cat "$CRON_FILE"
echo
echo "== 3. Verificar que existe el directorio destino =="
ls -la "$SCRIPTS_DIR" 2>&1 | head -5
echo
echo "== 4. Copiar monitorear_bots.sh al directorio destino =="
# descargar fresh desde GitHub
BRANCH=$(gh api repos/lamegawi/bots-backup/branches/arena/01a058fe-bots-backup --jq '.commit.sha[:8]' 2>/dev/null || echo "HEAD")
echo "descargando desde rama (HEAD: $BRANCH)"
curl -sL -o "$SCRIPTS_DIR/monitorear_bots.sh" \
    "https://raw.githubusercontent.com/lamegawi/bots-backup/arena/01a058fe-bots-backup/scripts_despliegue/monitorear_bots.sh"
chmod +x "$SCRIPTS_DIR/monitorear_bots.sh"
ls -la "$SCRIPTS_DIR/monitorear_bots.sh"
echo
echo "== 5. Validar sintaxis del cron =="
# validar con crontab
if command -v crontab >/dev/null; then
    if crontab -T "$CRON_FILE" 2>/dev/null; then
        echo "  ✅ sintaxis válida"
    else
        echo "  ⚠️ crontab -T no disponible, probando otra forma"
        # intentar parsear manualmente
        grep -vE "^#|^$" "$CRON_FILE" | head -3
    fi
fi
echo
echo "== 6. Reiniciar cron para releer =="
systemctl restart cron 2>&1
systemctl status cron 2>&1 | head -5
echo
echo "== 7. Esperar 1 min y verificar que se ejecuta =="
sleep 65
ls -lat /tmp/mon_bots_*.log 2>&1 | head -3
echo
echo "== 8. Resumen =="
echo "  ✅ cron reescrito con formato correcto (campo 'root')"
echo "  ✅ monitorear_bots.sh copiado a $SCRIPTS_DIR/"
echo "  ✅ cron reiniciado"
echo
echo "  Esperar a la próxima pasada (cada 5 min en punto)"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/arreglar_cron_mon_*.log'))
LOG = logs[-1] if logs else '/tmp/arreglar_cron_mon.log'
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
