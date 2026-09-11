#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera desplegar_v1290_sin_pat.sh a partir de desplegar_v1284_sin_pat.sh.
Plan B: despliegue de v12.9.0 SIN GitHub/PAT. El parche (38 KB) viaja gzip+base64
dentro del propio script, así que basta con bajarlo de paste.rs (o pegarlo) en la
sesión SSH del server. Comprueba que el bot desplegado es la v12.8.4 (md5), parchea
sobre una copia, valida md5+compilación+funciones nuevas+GARANTÍAS de que el copy
no puede comprar, y sólo entonces sustituye y rearranca (dejando el modo en SEMI).

Los bloques de garantías y de comprobación EN VIVO del copy se EXTRAEN del
actualizar_v1290.sh ya generado, para que las dos rutas no diverjan.

Uso: python3 gen_planB_v1290.py
"""
import base64, gzip, hashlib, io, re

SRC = "/home/user/v12.8.4_semi/desplegar_v1284_sin_pat.sh"
ACT = "/home/user/bots-backup/scripts_despliegue/actualizar_v1290.sh"
PARCHE = "/home/user/v12.9_copytrading/parche_v1290.py"
BOT = "/home/user/v12.9_copytrading/bot_v1290.py"
DST = "/home/user/v12.9_copytrading/desplegar_v1290_sin_pat.sh"

MD5_ANTES = "e08cb649f4838a963135e2f301498092"      # v12.8.4 desplegada en el server
MD5_DESPUES = hashlib.md5(io.open(BOT, "rb").read()).hexdigest()
raw = io.open(PARCHE, "rb").read()
B64 = base64.b64encode(gzip.compress(raw, 9)).decode()

s = io.open(SRC, encoding="utf-8").read()
act = io.open(ACT, encoding="utf-8").read()
n = [0]


def rep(viejo, nuevo, etiqueta, veces=1):
    global s
    c = s.count(viejo)
    assert c == veces, f"'{etiqueta}': {c} coincidencias (esperaba {veces})"
    s = s.replace(viejo, nuevo, veces)
    n[0] += 1
    print(f"  ✓ {etiqueta}")


# ---------------------------------------------------------------- 1) renombres
c = s.count("v1284"); s = s.replace("v1284", "v1290"); n[0] += c
c = s.count("v12.8.4"); s = s.replace("v12.8.4", "v12.9.0"); n[0] += c
print("  ✓ renombres (v1284→v1290, v12.8.4→v12.9.0)")
rep("el bot no es la v12.8.3 esperada", "el bot no es la v12.8.4 esperada",
    "mensaje de md5 previo (la desplegada es la v12.8.4)")

# ------------------------------------------------------------- 2) md5 y blob
rep(f'MD5_ANTES="d096c581d57f05a66784c10f004fbf9b"', f'MD5_ANTES="{MD5_ANTES}"',
    "MD5_ANTES (v12.8.4)")
s2 = re.sub(r'^MD5_DESPUES="[0-9a-f]{32}"$', f'MD5_DESPUES="{MD5_DESPUES}"', s, count=1, flags=re.M)
assert s2 != s, "no se sustituyó MD5_DESPUES"
s = s2
print(f"  ✓ MD5_DESPUES={MD5_DESPUES}")

s2, k = re.subn(r'^echo "[A-Za-z0-9+/=]{1000,}" \| base64 -d \| gunzip > /tmp/parche_v1290\.py$',
                f'echo "{B64}" | base64 -d | gunzip > /tmp/parche_v1290.py', s, count=1, flags=re.M)
assert k == 1, "no se sustituyó el blob del parche"
s = s2
print(f"  ✓ parche v12.9.0 embebido: {len(raw)} bytes → {len(B64)} en base64")

# ------------------------------------------------------------ 3) cabecera
i0 = s.index("# Despliegue v12.9.0 SIN GitHub")
i1 = s.index("set -e", i0)
s = s[:i0] + r'''# Despliegue v12.9.0 SIN GitHub (plan B): el parche va gzip+base64 aquí dentro.
#   🏆 Top real en vivo (lb-api, ventanas 24 h/7 d/30 d/histórico + wallet).
#   📡 Copy-trading EN PAPEL de los 5 mejores del top 30d filtrados (activos, no
#      market makers, no concentrados, ≥40% deporte): cada compra suya es una
#      SEÑAL con dos precios (el suyo y el nuestro), las repetidas se fusionan,
#      tope propio 5/día, y al resolverse apunta acierto y PnL teórico a $5.
#   🔒 COPY_DINERO=False: no hay ruta del copy a firmar o enviar una orden.
#   🟡 Sigues en SEMI con intervalo de 10 min: este despliegue no cambia tu modo.
# Cómo usarlo (bajándolo de paste.rs, que es como se hizo con v12.8.4):
#     curl -sL <URL_paste_rs> -o /tmp/d1290.sh && bash /tmp/d1290.sh
# O pegando el script ENTERO en la sesión SSH:
#     cat > /tmp/d1290.sh <<'FIN'
#     ...(todo este fichero)...
#     FIN
#     bash /tmp/d1290.sh
''' + s[i1:]
n[0] += 1
print("  ✓ cabecera nueva")

# ------------------------------------- 4) paso 2: funciones + garantías 🔒
rep('''for fn in "def proponer_combo_semi" "def ejecutar_semi_aprobado" "def respuesta_propuesta" \\
          "def _marcar_propuesta" "def _prune_propuestas" "def _sin_tick" \\
          "PROPUESTA_VALIDA_S" "VENTAJA_MIN_EV" "ventaja insuficiente" \\
          "CUENTAS DE COMPENSACIÓN" "pnl_wins" "v12.9.0 cargado" \\
          "def restaurar_modo" "restaurar_modo(_est0)" \\
          "def teclado_fijo" "def cmd_leer_ahora" "def curar_abiertas" "def _reparto_mapa"; do
  if grep -q "$fn" /tmp/bot_v1290.py; then echo "   OK    $fn"; else echo "   FALTA $fn"; fi
done''',
    r'''for fn in "def proponer_combo_semi" "def ejecutar_semi_aprobado" "def respuesta_propuesta" \
          "def _marcar_propuesta" "def _prune_propuestas" "def _sin_tick" \
          "PROPUESTA_VALIDA_S" "VENTAJA_MIN_EV" "ventaja insuficiente" \
          "CUENTAS DE COMPENSACIÓN" "pnl_wins" "v12.9.0 cargado" \
          "def restaurar_modo" "restaurar_modo(_est0)" \
          "def teclado_fijo" "def cmd_leer_ahora" "def curar_abiertas" "def _reparto_mapa" \
          "def top_traders" "def nombre_lb" "def perfil_trader" "def filtros_perfil" \
          "def copy_elegir" "def fills_recientes" "def registrar_señal" \
          "def resolver_señales" "def resumen_copy" "def texto_copy" "def cmd_copy" \
          "def copy_pasada" "def programar_copy_inicio" "def _caras_de" "def _lb_get" \
          "LB_API" "COPY_DINERO = False" "COPY_ACTIVO = True" "COPY_N_TRADERS = 5" \
          "COPY_TOPE_DIA = 5" "COPY_DERIVA_MAX = 0.05" "COPY_MAX_VISTOS" \
          "copy_señales" "copy_pasada(CHAT_ID)" "programar_copy_inicio()" \
          'data.startswith("lb:")' '{"text": "📡 Copy"}' "NEXT_COPY_TS"; do
  if grep -q "$fn" /tmp/bot_v1290.py; then echo "   OK    $fn"; else echo "   FALTA $fn"; fi
done
if grep -q "pleaseplease123 +\$1.0M" /tmp/bot_v1290.py; then
  echo "   ❌ sigue la lista falsa del Top escrita a mano"; exit 1
else
  echo "   OK    la lista falsa del Top ya no está (ahora es lb-api en vivo)"
fi
MALO=$(sed -n '/^def _lb_get/,/^def cmd_top/p' /tmp/bot_v1290.py \
       | grep -c "enviar_orden(\|ejecutar_combo_rfq(\|firmar_orden_v3(\|crear_rfq(\|reservar_combo(\|ejecutar_trade(\|aceptar_rfq(\|obtener_identidad_rfq(" || true)
echo "   🔒 llamadas a compra en TODA la sección 📡: ${MALO:-0} (tiene que ser 0)"
if [ "${MALO:-0}" != "0" ]; then echo "   ❌ el copy-trading podría gastar: NO se despliega"; exit 1; fi
if ! grep -q "COPY_DINERO = False" /tmp/bot_v1290.py; then
  echo "   ❌ falta COPY_DINERO = False: NO se despliega"; exit 1
fi''', "paso 2: verificación v12.9.0 + garantías")

# ------------------------------------------ 5) paso 6: precio real del catálogo
rep('''    try:
        p = float(lg.get("yes_price") or lg.get("price") or 0)
    except Exception:
        p = 0.0
    if 0.70 <= p < 0.995:
        b.append((p, str(lg.get("question") or lg.get("title") or "?")[:52]))''',
    r'''    v = lg.get("outcome_prices")            # ← el catálogo RFQ usa ESTO
    if isinstance(v, str):                  #    (lista de textos [yes, no])
        try:
            v = json.loads(v)
        except Exception:
            v = []
    try:
        p = float((v or [0])[0])
    except Exception:
        p = 0.0
    if 0.70 <= p < 0.995:
        b.append((p, str(lg.get("title") or lg.get("question") or "?")[:52]))''',
    "paso 6: outcome_prices/title (antes siempre daba 0 legs)")

# ---------------------------- 6) paso 7 NUEVO: el copy EN VIVO (desde el actualizador)
i0 = act.index('echo "=== Paso 6c:')
i1 = act.index('echo ""\necho "   --- servicio y modo tras el arranque ---"', i0)
paso7 = act[i0:i1].replace("Paso 6c:", "Paso 7:")
assert "PYEOF" in paso7 and "lb-api" in paso7
rep('''echo ""
echo "=== EN TELEGRAM ==="''', paso7 + '''echo ""
echo "=== EN TELEGRAM ==="''', "paso 7 nuevo (copy EN VIVO, mismo bloque que el actualizador)")

# --------------------------------------------------------- 7) bloque EN TELEGRAM
i0 = s.index('echo "=== EN TELEGRAM ==="')
i1 = s.index("# Publicar en diag-public", i0)
s = s[:i0] + r'''echo "=== EN TELEGRAM ==="
echo "  🏆 Top         → ranking REAL (lb-api) con botones 24 h / 7 días / 30 días /"
echo "                   histórico: beneficio, volumen, margen y wallet de cada uno."
echo "                   La lista de antes estaba escrita a mano y ya no se parecía a nada."
echo "  📡 Copy        → panel del seguimiento EN PAPEL: a quiénes vigila, señales de hoy"
echo "                   (tope 5), acierto, ROI AL PRECIO NUESTRO, deriva, retraso medio y"
echo "                   desglose por trader. También con /copy (o /señales)."
echo "  🕐 1ª ronda    → ~90 s después de arrancar: elige los traders y te lo dice en el"
echo "                   chat. Después sondea cada 3 min e informa automáticamente cada 24 h."
echo "  🔒 Dinero      → CERO. COPY_DINERO=False: el copy no firma ni envía ninguna orden,"
echo "                   sólo lee ranking, fills y mids públicos (ni usa el proxy)."
echo "  🎯 Fase 2      → con ≥30 señales resueltas y ROI positivo AL PRECIO NUESTRO, la"
echo "                   señal se convertiría en un COMBO PROPIO por RFQ. Nunca líneas"
echo "                   sueltas: la regla de los combos multi-leg sigue intacta."
echo "  📊 Tus combos  → TODO sigue igual: 🟡 SEMI con propuesta ✅/❌ cada 10 min, filtro"
echo "                   de ventaja 5%, stake $5-10 y tope de 10 ops/día. El copy tiene su"
echo "                   propio tope (5 señales/día) y NO toca ese contador."
echo "  🟡 Modo        → sigues en SEMI: este despliegue no lo cambia (el bot restaura el"
echo "                   modo guardado al arrancar)."

''' + s[i1:]
n[0] += 1
print("  ✓ bloque final EN TELEGRAM")

# ------------------------------------------------------------- 8) comprobaciones
assert "v1284" not in s, "queda algún nombre viejo"
assert s.count(f'MD5_ANTES="{MD5_ANTES}"') == 1
assert s.count(f'MD5_DESPUES="{MD5_DESPUES}"') == 1
assert s.count("parche_v1290.py") >= 3
assert 'lg.get("yes_price")' not in s, "sigue el bug del precio del catálogo"
assert s.count('d["modo"] = "SEMI"') == 1
assert s.count("diag_hetzner/combos_update_v1290_sinpat_") == 1
assert s.count("PYEOF") == 4, f"heredocs PYEOF: {s.count('PYEOF')} (esperaba 4)"
assert s.count("=== Paso 7:") == 1 and s.count("=== Paso 6:") == 1
io.open(DST, "w", encoding="utf-8").write(s)
print(f"\n✅ {DST}")
print(f"   {len(s.splitlines())} líneas · {len(s.encode()) / 1024:.0f} KB · {n[0]} cambios")
print(f"   md5 del script: {hashlib.md5(s.encode()).hexdigest()}")
print(f"   MD5_ANTES={MD5_ANTES} (v12.8.4) · MD5_DESPUES={MD5_DESPUES} (v12.9.0)")
