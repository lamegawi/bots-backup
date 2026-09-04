#!/bin/bash
# DESPLEGAR BOT DE TRUMP EN HETZNER desde lamegawi/bots-backup commit a5c02ed
# Ejecutar como root en la consola de Hetzner. NO REINICIAR NADA si hay un error.
set -e
TS=$(date +%Y%m%d_%H%M%S)
echo "########################################"
echo "# Despliegue Trump · $TS"
echo "########################################"
echo ""

# === 0. Comprobaciones previas ===
echo "=== 0. Comprobaciones previas ==="
[ -d /opt/polymarket ] || { echo "❌ /opt/polymarket no existe"; exit 1; }
[ -d /opt/polymarket/bot-polymarket-trump ] || { echo "❌ bot-polymarket-trump no existe"; exit 1; }
[ -d /opt/polymarket/codigo ] || { echo "❌ /opt/polymarket/codigo no existe"; exit 1; }
echo "✓ Estructura básica presente"

# === 1. Backup ===
echo ""
echo "=== 1. Backup de la versión actual ==="
BKP=/opt/polymarket/backup_pre_repo_$TS
mkdir -p $BKP
cp -a /opt/polymarket/bot-polymarket-trump $BKP/bot-polymarket-trump.orig
cp /opt/polymarket/codigo/check_salud.py $BKP/check_salud.py.orig 2>/dev/null || true
cp /opt/polymarket/codigo/check_integral.py $BKP/check_integral.py.orig 2>/dev/null || true
echo "✓ Backup en $BKP"
ls $BKP/

# === 2. Clonar el repo y dejar los archivos preparados en /tmp ===
echo ""
echo "=== 2. Clonar el repo ==="
cd /tmp
rm -rf bots-backup-despliegue
git clone --branch arena/01a058fe-bots-backup https://github.com/lamegawi/bots-backup.git bots-backup-despliegue 2>&1 | tail -3
cd bots-backup-despliegue
git log --oneline -3
NUEVO=$(git rev-parse --short HEAD)
echo "Vamos a desplegar el commit $NUEVO"

# === 3. Comparar antes de machacar ===
echo ""
echo "=== 3. Diff resumen ==="
echo "Bot de Trump: $(ls /opt/polymarket/bot-polymarket-trump/*.py | wc -l) .py actuales vs $(ls poly/codigo/bot-polymarket-trump/*.py | wc -l) en el repo"
echo ""
echo "--- Archivos que van a cambiar en el bot de Trump ---"
for f in $(ls /opt/polymarket/bot-polymarket-trump/*.py); do
  base=$(basename $f)
  if [ -f "poly/codigo/bot-polymarket-trump/$base" ]; then
    if ! diff -q "$f" "poly/codigo/bot-polymarket-trump/$base" >/dev/null 2>&1; then
      echo "  ✗ $base (cambia)"
    fi
  fi
done

# === 4. PARAR el servicio Trump para no romper nada a media operación ===
echo ""
echo "=== 4. Parando el servicio poly-trump (lo reiniciaremos al final) ==="
systemctl stop poly-trump 2>&1 || echo "no se pudo parar (¿no existe?)"
sleep 2
systemctl is-active poly-trump 2>&1 || echo "  (parado correctamente)"

# === 5. Copiar el bot de Trump (preservando config_real.json, estado_*.json, *.json runtime) ===
echo ""
echo "=== 5. Actualizar archivos del bot de Trump ==="
# Preservar todo lo que sea runtime
PRESERVAR=(
  "config_real.json"
  "estado_tweets_trump.json"
  "estado_bot_trump.json"
  "mercado_activo.json"
  "avisos_cooldown.json"
  "ventanas_vistas.json"
  "real_trump.json"
  "historial_trump.json"
  "datos_raw_trump"
)
PRES_DIR=/tmp/preservar_trump_$TS
mkdir -p $PRES_DIR
for f in "${PRESERVAR[@]}"; do
  if [ -e "/opt/polymarket/bot-polymarket-trump/$f" ]; then
    cp -a "/opt/polymarket/bot-polymarket-trump/$f" $PRES_DIR/
    echo "  preservado: $f"
  fi
done

# Borrar el bot viejo y poner el del repo
rm -rf /opt/polymarket/bot-polymarket-trump
cp -a poly/codigo/bot-polymarket-trump /opt/polymarket/

# Restaurar lo preservado
for f in "${PRESERVAR[@]}"; do
  if [ -e "$PRES_DIR/$f" ]; then
    cp -a "$PRES_DIR/$f" "/opt/polymarket/bot-polymarket-trump/"
    echo "  restaurado: $f"
  fi
done

# Permisos
chmod 600 /opt/polymarket/bot-polymarket-trump/config_real.json 2>/dev/null || true
chmod -R u+rwX,go+rX /opt/polymarket/bot-polymarket-trump/
echo "✓ Bot de Trump actualizado"

# === 6. Actualizar chequeos ===
echo ""
echo "=== 6. Actualizar chequeos con soporte --trump ==="
cp poly/codigo/check_salud.py /opt/polymarket/codigo/check_salud.py
cp poly/codigo/check_integral.py /opt/polymarket/codigo/check_integral.py
chmod +x /opt/polymarket/codigo/check_salud.py /opt/polymarket/codigo/check_integral.py
echo "✓ check_salud.py y check_integral.py actualizados"

# === 7. Validar sintaxis ===
echo ""
echo "=== 7. Validar sintaxis Python ==="
PYERR=0
for f in /opt/polymarket/bot-polymarket-trump/*.py /opt/polymarket/codigo/check_salud.py /opt/polymarket/codigo/check_integral.py; do
  if python3 -c "import ast; ast.parse(open('$f').read())" 2>/dev/null; then
    echo "  ✓ $(basename $f)"
  else
    echo "  ✗ ERROR en $f"
    PYERR=1
  fi
done
if [ $PYERR -ne 0 ]; then
  echo "❌ Hay errores de sintaxis. NO REINICIAR. Mira los archivos."
  exit 1
fi

# === 8. Actualizar ESTADO.md y motores.json (en el repo, ya hecho en github) ===
echo ""
echo "=== 8. ESTADO.md y motores.json ya están actualizados en GitHub ==="
echo "    Si quieres refrescarlos en /opt/polymarket: (opcional, no es crítico)"
echo "    cp /tmp/bots-backup-despliegue/poly/ESTADO.md /opt/polymarket/ESTADO.md"
echo "    cp /tmp/bots-backup-despliegue/poly/datos/motores.json /opt/polymarket/datos/motores.json 2>/dev/null || true"

# === 9. Arrancar el servicio ===
echo ""
echo "=== 9. Arrancando el servicio poly-trump ==="
systemctl start poly-trump
sleep 5
systemctl is-active poly-trump && echo "✓ poly-trump está active" || echo "❌ poly-trump NO arrancó. Mira journalctl -u poly-trump -n 30"
systemctl status poly-trump --no-pager | head -15

# === 10. Probar los chequeos con --trump (sin enviar telegram) ===
echo ""
echo "=== 10. Probar check_salud.py --trump (modo test, sin enviar telegram) ==="
cd /opt/polymarket/codigo
TRUMP_BOT_TOKEN="" TELEGRAM_CHAT_ID="" python3 check_salud.py --trump --test 2>&1 | head -30 || true

echo ""
echo "=== 11. Probar check_integral.py --trump (modo test) ==="
cd /opt/polymarket/codigo
TRUMP_BOT_TOKEN="" TELEGRAM_CHAT_ID="" python3 check_integral.py --trump --test 2>&1 | head -50 || true

# === 12. Resumen ===
echo ""
echo "########################################"
echo "# DESPLIEGUE COMPLETADO · $TS"
echo "# Commit desplegado: $NUEVO"
echo "# Backup en: $BKP"
echo "# Preservados en: $PRES_DIR"
echo "########################################"
echo ""
echo "Siguiente paso: revisa la salida de los chequeos de arriba."
echo "Si todo se ve OK, los chequeos se pueden activar en cron con:"
echo "  crontab -e"
echo "  y añadir (cada 15 min):"
echo "  */15 * * * * /opt/polymarket/codigo/check_salud.py --trump"
echo "  0 9 * * *   /opt/polymarket/codigo/check_integral.py --trump"
