#!/usr/bin/env bash
# actualizar_filtros_trump_y_diag_ventanas_elon.sh
# 1. actualizar filtros Trump al nivel 10-sept (como Elon/Zelenskyy)
# 2. diagnosticar por qué ventanas 48h no salen en bot de Elon
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/act_fil_diag_ven_${TS}.log

TRUMP_DIR="/opt/polymarket/bot-polymarket-trump"
TRUMP_SENAL="$TRUMP_DIR/senal.py"
ELON_DIR="/opt/polymarket/bot-polymarket-elon"

{
echo "════════════════════════════════════════════"
echo "  ACTUALIZACIÓN FILTROS TRUMP + DIAG VENTANAS ELON — $TS UTC"
echo "════════════════════════════════════════════"
echo

echo "########################################"
echo "# PARTE 1: ACTUALIZAR FILTROS DE TRUMP"
echo "########################################"
echo
echo "== 1. Filtros actuales de Trump =="
grep -nE "^(CUOTA_MINIMA|PRECIO_MAX|EDGE_MIN|P_FLOOR|FACTOR|STAKE_INICIAL)" "$TRUMP_SENAL" 2>&1
echo
echo "== 2. Backup del senal.py =="
cp "$TRUMP_SENAL" "$TRUMP_SENAL.bak_${TS}"
echo "backup: $TRUMP_SENAL.bak_${TS}"
echo
echo "== 3. Actualizar filtros (alineado con Zelenskyy/Elon 10-sept) =="
# Reemplazar las líneas:
#   CUOTA_MINIMA   = 2.80          # cuota mínima aceptada
#   EDGE_MIN       = 0.12          # ventaja mínima p_modelo − precio (12 pp)
#   P_FLOOR        = 0.15          # p mínimo para entrar en un bin (evita colas)
# Por:
#   CUOTA_MINIMA   = 3.00          # cuota mínima aceptada — SUBIDA de 2.80 a 3.00 (12/09)
#   PRECIO_MAX     = 0.30          # precio máximo del lado que compramos — NUEVO (12/09)
#   EDGE_MIN       = 0.15          # ventaja mínima p_modelo − precio — SUBIDA de 0.12 a 0.15 (12/09)
#   P_FLOOR        = 0.20          # p mínimo para entrar en un bin — SUBIDA de 0.15 a 0.20 (12/09)
sed -i 's/^CUOTA_MINIMA   = 2.80.*/CUOTA_MINIMA   = 3.00          # cuota mínima aceptada — SUBIDA de 2.80 a 3.00 (12\/09)/' "$TRUMP_SENAL"
# Insertar PRECIO_MAX=0.30 después de CUOTA_MINIMA
if ! grep -q "^PRECIO_MAX     = 0.30" "$TRUMP_SENAL"; then
    sed -i '/^CUOTA_MINIMA   = 3.00/a PRECIO_MAX     = 0.30          # precio máximo del lado que compramos — NUEVO (12\/09)' "$TRUMP_SENAL"
fi
sed -i 's/^EDGE_MIN       = 0.12.*/EDGE_MIN       = 0.15          # ventaja mínima p_modelo − precio — SUBIDA de 0.12 a 0.15 (12\/09)/' "$TRUMP_SENAL"
sed -i 's/^P_FLOOR        = 0.15.*/P_FLOOR        = 0.20          # p mínimo para entrar en un bin — SUBIDA de 0.15 a 0.20 (12\/09)/' "$TRUMP_SENAL"

echo "filtros actualizados:"
grep -nE "^(CUOTA_MINIMA|PRECIO_MAX|EDGE_MIN|P_FLOOR|FACTOR|STAKE_INICIAL)" "$TRUMP_SENAL" 2>&1
echo
echo "== 4. Verificar que no hay errores de sintaxis =="
python3 -m py_compile "$TRUMP_SENAL" 2>&1 && echo "  ✅ compila correctamente" || echo "  ❌ ERROR de sintaxis"
echo
echo "== 5. ¿Hay que reiniciar el servicio? =="
systemctl status poly-trump.service 2>&1 | head -8
echo
echo "== 6. NO reiniciar todavía — esperar al diag de ventanas =="
echo

echo "########################################"
echo "# PARTE 2: DIAGNÓSTICO VENTANAS 48H EN ELON"
echo "########################################"
echo
echo "== 1. ¿Qué archivo muestra el botón 'ventanas'? =="
# buscar archivos que mencionen 'ventana' o 'botón' o interfaz
grep -rlE "ventana|48h|48 h" /opt/polymarket/bot-polymarket-elon/*.py 2>&1 | head -10
echo
echo "== 2. ¿Qué tipo de mercado usa el bot de Elon? =="
grep -nE "tipo|tipo_mercado|48h|semanal|mensual" "$ELON_DIR/senal.py" 2>&1 | head -15
echo
echo "== 3. mercados_activos de Elon: ¿cuáles son? =="
python3 -c "
import json
d = json.load(open('$ELON_DIR/mercado_activo.json'))
ms = d.get('mercados', [])
print(f'total: {len(ms)}')
for m in ms:
    tipo = m.get('tipo', '?')
    cerrado = m.get('cerrado', False)
    titulo = m.get('titulo', '?')[:60]
    print(f'  [{tipo}] {\"[CERRADO]\" if cerrado else \"[ABIERTO]\"} {titulo}')
"
echo
echo "== 4. ¿Cómo clasifica el bot las ventanas (48h vs semanal)? =="
grep -nE "48h|semanal|horas_rest|duracion" "$ELON_DIR/senal.py" 2>&1 | head -15
echo
echo "== 5. ¿Qué ventana se muestra en el panel '4/4 Estado'? =="
tail -50 /opt/polymarket/bot-polymarket-elon/bot.log 2>&1 | grep -A2 -B2 "Estado\|mercado" | head -30
echo
echo "== 6. ¿El log muestra el TIPO de mercado? =="
tail -100 /opt/polymarket/bot-polymarket-elon/bot.log 2>&1 | grep -iE "tipo.*48h|tipo.*semanal|mercado.*tipo" | head -10
echo
echo "== 7. mercado_activo.json: claves 'tipo' vs realidad =="
python3 -c "
import json
d = json.load(open('$ELON_DIR/mercado_activo.json'))
ms = d.get('mercados', [])
# agrupar por tipo
tipos = {}
for m in ms:
    t = m.get('tipo', '?')
    tipos[t] = tipos.get(t, 0) + 1
print('distribución por tipo:')
for t, c in tipos.items():
    print(f'  {t}: {c}')
"
echo
echo "== 8. ¿bot.py tiene la lista de mercados en pantalla? =="
grep -nE "titulo.*48|48.*h|def.*mostrar|def.*estado" "$ELON_DIR/bot.py" 2>&1 | head -15
echo
echo "== 9. ¿Qué imprime '4/4 Estado:' exactamente? =="
grep -nE "4/4|def.*estado|print.*estado" "$ELON_DIR/bot.py" 2>&1 | head -10
echo
echo "== 10. ¿El bot muestra TODOS los mercados activos o solo uno? =="
sed -n '180,220p' "$ELON_DIR/bot.py" 2>&1
echo
echo "== 11. Última pasada completa =="
tail -40 /opt/polymarket/bot-polymarket-elon/bot.log 2>&1
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/act_fil_diag_ven_*.log'))
LOG = logs[-1] if logs else '/tmp/act_fil_diag_ven.log'
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
