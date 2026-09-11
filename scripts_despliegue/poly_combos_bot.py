#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POLY COMBOS BOT v12.9.0 — COMBOS REALES (parlays multi-leg) via RFQ
=====================================================
Estrategia nueva (vs v7):
  1. Lee COMBOS ACTIVOS del endpoint publico: /v1/rfq/combo-markets
  2. Cada combo = 2-10 legs, paga si TODOS aciertan
  3. Cuota objetivo 1.20-2.50 (multiplicacion de legs)
  4. v11.0: /v1/rfq/combo-markets es un CATALOGO DE LEGS (no combos formados).
     Los combos reales se crean por la Requester API (RFQ):
       POST combos-rfq-gateway-requester-api /v1/requester/rfq/requests
       con 2-50 leg_position_ids → quote de market makers → firmar orden
       Exchange v3 (EIP-712) → accept (<5s) → poll hasta FILLED (tx_hash)
     Docs: https://docs.polymarket.com/trading/combos/requesters
   v11.1: botones ⏱ 5/10/20/30/60 min para elegir el intervalo entre
   pasadas AUTO (persistido en combos_estado.json, efecto inmediato).
   v11.2: pre-check de saldo CLOB antes de firmar + reintento único
   idempotente si el accept falla por reserva transitoria (503 /
   PRE_EXECUTION_BALANCE_RESERVATION_FAILED) + aviso 💸 por Telegram.
   v11.3: ANTI-DUPLICIDAD de pasadas: un único ejecutor (auto_loop con
   lock); /start y 🟢 AUTO solo reprograman NEXT_PASADA_TS (ya no lanzan
   hilos paralelos); huella del combo RESERVADA en estado antes de crear
   el RFQ (y liberada si el intento falla terminalmente).
   v11.4: HORARIO PERSISTENTE — proximo_paso_ts y chat_id se guardan en
   estado; los reinicios/despliegues respetan el intervalo programado y
   YA NO provocan pasada inmediata al primer mensaje.
   v11.5: PANEL DE OPERACIONES EN VIVO — 📋/📂/✅ sincronizan contra el
   CLOB público: las ops resueltas pasan automáticamente de ABIERTAS a
   CERRADAS con 🟢/🔴 y PnL; los combos muestran estado por leg y la
   HORA DE FIN (Madrid) de cada combo; sync también al arrancar.
   v11.6: 📋 Trades vuelve a ser SOLO INFORMATIVO — top 1-10 del catálogo
   de combos por VOLUMEN EN $ (mayor primero), dentro del rango de cuota;
   las operaciones viven únicamente en 📂 Abiertas / ✅ Cerradas; se
   filtran los registros basura (sin pregunta/stake).
   v11.7: 📋 Trades muestra COMBOS CANDIDATOS REALES (2-3 legs de eventos
   distintos, cuota estimada en rango) generados con la misma lógica de
   selección del bot, ordenados por volumen $ — no líneas sueltas.
   v11.8: cada combo del catálogo lleva su PROBABILIDAD DE ACIERTO
   (producto de precios de legs, etiqueta alta/media/baja) y un BOTÓN
   INLINE ▶️ que ejecuta ESE combo en Polymarket (RFQ real, $5) con
   anti-duplicados y serializado con el auto_loop (PASADA_LOCK).
   v11.9: FRANJA EXTENDIDA 🚀 (petición user) — combos de cuota estimada
   (2.5, 3.0] si TODOS sus legs tienen p >= 0.70 (favoritos claros; con
   0.75 el techo matemático sería 2.37 y la franja no existiría), máximo
   2 extendidos/día, cuota real aceptada hasta 3.2, etiquetados en estado
   y paneles para poder medir resultados por separado.
   v12.0: TRES FRANJAS INDEPENDIENTES (petición user) —
   🤖 BASE (cuota 1.2-2.5): la ÚNICA automática (tope 6/día).
   🚀 EXTENDIDA (2.5-3.0, legs ≥0.70): SOLO MANUAL (botón), cupo 2/día.
   💥 SÚPER (cuota ≥5, 3-5 legs, p ≥0.55): SOLO MANUAL, nuevo botón
   💥 SúperCombos (top 10 informativo), cupo 2/día.
   📋 Trades: un mensaje por combo con SU botón debajo. Estadísticas y
   contadores diarios separados por franja (las manuales NO consumen
   el tope AUTO).
   v12.9.0: 🏆 TOP REAL EN VIVO + 📡 COPY-TRADING EN PAPEL (FASE 1, $0). El botón
   🏆 era una lista escrita a mano y falsa; ahora llama a lb-api (ventanas
   1d/7d/30d/all con botones) y enseña la wallet de cada trader. Además el bot
   vigila los fills de los 5 mejores (filtrados por conducta: activos, no market
   makers, no concentrados en 1-2 mercados y ≥40% deporte) y ANOTA cada compra
   como señal con dos precios: el suyo y el mid real al que nosotros entraríamos.
   Si el precio ya se movió más de 5 puntos, la señal se descarta por tardía. Escalan
   mucho (medido en vivo: 102 fills de un trader en 1 h eran sólo 4 posiciones), así
   que las compras repetidas del MISMO mercado se FUSIONAN en una señal: cuenta el
   importe total y vale el precio de la primera entrada, que es cuando nosotros
   habríamos entrado. El tope diario cuenta pues MERCADOS distintos, no fills.
   Cuando el mercado se resuelve se apunta si acertó y el PnL teórico a $5 al
   precio nuestro y al suyo → /copy da acierto, ROI, deriva y desglose por
   trader. NO GASTA NADA: COPY_DINERO=False, las señales viven en
   estado["copy_señales"] (nunca en trades_copiados) y no hay camino desde esta
   versión a firmar una orden. Se midió antes: copiar al top-1 histórico activo
   habría dado −48.8% en 48 h, y en 30 días conviven +130% con −100%.
   v12.8.4: 🟡 SEMI DE VERDAD + ⚖️ VENTAJA MÍNIMA 5%. SEMI era un modo muerto
   (auto_pasada salía al instante si el modo no era AUTO, y auto_loop ni
   escaneaba): pulsar 🟡 dejaba el bot parado, sin nada que aprobar. Ahora en
   SEMI el bot busca y TE PROPONE el combo con ✅ Aceptar / ❌ Descartar, la
   propuesta caduca a los 10 min y al aceptar se pide una cotización nueva
   (las del RFQ viven segundos) y se ejecuta por la ruta de AUTO. Además sólo
   compra si prob × cuota_real ≥ 1.05 (antes bastaba con que el RFQ no fuera
   peor que el mercado, o sea esperanza ≈ 0). Además el MODO guardado ya
   sobrevive al reinicio: main() no leía estado["modo"], así que el bot volvía
   siempre en AUTO por mucho que hubieras pulsado 🟡 SEMI. Y: ✅ verde en el botón
   del modo activo, 🧮 cuentas de compensación en 📊 Stats (victorias por
   derrota, win-rate de equilibrio) y cosméticos (arranque decía v12.8.1,
   anuladas sin cobro_real, "sin cobrar" contaba avisos de importe 0).
   v12.8.3: EL PANEL DICE LA VERDAD + ✅ + 🔍. (1) El botón ⏱ del intervalo
   ACTIVO lleva un tick verde ✅ (teclado dinámico, se reconstruye en cada
   mensaje). (2) Nuevo botón 🔍 Leer ahora (+ /leer): lectura inmediata que
   cuenta bankroll, catálogo, qué abriría y el estado REAL de cada posición,
   SIN abrir ni vender nada. (3) ⏸ mercado SUSPENDIDO y ↩️ ANULADO en
   cristiano, con la fecha de resolución prevista, y último precio publicado
   cuando /midpoint da 404. (4) 🧹 curación por evidencia de cadena: los
   registros de Abiertas se casan con los fills reales de data-api; los
   sobrantes (duplicados fantasma) y los vacíos (basura) salen a
   estado["descartadas"]. (5) Mercados simples cerrados SIN ganador declarado
   ya no se esperan para siempre: si la wallet cobró, se archivan con el
   dinero REAL, repartido entre los fills del mismo mercado en proporción a
   sus shares, y cuentan como "anulada" (↩️), no como ganada/perdida.
   v12.8.2: 🔒 EL CIERRE DE UN COMBO VUELVE A SER POSIBLE. `vivo_de()` pedía el
   precio con `legs[].position_id`, que es el id del CATÁLOGO de combos y NO el
   token_id del CLOB (`/midpoint` da 404 siempre con él): ningún combo tenía
   "precio vivo", así que 🔒 y /testcerrar acababan en "sin precio vivo" y el
   panel 📂 mostraba "precio ahora: n/d". Ahora cada leg se valora con su TOKEN
   REAL del CLOB (`token_clob_de_leg()`, resuelto por condition_id + outcome).
   Además: mensajes claros cuando la posición YA está resuelta (no se vende, se
   cobra) y `/reclamar` con pausa + reintento para no chocar con los 429 de RPC.
   v12.8.1: FIN DE LAS FALSAS ALARMAS de "ganadas sin cobrar". El primer aviso
   de la v12.8 (11-sep, "7 ganadas sin cobrar ~$47.58") era FALSO: eran 7 ops de
   MERCADO SIMPLE de la era copy-trading (Cagliari ×4, LoL IG-LGD, SMU-FSU ×2)
   que SÍ se cobraron (un redeem de $27.13 agrupa las 4 de Cagliari, $12.58 SMU,
   $7.87 LoL) y su saldo on-chain es 0 en el CTF y en el ERC1155 de parlays.
   Causas y arreglos: (a) `cobros_wallet()` leía /activity SIN filtro de tipo y
   los trades dejaban fuera los cobros antiguos ⇒ ahora pide `type=REDEEM` con 2
   páginas (77 cobros desde abril, no 48); (b) esas ops guardan un id que NO es
   el `asset` del cobro ⇒ nuevo índice por TÍTULO normalizado ("A AND B" ↔
   "A + B") con ventana temporal, y el cobro que se anota son SUS shares (1 token
   ganador = $1), nunca el total del redeem; (c) `reclamar_check()` no deduplicaba
   por token ni confirmaba on-chain ⇒ ahora deduplica y sólo avisa con saldo > 0;
   (d) cada op se mira en SU contrato: `saldo_token_op()` (combos → ERC1155 de
   parlays, simples → CTF `0x4D97…6045`), que es lo que usa `pendientes_reclamar`.
   v12.8: 💰 /reclamar — DETECTOR DE GANADAS SIN COBRAR. Recorre TODO el
   histórico y las abiertas (los cobros de Polymarket NO caducan ⇒ sin el límite
   de días de la auto-curación) y busca los combos GANADOS cuyo dinero SIGUE en
   tokens: sin cobro REDEEM en /activity + saldo on-chain > 0 en el ERC1155 de
   parlays + todas las legs ganadoras. Los lista con fecha, pagado, a cobrar y
   enlace al evento, y hace una PRUEBA REAL de si la wallet puede ejecutar el
   cobro ella sola (eth_call al adaptador de parlays 0xa120…00af con el calldata
   redeem(address[],uint256[]) — sel 0x53d190cf — reproducido byte a byte contra
   un cobro real). RESULTADO DE ESA PRUEBA (11-sep-2026): REVERT. Polymarket
   restringe redeem() a su propia cuenta ERC-4337 (0xac9930b2…5294), que es quien
   cobra las ganadoras vía EntryPoint handleOps; ni la proxy wallet ni una EOA
   pueden llamarlo, y no hay endpoint público de redeem de combos. Por eso el bot
   NO ejecuta el cobro: /reclamar dice exactamente cuánto hay pendiente y dónde
   cobrarlo (Portfolio → Positions → Claim). La prueba se cachea 24h y, si algún
   día deja de revertir, /reclamar lo anuncia (el calldata ya está listo).
   La auto-curación llama al detector y avisa sólo de reclamos NUEVOS.
   v12.8 (RPC): polygon-rpc.com devuelve 401 Unauthorized desde el 11-sep-2026 y
   era el PRIMERO de RPCS_POLYGON ⇒ cada eth_call gastaba un intento en un RPC
   muerto. Lista nueva y comprobada en vivo: publicnode → drpc → 1rpc.
   v12.7: AUTO-CURACIÓN — la re-auditoría ya NO hace falta pedirla: corre sola
   ~25s después de cada arranque y después cada 4h (AUDITORIA_CADA_H), dentro
   del lock de pasada para no pisar el AUTO. Reabre las ops archivadas que
   siguen en juego, corrige resultado/PnL contra la verdad real (cobros REDEEM
   + ganador por OUTCOME de cada leg), cierra las abiertas ya resueltas y deja
   intactos los cierres manuales 🔒. Sólo avisa por Telegram cuando cambia algo
   (🩺 AUTO-CURACIÓN). /reauditar sigue disponible para hacerlo a mano y con
   detalle (incluye el saldo on-chain de los tokens).
   v12.6: RESULTADOS REALES EN ✅ CERRADAS — arreglado el bug que archivaba
   combos como PERDIDOS antes de tiempo y con cifras que no casaban con
   Polymarket. Causa raíz: el catálogo /v1/rfq/combo-markets devuelve
   position_ids que NO son los token_id del CLOB (son otro espacio de ids,
   pares consecutivos), así que la comparación "nuestro token == token
   ganador" NUNCA acertaba: en cuanto una leg cerraba, el combo entero se
   archivaba como pérdida (pnl = -stake). Ahora:
     · El ganador de cada leg se lee por OUTCOME (nombre de la cara) y, si la
       op antigua no lo guarda, por el ÍNDICE 0 (el bot compra la primera cara,
       igual que position_ids[0]). Las ops nuevas guardan su outcome.
     · Un mercado closed SIN ganador declarado (resolución UMA pendiente)
       cuenta como ⏳ PENDIENTE, nunca como pérdida.
     · Manda la VERDAD de Polymarket: los cobros REDEEM reales de la wallet
       (data-api /activity, usdcSize>0 = ganado y cobrado) y el saldo on-chain
       del token de combo en su ERC1155 0x006f…efef (NO el CTF).
     · Nuevo 🩺 /reauditar: re-audita las archivadas, REABRE las que siguen en
       juego y corrige resultado/PnL de las mal cerradas (con copia previa).
       /reauditar seco = sólo informa.
   v12.5: REINTENTO ANTE SIZE_TOO_LARGE — si el maker del RFQ responde
   SIZE_TOO_LARGE (no cubre ese tamaño), el bot reintenta UNA única vez con el
   stake mínimo ($5) siempre que el pedido inicial fuera mayor; si ya iba al
   mínimo, no reintenta. Se avisa por Telegram (🔁) y queda en el log. NO se
   aplica al cierre (SELL): vender menos dejaría la posición a medias.
   v12.4: CÓDIGO PIN FIJO ELEGIDO POR EL USER — el código de 4 cifras que
   confirma los topes ≥10 ops/día ya NO se genera aleatoriamente: es el que
   fijó el user (constante PIN_FIJO_OPS). Se teclea SIEMPRE con el teclado
   numérico que saca el bot al elegir 10/20/30/50 en 🔢 Máx ops/día (o
   escribiendo las 4 cifras). Override sin tocar código: env POLY_PIN_OPS.
   El archivo antiguo /opt/polymarket/codigo_pin.txt queda SIN efecto (se
   puede borrar). El PIN NUNCA se escribe en el log (el log se publica).
   v12.3: (1) AUTO SOLO CON PROBABILIDAD SUFICIENTE — cada candidato se
   mide por su probabilidad (producto de legs); si no llega al nivel elegido
   se DESCARTA y se pasa al siguiente. Niveles: alta ≥65% · media-alta ≥60%
   (por defecto, elegida por el user) · media+ ≥50%; botón 🎯 Prob AUTO.
   (2) 📂 ABIERTAS con el ESTADO A LA DERECHA de cada línea: ✅ verde si ya
   terminó y salió positiva, ❌ roja si se perdió, ⏳ si sigue en juego.
   (3) 🔒 CERRAR POSICIÓN REAL — botón por posición: combos vía RFQ con
   direction=SELL (orden Exchange v3 side=1), simples vía orden CLOB SELL.
   /testcerrar pide la cotización de venta SIN aceptarla (coste $0).
   v12.2: STAKE DINÁMICO $5-10 — el bot decide la apuesta según la CUOTA y
   CÓMO VA LA COMBINADA: cuota más baja ⇒ más stake, y la ventaja REAL del
   RFQ sobre los legs lo ajusta (si el RFQ no mejora el mercado ≥0.5%, AUTO
   no apuesta); botones 💵 Stake AUTO/$5.
   🔢 MÁX OPERACIONES/DÍA (5/10/20/30/50): desde 10 exige el CÓDIGO PIN de
   4 cifras FIJO del user (teclado numérico que saca el bot; también vale
   escribirlo; se puede ver con 👁). El tope cuenta TODAS las ops del día
   (AUTO 🤖 + manuales 🚀/💥).
   v12.1: 📂 ABIERTAS SIN DUPLICADOS — los fills repetidos de la misma
   apuesta/conjunta se agrupan en UNA línea (×N, stake y shares totales);
   títulos ENTEROS (sin cortar); y por cada posición: PRECIO ACTUAL en
   vivo (midpoint CLOB, cache 60s), probabilidad ahora, valor vs pago y
   recomendación (💰 cerrar anticipado / 🟢 mantener / 🔴 muy caída).

FIX v10.9 (el SDK usa HTTPX, no requests):
  · inyectar_proxy_sdk() reemplaza helpers._http_client del SDK por un
    httpx.Client con proxy → TODAS las llamadas del SDK salen por el PC
  · enviar_orden() usa create_and_post_order() NATIVO del SDK (patrón
    bot de Elon): el SDK construye el envelope v2 {"order":..,"owner":..,
    "orderType":..} y firma headers L2 (POLY_SIGNATURE HMAC con creds
    derivadas). El POST manual v10.6-10.8 enviaba cuerpo+headers mal.

ARCHIVOS:
  · /root/poly_combos_token.txt       - Token Telegram
  · /opt/polymarket/combos_estado.json - Estado + historial
  · /etc/polymarket.env               - Credenciales Polymarket
"""
import os
import sys
import json
import time
import shutil
import base64
import random
import hashlib
import re as _re
import itertools
import subprocess
import urllib.request
import urllib.parse
import threading
import ssl
from datetime import datetime, timezone
from collections import defaultdict

LOG = []
def log(s):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {s}"
    print(line, flush=True)
    LOG.append(line)

# Anti-shadow
try:
    import importlib.util as _ilu
    _ilu.find_spec("copy")
except: pass


# ============================================
# CONFIGURACIÓN
# ============================================
TELEGRAM_TOKEN = None
WALLET = "0xb0e1197098e6d427c01720f1631cad24ce740fa0"
HOST_CLOB = "https://clob.polymarket.com"
COMBOS_API = "https://combos-rfq-api.polymarket.com"
PROXY_URL = "http://100.83.57.99:8888"

ESTADO_FILE = "/opt/polymarket/combos_estado.json"
BACKUP_FILE = "/opt/polymarket/combos_estado.bak.json"
ENV_FILE = "/etc/polymarket.env"

# ============================================
# ESTRATEGIA v7 — Mercados activos
# ============================================
STAKE_POR_TRADE = 5.0
MIN_SHARES = 5.0  # CLOB pide minimo 5 shares por orden
CUOTA_MIN = 1.20
CUOTA_MAX = 2.50

# ---- v11.0: combos reales via RFQ (Requester API) ----
RFQ_GATEWAY = "https://combos-rfq-gateway-requester-api.polymarket.com"
RFQ_BASE = "/v1/requester/rfq"
EXCHANGE_V3 = "0xe3333700cA9d93003F00f0F71f8515005F6c00Aa"
DATA_API = "https://data-api.polymarket.com"
# v12.6: FUENTES DE VERDAD del resultado real (cobros REDEEM + saldo on-chain)
PARLAY_ERC1155 = "0x006f54f7f9a22e0000cc2ab60031000000ae9fef"  # posiciones de COMBO (no es el CTF)
CTF_ERC1155 = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"     # v12.8.1: mercados SIMPLES
COBROS_PAGINAS = 2                     # v12.8.1: páginas de /activity?type=REDEEM (histórico completo)
COBRO_TITULO_VENTANA_D = 21            # días tras la op en los que un cobro por título es creíble
# v12.8: 💰 RECLAMAR — cobro (redeem) de parlays
PARLAY_REDEEM_ADAPTER = "0xa1200000d0002264c9a1698e001292d00e1b00af"   # adaptador redeem()
REDEEM_SEL = "53d190cf"                    # redeem(address[] owners, uint256[] tokenIds)
OPERADOR_REDEEM_4337 = "0xac9930b2ae455a671b62de86876a7e8587825294"    # única cuenta que hoy puede llamarlo
RECLAMO_PREFLIGHT_H = 24.0                 # horas entre pruebas de "¿puedo redimir yo sola?"
RECLAMO_MAX_LISTA = 12                     # combos que se detallan en el mensaje
GAMMA_API = "https://gamma-api.polymarket.com"
# v12.8: polygon-rpc.com da 401 Unauthorized (11-sep-2026) y era el primero;
# lista reordenada y comprobada en vivo (publicnode y drpc ~0.1s, 1rpc de respaldo)
RPCS_POLYGON = ("https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org",
                "https://1rpc.io/matic")
OUTCOME_NUESTRO = ("yes", "true", "up")   # caras que equivalen a "la nuestra"
LEGS_POR_COMBO = (2, 3)    # combinar 2 legs (preferido) o 3
# ---- v11.9: franja EXTENDIDA 🚀 (aprobada por user: techo 3.0, 2/día) ----
CUOTA_MAX_EXT = 3.0        # techo de cuota ESTIMADA extendida
CUOTA_REAL_MAX_EXT = 3.2   # techo de cuota REAL aceptable en extendidos
LEG_P_MIN_EXT = 0.70       # probabilidad mínima de CADA leg en extendidos
MAX_EXT_DIA = 2            # combos extendidos máximos por día
# ---- v12.0: franja SÚPER 💥 (manual, informativa, cuentas aparte) ----
SUPER_CUOTA_MIN = 5.0      # cuota estimada mínima de un súper combo
SUPER_CUOTA_MAX = 15.0     # techo (por debajo, probabilidad ~7%)
SUPER_LEGS = (3, 5)        # 3-5 legs (con 3 legs p≥0.60 no llega a 5)
SUPER_P_MIN = 0.55         # probabilidad mínima por leg en súper
SUPER_POOL_N = 20          # top-N legs por volumen para generar súper
SUPER_REAL_MIN = 3.5       # cuota REAL mínima aceptable en súper
SUPER_REAL_MAX = 18.0      # cuota REAL máxima aceptable en súper
MAX_SUPER_DIA = 2          # súper combos máximos por día
LEG_PRICE_MIN = 0.60       # yes_price mínimo por leg
LEG_PRICE_MAX = 0.96       # yes_price máximo por leg
LEG_VOL_MIN = 20000        # volumen mínimo ($) por leg
POOL_TOP_N = 30            # considerar top-N legs por volumen
MAX_COMBOS_DIA = 6         # tope de combos por día UTC
COOLDOWN_LEG_H = 6.0       # horas sin reutilizar un leg ya operado
RFQ_TIMEOUT_FILL_S = 45    # espera de FILLED tras aceptar
# v12.8.4: SEMI de verdad + filtro de ventaja
PROPUESTA_VALIDA_S = 600   # lo que vive una propuesta 🟡 SEMI antes de caducar
VENTAJA_MIN_EV = 0.05      # exige prob × cuota_real ≥ 1.05 (5% de ventaja real)
MAX_TRADES_SIMULTANEOS = 3
INTERVALO_AUTO_S = 300
NEXT_PASADA_TS = 0.0   # v11.1: próxima pasada programada (epoch); 0 = ya
PASADA_LOCK = threading.Lock()   # v11.3: una pasada a la vez
# v12.7: AUTO-CURACIÓN (re-auditoría sola)
AUDITORIA_CADA_H = 4.0                       # horas entre auditorías automáticas
AUDITORIA_CADA_S = int(AUDITORIA_CADA_H * 3600)
AUDITORIA_ARRANQUE_S = 25                    # 1ª auditoría tras arrancar
AUDITORIA_MIN_ENTRE_S = 600                  # no repetir si ya corrió hace <10 min
AUDITORIA_DIAS_MAX = 45                      # sólo ops de los últimos N días
NEXT_AUDITORIA_TS = time.time() + AUDITORIA_ARRANQUE_S
AUDITORIA_LOCK = threading.Lock()            # una auditoría a la vez
PESO_MIN = 5
MAX_MERCADOS_A_REVISAR = 100  # limita para no saturar

MODO_OPERACION = "AUTO"
CHAT_ID = None
ULTIMO_TRADE_TS = 0

# Categorias de mercados que nos interesan (deportes)
DEPORTES_KEYWORDS = {
    # Deportes con sus titulos comunes
    "MLB": ["mlb", "yankees", "dodgers", "astros", "mets", "giants",
            "nationals", "cardinals", "padres", "braves", "cubs",
            "red sox", "rangers", "tigers", "guardians", "royals",
            "mariners", "angels", "athletics", "orioles", "rays",
            "blue jays", "twins", "white sox", "brewers", "reds",
            "pirates", "rockies", "diamondbacks", "marlins", "phillies"],
    "UFC": ["ufc", "mma", "fight night", "knockout", "submission",
            "featherweight", "lightweight", "heavyweight", "middleweight",
            "welterweight", "bantamweight", "flyweight"],
    "NFL": ["nfl", "quarterback", "touchdown", "super bowl", "chiefs",
            "cowboys", "eagles", "packers", "ravens", "bills",
            "49ers", "lions", "dolphins", "jets", "texans", "colts",
            "jaguars", "titans", "broncos", "raiders", "chargers",
            "browns", "bengals", "steelers", "saints", "falcons",
            "panthers", "bears", "vikings", "cardinals", "buccaneers",
            "rams", "seahawks", "commanders"],
    "NBA": ["nba", "lakers", "celtics", "warriors", "bulls", "heat",
            "knicks", "nets", "bucks", "76ers", "raptors", "nuggets",
            "suns", "mavericks", "clippers", "rockets", "spurs",
            "thunder", "trail blazers", "jazz", "kings", "pacers",
            "hawks", "hornets", "pistons", "magic", "cavaliers",
            "timberwolves", "grizzlies", "pelicans"],
    "Tennis": ["tennis", "atp", "wta", "us open", "wimbledon",
               "french open", "australian open", "roland garros",
               "djokovic", "alcaraz", "sinner", "medvedev", "zverev",
               "swiatek", "sabalenka", "rybakina", "gael monfils",
               "federer", "nadal"],
    "Soccer": ["soccer", "epl", "premier league", "la liga", "bundesliga",
               "serie a", "ligue 1", "champions league", "europa league",
               "world cup", "uefa", "real madrid", "barcelona", "atletico",
               "manchester", "liverpool", "chelsea", "arsenal", "tottenham",
               "bayern", "dortmund", "psg", "juventus", "milan", "inter",
               "napoli", "roma", "ajax"],
    "NCAAF": ["ncaaf", "college football", "alabama", "georgia", "lsu",
              "michigan", "ohio state", "texas", "oklahoma", "notre dame",
              "usc", "oregon"],
    "NCAAB": ["ncaab", "march madness", "kansas", "duke", "kentucky",
              "north carolina", "villanova", "uconn"],
}

EXCLUIR_KEYWORDS = ["xi jinping", "trump", "biden", "election", "president",
                    "congress", "senate", "democratic", "republican", "governor",
                    "bitcoin", "ethereum", "crypto", "nft", "fed",
                    "russia", "ukraine", "china", "iran", "israel", "who",
                    "nobel", "oscar", "grammy", "emmy", "box office",
                    "movie", "film", "album", "song", "taylor swift", "kanye"]


# ============================================
# TELEGRAM
# ============================================
def cargar_token():
    global TELEGRAM_TOKEN
    paths = ["/root/poly_combos_token.txt", os.path.expanduser("~/poly_combos_token.txt")]
    for p in paths:
        if os.path.exists(p):
            t = open(p).read().strip()
            if ":" in t and len(t) > 20:
                TELEGRAM_TOKEN = t
                return True
    return False

def telegram_api(method, params=None):
    if not TELEGRAM_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        if params:
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(url, data=data)
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"telegram_api error: {e}")
        return None


# ============================================
# PROXY
# ============================================
_proxy_ctx = None
def _proxy_opener():
    global _proxy_ctx
    if _proxy_ctx is None:
        _proxy_ctx = ssl.create_default_context()
        _proxy_ctx.check_hostname = False
        _proxy_ctx.verify_mode = ssl.CERT_NONE
    proxy_handler = urllib.request.ProxyHandler({
        "http": PROXY_URL, "https": PROXY_URL,
    })
    https_handler = urllib.request.HTTPSHandler(context=_proxy_ctx)
    return urllib.request.build_opener(proxy_handler, https_handler)

def http_get(url, timeout=20, headers=None):
    try:
        opener = _proxy_opener()
        hdrs = {"User-Agent": "Mozilla/5.0"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, headers=hdrs)
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode('utf-8', errors='replace')
        except Exception:
            return e.code, str(e)
    except Exception as e:
        return None, str(e)

def http_post(url, data, headers=None, timeout=30):
    """POST con proxy. data es string (JSON ya serializado)."""
    try:
        opener = _proxy_opener()
        hdrs = {"User-Agent": "Mozilla/5.0"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data,
                                     headers=hdrs, method="POST")
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
    except Exception as e:
        return None, str(e)


# ============================================
# TECLADO FIJO
# ============================================
INTERVALOS_MIN = (5, 10, 20, 30, 60)   # v12.8.3: sube aquí (el ✅ lo necesita)
TICK_ACTIVO = " ✅"                     # v12.8.3: tick verde del botón ACTIVO


def intervalo_min_actual():
    """v12.8.3: minutos del intervalo activo, o None si no es uno de los botones
    (p. ej. un /intervalo a mano con un valor raro). Sirve para pintar el ✅."""
    try:
        m = int(round(INTERVALO_AUTO_S / 60))
    except Exception:
        return None
    return m if m in INTERVALOS_MIN else None


def teclado_fijo():
    """✅ v12.8.3: teclado DINÁMICO. El botón ⏱ del intervalo activo y el del MODO
    activo salen con un tick verde al final ("⏱ 10m ✅", "🟡 SEMI ✅") para ver de
    un golpe cada cuánto lee el bot y en qué modo está;
    los demás van sin tick. Se reconstruye en CADA mensaje porque Telegram sólo
    refresca un teclado cuando llega uno nuevo, así que el tick se mueve solo al
    cambiar el intervalo o el modo. El tick va AL FINAL para que los handlers
    sigan casando: el de ⏱ por startswith y los de modo vía _sin_tick() (v12.8.4).
    Añade el botón 🔍 Leer ahora."""
    act = intervalo_min_actual()
    fila_int = [{"text": f"⏱ {m}m" + (TICK_ACTIVO if act == m else "")}
                for m in INTERVALOS_MIN]
    # v12.8.4: también el MODO activo lleva su ✅ (🟢 AUTO ✅ / 🟡 SEMI ✅ / 🔴 OFF ✅)
    _modo_txt = {"AUTO": "🟢 AUTO", "SEMI": "🟡 SEMI", "OFF": "🔴 OFF"}.get(
        str(MODO_OPERACION or "").upper())
    fila_modo = [{"text": t + (TICK_ACTIVO if t == _modo_txt else "")}
                 for t in ("🟢 AUTO", "🟡 SEMI", "🔴 OFF")]
    return {
        "keyboard": [
            [{"text": "📋 Trades"}, {"text": "💰 Saldo"}, {"text": "📂 Abiertas"}],
            [{"text": "💥 SúperCombos"}, {"text": "💰 Reclamar"},
             {"text": "📡 Copy"}],
            [{"text": "✅ Cerradas"}, {"text": "📊 Stats"}, {"text": "🏆 Top"}],
            fila_modo,
            [{"text": "💵 Stake AUTO"}, {"text": "💵 Stake $5"}],
            [{"text": "🔢 Máx ops/día"}, {"text": "🎯 Prob AUTO"}],
            fila_int,
            [{"text": "🔍 Leer ahora"}],
        ],
        "resize_keyboard": True,
        "persistent": True,
    }


TECLADO_FIJO = teclado_fijo()      # v12.8.3: compatibilidad (ya no es estático)

def enviar(chat_id, texto, reply_markup=None):
    params = {"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"}
    if reply_markup is None:
        # v12.8.3: teclado dinámico (el botón ⏱ activo lleva ✅)
        params["reply_markup"] = json.dumps(teclado_fijo())
    else:
        params["reply_markup"] = json.dumps(reply_markup)
    return telegram_api("sendMessage", params)


# ============================================
# CREDENCIALES
# ============================================
def cargar_env():
    env = {}
    if not os.path.exists(ENV_FILE):
        return env
    with open(ENV_FILE) as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            k, v = linea.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def get_clob_client():
    """Replica el patrón del bot de Elon: crea el cliente simple
    con las env vars de proxy. Confia en que py_clob_client_v2
    respeta HTTP_PROXY/HTTPS_PROXY."""
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds
        from py_clob_client_v2 import SignatureTypeV2
    except ImportError:
        log("  py_clob_client_v2 no instalado")
        return None
    env = cargar_env()
    signer = env.get("POLY_PRIVATE_KEY", "").strip()
    if not signer:
        log("  sin POLY_PRIVATE_KEY")
        return None
    # v10.9: inyectar proxy en el cliente httpx del SDK (no basta el env)
    inyectar_proxy_sdk()

    kwargs = {}
    if env.get("POLY_API_KEY") and env.get("POLY_API_SECRET") and env.get("POLY_API_PASSPHRASE"):
        kwargs["creds"] = ApiCreds(env["POLY_API_KEY"], env["POLY_API_SECRET"],
                                   env["POLY_API_PASSPHRASE"])
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET).strip()
    if wallet:
        kwargs["funder"] = wallet
    kwargs["signature_type"] = int(SignatureTypeV2.POLY_PROXY) if wallet else int(SignatureTypeV2.EOA)
    try:
        client = ClobClient(HOST_CLOB, chain_id=137, key=signer, **kwargs)
        if "creds" not in kwargs:
            try:
                creds = client.derive_api_key()
                client.set_api_creds(creds)
            except: pass
        return client
    except Exception as e:
        log(f"cliente error: {e}")
        return None


def inyectar_proxy_sdk(proxy_url=None):
    """v10.9: fuerza que py_clob_client_v2 salga por el proxy del PC.

    CLAVE: el SDK usa HTTPX (no requests). Su cliente se crea A NIVEL DE
    MODULO al importar:  helpers._http_client = httpx.Client(http2=True)
    → setear env vars despues de importar NO afecta al cliente ya creado,
    y los monkey-patch de v10.2-10.4 parcheaban requests (libreria que el
    SDK no usa). Aqui reemplazamos _http_client EXPLICITAMENTE por uno con
    proxy, cubriendo varias versiones de httpx. Devuelve True si OK."""
    proxy_url = proxy_url or PROXY_URL
    if not proxy_url:
        return False
    # env vars tambien (por si algo re-importa/crea clientes nuevos)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
              "http_proxy", "https_proxy", "all_proxy"):
        os.environ[k] = proxy_url
    try:
        import httpx
        from py_clob_client_v2.http_helpers import helpers as _hh
        ultimo_err = None
        for kwargs in (
            {"http2": True, "proxy": proxy_url},                   # httpx >= 0.26
            {"http2": True, "proxies": {"all://": proxy_url}},     # httpx 0.23-0.25
            {"http2": True, "proxies": proxy_url},                 # httpx antiguos
            {"proxy": proxy_url},                                  # sin paquete h2
            {"proxies": {"all://": proxy_url}},
        ):
            try:
                _hh._http_client = httpx.Client(**kwargs)
                return True
            except (TypeError, ImportError) as e:
                ultimo_err = e
                continue
        log(f"  · aviso: proxy SDK no inyectado ({str(ultimo_err)[:80]})")
        return False
    except Exception as e:
        log(f"  · aviso: proxy SDK fallo ({str(e)[:80]})")
        return False


# ============================================
# v11.0 — COMBOS REALES via RFQ (Requester API)
# ============================================
# Flujo oficial (docs.polymarket.com/trading/combos/requesters):
#   1. POST {gateway}/v1/requester/rfq/requests   (leg_position_ids + notional)
#      → subasta entre market makers (400ms) → mejor quote (blended_price_e6)
#   2. Firmar orden Exchange v3 (EIP-712, contrato 0xe333...00Aa,
#      tokenId = yes_position_id del combo, maker = proxy wallet, signer = EOA,
#      signatureType=1 POLY_PROXY, builder/metadata = bytes32 cero)
#   3. POST .../requests/{rfq_id}/accept  (ventana ~5s desde el quote)
#   4. GET  .../requests/{rfq_id}  → poll hasta FILLED (tx_hash) / FAILED
# Headers L2 en cada petición: POLY_ADDRESS (EOA signer), POLY_API_KEY,
# POLY_PASSPHRASE, POLY_TIMESTAMP, POLY_SIGNATURE (HMAC-SHA256 del secret
# derivado sobre ts+METHOD+path+body_exacto, base64url).
_IDENTIDAD_RFQ = None
_CLOB_CLIENT_RMQ = None   # cliente CLOB cacheado (para /balance-allowance)

def obtener_identidad_rfq(forzar=False):
    """(creds CLOB derivadas, direccion EOA signer, proxy wallet, private key).
    Cacheado por proceso. Todo via proxy (httpx del SDK inyectado)."""
    global _IDENTIDAD_RFQ
    if _IDENTIDAD_RFQ is not None and not forzar:
        return _IDENTIDAD_RFQ
    env = cargar_env()
    pk = env.get("POLY_PRIVATE_KEY", "").strip()
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET).strip()
    if not pk:
        log("  RFQ: sin POLY_PRIVATE_KEY")
        return None
    if not inyectar_proxy_sdk():
        log("  RFQ: aviso, proxy SDK no inyectado")
    from py_clob_client_v2.client import ClobClient
    from py_clob_client_v2 import SignatureTypeV2
    from eth_account import Account
    client = ClobClient(host=HOST_CLOB, chain_id=137, key=pk, funder=wallet,
                        signature_type=int(SignatureTypeV2.POLY_PROXY))
    creds = client.derive_api_key()
    client.set_api_creds(creds)
    signer_addr = Account.from_key(pk).address
    global _CLOB_CLIENT_RMQ
    _CLOB_CLIENT_RMQ = client
    _IDENTIDAD_RFQ = (creds, signer_addr, wallet, pk)
    log(f"  RFQ: identidad lista (signer {signer_addr[:10]}... maker {wallet[:10]}...)")
    return _IDENTIDAD_RFQ


def saldo_disponible_clob():
    """Colateral (pUSD, 6 decimales) visible por el CLOB via /balance-allowance.
    None si no se pudo consultar (en ese caso NO se bloquea el trade)."""
    global _CLOB_CLIENT_RMQ
    if _CLOB_CLIENT_RMQ is None:
        if not obtener_identidad_rfq():
            return None
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        r = _CLOB_CLIENT_RMQ.get_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        if isinstance(r, dict) and r.get("balance") is not None:
            return int(r["balance"]) / 1e6
    except Exception as e:
        log(f"  balance-allowance error: {str(e)[:120]}")
    return None


def l2_headers_rfq(method, path, body_str, creds, signer_addr):
    """Headers L2 para el gateway RFQ (mismo esquema HMAC que el CLOB)."""
    from py_clob_client_v2.signing.hmac import build_hmac_signature
    ts = str(int(time.time()))
    sig = build_hmac_signature(creds.api_secret, ts, method.upper(), path, body_str)
    return {
        "Content-Type": "application/json",
        "POLY_ADDRESS": signer_addr,
        "POLY_SIGNATURE": sig,
        "POLY_TIMESTAMP": ts,
        "POLY_API_KEY": creds.api_key,
        "POLY_PASSPHRASE": creds.api_passphrase,
    }


def crear_rfq(leg_position_ids, notional_usd, identidad, direction="BUY"):
    """v12.3: direction='SELL' pide cotización para VENDER el combo (cerrar)."""
    creds, signer_addr, wallet, pk = identidad
    body = {
        "signer_address": signer_addr,
        "maker_address": wallet,
        "signature_type": 1,
        "leg_position_ids": [str(x) for x in leg_position_ids],
        "direction": direction,
        "side": "YES",
        "requested_size": {"unit": "notional",
                           "value_e6": str(int(round(notional_usd * 1000000)))},
    }
    body_str = json.dumps(body, separators=(",", ":"))
    path = f"{RFQ_BASE}/requests"
    headers = l2_headers_rfq("POST", path, body_str, creds, signer_addr)
    return http_post(RFQ_GATEWAY + path, body_str, headers, timeout=20)


def firmar_orden_v3(req, quote, identidad, side=0):
    """Firma EIP-712 de la orden Exchange v3 para aceptar el quote.
    v12.3: side=0 COMPRA (BUY) · side=1 VENTA (SELL, para cerrar posición)."""
    creds, signer_addr, wallet, pk = identidad
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    msg = {
        "salt": str(random.randint(1, 2**249)),
        "maker": wallet,
        "signer": signer_addr,
        "tokenId": str(req.get("yes_position_id")),
        "makerAmount": str(quote.get("maker_amount_e6")),
        "takerAmount": str(quote.get("taker_amount_e6")),
        "side": side,
        "signatureType": 1,
        "timestamp": str(int(time.time())),
        "metadata": "0x" + "00" * 32,
        "builder": "0x" + "00" * 32,
    }
    typed = {
        "domain": {"name": "Polymarket CTF Exchange", "version": "3",
                   "chainId": 137, "verifyingContract": EXCHANGE_V3},
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Order": [
                {"name": "salt", "type": "uint256"},
                {"name": "maker", "type": "address"},
                {"name": "signer", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
                {"name": "makerAmount", "type": "uint256"},
                {"name": "takerAmount", "type": "uint256"},
                {"name": "side", "type": "uint8"},
                {"name": "signatureType", "type": "uint8"},
                {"name": "timestamp", "type": "uint256"},
                {"name": "metadata", "type": "bytes32"},
                {"name": "builder", "type": "bytes32"},
            ],
        },
        "primaryType": "Order",
        "message": {**msg,
                    "salt": int(msg["salt"]),
                    "tokenId": int(msg["tokenId"]),
                    "makerAmount": int(msg["makerAmount"]),
                    "takerAmount": int(msg["takerAmount"]),
                    "timestamp": int(msg["timestamp"])},
    }
    acct = Account.from_key(pk)
    firmado = acct.sign_message(encode_typed_data(full_message=typed))
    sig = bytes(firmado.signature)
    if sig[64] in (0, 1):           # normalizar v a 27/28
        sig = sig[:64] + bytes([sig[64] + 27])
    msg["signature"] = "0x" + sig.hex()
    return msg


def aceptar_rfq(rfq_id, quote_id, signed_order, identidad):
    creds, signer_addr, wallet, pk = identidad
    body = {"quote_id": str(quote_id), "signed_order": signed_order}
    body_str = json.dumps(body, separators=(",", ":"))
    path = f"{RFQ_BASE}/requests/{rfq_id}/accept"
    headers = l2_headers_rfq("POST", path, body_str, creds, signer_addr)
    return http_post(RFQ_GATEWAY + path, body_str, headers, timeout=20)


def consultar_rfq(rfq_id, identidad):
    creds, signer_addr, wallet, pk = identidad
    path = f"{RFQ_BASE}/requests/{rfq_id}"
    headers = l2_headers_rfq("GET", path, None, creds, signer_addr)
    return http_get(RFQ_GATEWAY + path, timeout=15, headers=headers)


def esperar_fill(rfq_id, identidad, timeout_s=RFQ_TIMEOUT_FILL_S):
    """Poll del estado del RFQ. FILLED/CONFIRMED = éxito; FAILED/EXPIRED/
    CANCELED = terminal; timeout local NO es fallo (seguir consultando luego)."""
    fin = time.time() + timeout_s
    ultimo = {}
    while time.time() < fin:
        status, resp = consultar_rfq(rfq_id, identidad)
        try:
            ultimo = json.loads(resp)
        except Exception:
            ultimo = {"status": f"http_{status}"}
        st = ultimo.get("status", "")
        if st in ("FILLED", "CONFIRMED"):
            return st, ultimo
        if st in ("FAILED", "EXPIRED", "CANCELED"):
            return st, ultimo
        time.sleep(3)
    return ultimo.get("status") or "TIMEOUT_LOCAL", ultimo


# ---- seleccion de legs y deduplicacion ----

def evento_de(slug):
    """Clave de evento: slug hasta la fecha incluida (mlb-laa-bos-2026-09-07-total-8pt5
    y mlb-laa-bos-2026-09-07 son el MISMO evento → no combinar, correlacionados)."""
    m = _re.match(r"^(.*?\d{4}-\d{2}-\d{2})", slug or "")
    if m:
        return m.group(1)
    partes = (slug or "").split("-")
    return "-".join(partes[:-1]) if len(partes) > 1 else (slug or "")


def fecha_slug_ok(slug):
    """Descarta legs con fecha pasada en el slug (partidos ya jugados)."""
    m = _re.search(r"(\d{4}-\d{2}-\d{2})", slug or "")
    if not m:
        return True
    try:
        d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except Exception:
        return True
    return d >= datetime.now(timezone.utc).date()


def huella_combo(pids):
    return hashlib.sha1("|".join(sorted(str(x) for x in pids)).encode()).hexdigest()[:16]


def leg_reciente(estado, pid):
    ts = estado.get("combos_rfq", {}).get("legs", {}).get(str(pid))
    if not ts:
        return False
    try:
        t = datetime.fromisoformat(ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600.0 < COOLDOWN_LEG_H


def franja_of(op):
    """v12.0: franja de una operación — 'base' | 'extendida' | 'super'.
    Compatible con registros antiguos (campo 'extendida' o sin franja)."""
    f = op.get("franja")
    if f in ("base", "extendida", "super"):
        return f
    if op.get("super"):
        return "super"
    if op.get("extendida"):
        return "extendida"
    return "base"


def combos_hoy_count(estado):
    """v12.0: SOLO franja base — las manuales 🚀/💥 no consumen el tope AUTO."""
    hoy = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for r in estado.get("combos_rfq", {}).get("historial", [])
               if str(r.get("fecha", "")).startswith(hoy) and franja_of(r) == "base")


def extendidas_hoy_count(estado):
    """v11.9: extendidos de hoy que consumieron dinero (filled/pendiente)."""
    hoy = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for r in estado.get("combos_rfq", {}).get("historial", [])
               if franja_of(r) == "extendida" and str(r.get("fecha", "")).startswith(hoy)
               and r.get("status") in ("filled", "pendiente"))


def supers_hoy_count(estado):
    """v12.0: súper combos de hoy que consumieron dinero."""
    hoy = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for r in estado.get("combos_rfq", {}).get("historial", [])
               if franja_of(r) == "super" and str(r.get("fecha", "")).startswith(hoy)
               and r.get("status") in ("filled", "pendiente"))


def generar_combos_catalogo(legs, max_combos=10):
    """v11.7: candidatos INFORMATIVOS de combos reales (2-3 legs, eventos
    distintos, cuota estimada en rango) por volumen mín. desc.
    Sin estado: no aplica cooldown/huellas/tope (solo catálogo)."""
    pool = []
    for c in legs:
        p = c.get("yes_price") or 0
        if not (LEG_PRICE_MIN <= p <= LEG_PRICE_MAX):
            continue
        if (c.get("volumen") or 0) < LEG_VOL_MIN:
            continue
        if c.get("pending"):
            continue
        if not fecha_slug_ok(c.get("slug")):
            continue
        pool.append(c)
    pool.sort(key=lambda x: -(x.get("volumen") or 0))
    pool = pool[:POOL_TOP_N]
    candidatos = []
    for n in range(LEGS_POR_COMBO[0], LEGS_POR_COMBO[1] + 1):
        if n > len(pool):
            break
        for sel in itertools.combinations(pool, n):
            eventos = {evento_de(c.get("slug")) for c in sel}
            if len(eventos) != n:
                continue
            prod = 1.0
            for c in sel:
                prod *= c.get("yes_price") or 0
            cuota = round(1 / prod, 2) if prod > 0 else 0
            vol_min = min(c.get("volumen") or 0 for c in sel)
            if CUOTA_MIN <= cuota <= CUOTA_MAX:
                candidatos.append((vol_min, cuota, list(sel), "base"))
            elif (CUOTA_MAX < cuota <= CUOTA_MAX_EXT
                  and all((c.get("yes_price") or 0) >= LEG_P_MIN_EXT for c in sel)):
                candidatos.append((vol_min, cuota, list(sel), "extendida"))   # v11.9 🚀
    candidatos.sort(key=lambda x: -x[0])
    return candidatos[:max_combos]


FRANJA_ICO = {"base": "", "extendida": "🚀 ", "super": "💥 "}


def generar_super_catalogo(legs, max_combos=10):
    """v12.0: SÚPER combos 💥 (cuota est. [5,15], 3-5 legs, p ≥0.55 c/u,
    eventos distintos) por volumen mín. desc. Solo informativos + botón manual."""
    pool = []
    for c in legs:
        pr = c.get("yes_price") or 0
        if not (SUPER_P_MIN <= pr <= LEG_PRICE_MAX):
            continue
        if (c.get("volumen") or 0) < LEG_VOL_MIN:
            continue
        if c.get("pending"):
            continue
        if not fecha_slug_ok(c.get("slug")):
            continue
        if not c.get("yes_token"):
            continue
        pool.append(c)
    pool.sort(key=lambda x: -(x.get("volumen") or 0))
    pool = pool[:SUPER_POOL_N]
    candidatos = []
    for n in range(SUPER_LEGS[0], SUPER_LEGS[1] + 1):
        if n > len(pool):
            break
        for sel in itertools.combinations(pool, n):
            eventos = {evento_de(c.get("slug")) for c in sel}
            if len(eventos) != n:
                continue
            prod = 1.0
            for c in sel:
                prod *= c.get("yes_price") or 0
            cuota = round(1 / prod, 2) if prod > 0 else 0
            if not (SUPER_CUOTA_MIN <= cuota <= SUPER_CUOTA_MAX):
                continue
            vol_min = min(c.get("volumen") or 0 for c in sel)
            candidatos.append((vol_min, cuota, list(sel), "super"))
    candidatos.sort(key=lambda x: -x[0])
    return candidatos[:max_combos]


def enviar_catalogo(chat_id, cands, prefijo, cabecera, cierre=None):
    """v12.0: UN mensaje por combo con SU botón ▶️ debajo (Telegram no permite
    intercalar botones entre líneas de un mismo mensaje)."""
    enviar(chat_id, cabecera)
    for i, (vol, cuota, sel, franja) in enumerate(cands, 1):
        prod = 1.0
        for c in sel:
            prod *= float(c.get("yes_price") or 0)
        ico = FRANJA_ICO.get(franja, "")
        texto = (f"{i}. {ico}🎫 cuota ~{cuota:.2f} · 💵 ${vol:,.0f}\n"
                 f"🎯 prob ~{prod * 100:.0f}% — {etiqueta_prob(prod)}\n")
        for c in sel:
            texto += f"· {str(c['question'])[:54]} (p={c.get('yes_price', 0):.2f})\n"
        h8 = hash8_sel(sel)
        CATALOGO_CACHE[h8] = (time.time(), sel, franja)
        _stq = stake_txt()
        boton = {"inline_keyboard": [[
            {"text": f"▶️ {ico}#{i} · {_stq} · cuota ~{cuota:.2f}",
             "callback_data": f"{prefijo}:{i}:{h8}"}]]}
        enviar(chat_id, texto, boton)
    _prune_catalogo()
    if cierre:
        enviar(chat_id, cierre)


CATALOGO_CACHE = {}   # v11.8: hash8 -> (ts, sel) para los botones ▶️


def hash8_sel(sel):
    pids = sorted(str(c.get("yes_token")) for c in sel)
    return hashlib.sha1("|".join(pids).encode()).hexdigest()[:8]


def etiqueta_prob(p):
    """Etiqueta cualitativa: a más cuota, menos probabilidad."""
    if p >= PROB_ALTA:
        return "alta 🟢"
    if p >= PROB_MEDIA_ALTA:
        return "media-alta 🟢"
    if p >= PROB_MEDIA:
        return "media 🟡"
    return "baja 🔴"


def _prune_catalogo():
    global CATALOGO_CACHE
    ahora = time.time()
    CATALOGO_CACHE = {k: v for k, v in CATALOGO_CACHE.items() if ahora - v[0] < 3600}
    if len(CATALOGO_CACHE) > 60:
        viejas = sorted(CATALOGO_CACHE, key=lambda k: CATALOGO_CACHE[k][0])
        for k in viejas[:len(CATALOGO_CACHE) - 60]:
            CATALOGO_CACHE.pop(k, None)


# ============================================
# v12.2: STAKE DINÁMICO ($5-$10) + TOPE DIARIO CONFIGURABLE (PIN ≥10)
# ============================================
STAKE_MIN_AUTO = 5.0    # suelo del stake dinámico (petición user: $5-$10)
STAKE_MAX_AUTO = 10.0   # techo del stake dinámico
STAKE_KELLY_PCT = 25.0  # % de la ventaja (edge) que se suma al stake base
OPS_MAX_VALORES = (5, 10, 20, 30, 50)   # topes diarios elegibles
OPS_PIN_DESDE = 10      # desde este tope se exige código de 4 cifras
PIN_ARCHIVO = "/opt/polymarket/codigo_pin.txt"   # v12.2: ya SIN efecto (v12.4)
PIN_FIJO_OPS = "0667"   # v12.4: código de 4 cifras ELEGIDO POR EL USER
STAKE_MODE = "AUTO"     # "AUTO" = dinámico $5-10 | "FIJO" = STAKE_POR_TRADE
MAX_OPS_DIA = MAX_COMBOS_DIA   # tope diario vigente (persistido en estado)
PIN_ESPERA = None       # {"max": int, "digits": str} mientras se teclea el PIN

def stake_para(cuota_real, cuota_est, manual=False):
    """v12.2: stake DINÁMICO entre $5 y $10 según CUOTA y CÓMO VA LA COMBINADA.
    base por cuota: 1.2→$10 (techo) · 2.0→$8 · 2.5→$7.4 · 5→$6.2 · 10→$5.6.
    ventaja real = precio implícito de los legs (1/cuota_est) menos el precio
    REAL del RFQ (1/cuota_real): si el maker mejora el mercado, se suma
    (25% de la ventaja); si el RFQ sale ≥0.5% PEOR que comprar los legs por
    separado, AUTO devuelve 0.0 = NO apostar (un botón manual siempre opera,
    con el suelo $5)."""
    try:
        cr = float(cuota_real or 0)
        ce = float(cuota_est or 0)
    except Exception:
        cr, ce = 0.0, 0.0
    if cr <= 1 or ce <= 1:
        return STAKE_MIN_AUTO if manual else 0.0
    edge = (1.0 / ce) - (1.0 / cr)
    if edge < -0.005 and not manual:
        return 0.0                      # RFQ peor que el mercado → AUTO pasa
    base = 5.0 + 6.0 / cr
    stake = round(base + edge * STAKE_KELLY_PCT, 2)
    return min(max(stake, STAKE_MIN_AUTO), STAKE_MAX_AUTO)

def max_ops(estado=None):
    """v12.2: tope diario vigente (5/10/20/30/50, persistido)."""
    if estado is None:
        estado = cargar_estado()
    try:
        m = int(estado.get("max_ops_dia", MAX_OPS_DIA) or MAX_OPS_DIA)
    except Exception:
        m = MAX_OPS_DIA
    return m if m in OPS_MAX_VALORES else MAX_COMBOS_DIA

def ops_pagadas_hoy(estado):
    """v12.2: operaciones de hoy que han costado dinero (filled/pendiente),
    TODAS las franjas: el tope diario cuenta AUTO + manuales 🚀/💥."""
    hoy = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for r in estado.get("combos_rfq", {}).get("historial", [])
               if str(r.get("fecha", "")).startswith(hoy)
               and r.get("status") in ("filled", "pendiente"))

def codigo_pin():
    """v12.4: código de 4 cifras para confirmar topes ≥10 ops/día. Es el
    FIJO elegido por el user (PIN_FIJO_OPS) — ya no se genera aleatoriamente
    ni se lee/escribe PIN_ARCHIVO (ese archivo de la v12.2 queda sin efecto;
    se puede borrar del servidor). Se puede cambiar sin tocar el código con
    la variable de entorno POLY_PIN_OPS (4 cifras), que tiene prioridad.
    IMPORTANTE: no escribir NUNCA el código en el log (el log se publica en
    diag-public)."""
    tok = os.environ.get("POLY_PIN_OPS", "").strip()
    if tok.isdigit() and len(tok) == 4:
        return tok
    return PIN_FIJO_OPS

def set_stake_mode(modo):
    global STAKE_MODE
    STAKE_MODE = "AUTO" if str(modo).upper().startswith("A") else "FIJO"

def stake_txt(estado=None):
    """Texto del stake vigente para paneles/mensajes."""
    if estado is None:
        estado = cargar_estado()
    if str(estado.get("stake_mode", "AUTO")).upper() == "AUTO":
        return f"AUTO ${STAKE_MIN_AUTO:.0f}-${STAKE_MAX_AUTO:.0f} (según cuota/ventaja)"
    try:
        _sf = float(estado.get("stake", STAKE_POR_TRADE) or STAKE_POR_TRADE)
    except Exception:
        _sf = float(STAKE_POR_TRADE)
    return f"FIJO ${_sf:.2f}"

def stake_operacion(estado, cuota_real, cuota_est, manual=False):
    """Stake final de una operación: FIJO si el user lo fijó; AUTO dinámico."""
    if str(estado.get("stake_mode", "AUTO")).upper() != "AUTO":
        try:
            return float(estado.get("stake", STAKE_POR_TRADE) or STAKE_POR_TRADE)
        except Exception:
            return float(STAKE_POR_TRADE)
    return stake_para(cuota_real, cuota_est, manual=manual)

def set_max_ops_dia(chat_id, valor, pendiente=False):
    """v12.2: guarda el tope diario. Con pendiente=True exige el PIN de 4
    cifras antes (topes ≥10): abre el teclado numérico y espera el código."""
    global PIN_ESPERA, MAX_OPS_DIA
    try:
        v = int(valor)
    except Exception:
        return enviar(chat_id, "❌ Topes disponibles: 5, 10, 20, 30 o 50 operaciones/día")
    if v not in OPS_MAX_VALORES:
        return enviar(chat_id, "❌ Topes disponibles: 5, 10, 20, 30 o 50 operaciones/día")
    if pendiente:
        PIN_ESPERA = {"max": v, "digits": ""}
        return None
    MAX_OPS_DIA = v
    PIN_ESPERA = None
    estado = cargar_estado()
    estado["max_ops_dia"] = v
    guardar_estado(estado)
    hoy = ops_pagadas_hoy(estado)
    log(f"max ops/día -> {v}")
    pinnota = ""
    if v >= OPS_PIN_DESDE:
        pinnota = "\n🔐 Confirmado con código de 4 cifras"
    return enviar(chat_id, f"🔢 *Máximo {v} operaciones/día*{pinnota}\n"
                           f"Hoy ya hay {hoy} operación(es) pagadas.\n"
                           f"Cuenta TODO: AUTO 🤖 + manuales 🚀/💥")

def max_combos_menu(chat_id):
    """🔢 Menú del tope diario: botones 5/10/20/30/50 (desde 10, con PIN)."""
    estado = cargar_estado()
    m = max_ops(estado)
    hoy = ops_pagadas_hoy(estado)
    kb = []
    fila = []
    for v in OPS_MAX_VALORES:
        mark = "✅ " if v == m else ""
        fila.append({"text": f"{mark}{v}/día", "callback_data": f"mx:{v}"})
    kb.append(fila)
    kb.append([{"text": "👁 Ver código", "callback_data": "mxp:v"},
               {"text": "❌ Cerrar", "callback_data": "mxp:x"}])
    txt = (f"🔢 *MÁXIMO DE OPERACIONES/DÍA*\n\n"
           f"Ahora: *{m}/día* · hoy ya hay *{hoy}* pagadas (AUTO 🤖 + manuales 🚀/💥)\n"
           f"Para *{OPS_PIN_DESDE} o más* hay que confirmar con un *código de 4 cifras* 🔐\n"
           f"_(es tu código fijo de 4 cifras; se ve aquí con 👁 y se teclea con el teclado numérico)_")
    return enviar(chat_id, txt, {"inline_keyboard": kb})

def pin_menu(chat_id):
    """Teclado numérico de 4 cifras para confirmar topes ≥10."""
    global PIN_ESPERA
    if not isinstance(PIN_ESPERA, dict):
        return enviar(chat_id, "❌ Primero elige el tope (10/20/30/50) en 🔢 Máx ops/día")
    kb = [[{"text": str(d), "callback_data": f"pn:{d}"} for d in (1, 2, 3)],
          [{"text": str(d), "callback_data": f"pn:{d}"} for d in (4, 5, 6)],
          [{"text": str(d), "callback_data": f"pn:{d}"} for d in (7, 8, 9)],
          [{"text": "👁 Código", "callback_data": "pn:v"}, {"text": "0", "callback_data": "pn:0"},
           {"text": "⌫ Borrar", "callback_data": "pn:b"}],
          [{"text": "❌ Cancelar", "callback_data": "pn:x"}]]
    d = PIN_ESPERA.get("digits", "")
    return enviar(chat_id, f"🔐 *CÓDIGO DE 4 CIFRAS* — para *{PIN_ESPERA.get('max')}/día*\n"
                           f"Llevas: `{d or '· · · ·'}` ({len(d)}/4)\n_Tecla las 4 cifras del código_",
                  {"inline_keyboard": kb})

def pin_tecla(chat_id, d):
    """Procesa una tecla del PIN: dígitos, borrar, ver código, cancelar."""
    global PIN_ESPERA
    if not isinstance(PIN_ESPERA, dict):
        return enviar(chat_id, "❌ No hay ningún código pendiente")
    if d == "x":
        mx = PIN_ESPERA.get("max")
        PIN_ESPERA = None
        return enviar(chat_id, f"❌ Cancelado — el tope sigue en {max_ops(cargar_estado())}/día (no se cambió a {mx})")
    if d == "v":
        return enviar(chat_id, f"👁 Tu código de 4 cifras: `{codigo_pin()}`\n_Tecléalo con los botones numéricos_")
    if d == "b":
        PIN_ESPERA["digits"] = str(PIN_ESPERA.get("digits", ""))[:-1]
        return pin_menu(chat_id)
    if not str(d).isdigit():
        return
    digs = str(PIN_ESPERA.get("digits", "")) + str(d)
    if len(digs) < 4:
        PIN_ESPERA["digits"] = digs
        return pin_menu(chat_id)
    mx = PIN_ESPERA.get("max")
    if digs == codigo_pin():
        return set_max_ops_dia(chat_id, mx, pendiente=False)
    PIN_ESPERA["digits"] = ""
    return enviar(chat_id, "❌ *Código incorrecto* — el máximo NO se ha cambiado.\n"
                           "Intenta otra vez (👁 para ver el código) o ❌ Cancelar en 🔢 Máx ops/día")

def stake_menu(chat_id):
    """💵 Menú de stake: AUTO $5-10 (decide el bot) o FIJO manual."""
    estado = cargar_estado()
    modo = str(estado.get("stake_mode", "AUTO")).upper()
    kb = [[{"text": ("✅ " if modo == "AUTO" else "") + f"AUTO ${STAKE_MIN_AUTO:.0f}-${STAKE_MAX_AUTO:.0f}",
            "callback_data": "st:auto"},
           {"text": ("✅ " if modo != "AUTO" else "") + f"FIJO ${STAKE_POR_TRADE:.0f}",
            "callback_data": "st:fijo"}]]
    txt = (f"💵 *STAKE POR OPERACIÓN*\n\nAhora: *{stake_txt(estado)}*\n\n"
           f"*AUTO ${STAKE_MIN_AUTO:.0f}-{STAKE_MAX_AUTO:.0f}* — decide el bot según la *cuota* y *cómo va la combinada*: "
           f"cuota más baja ⇒ más stake (1.2⇒${STAKE_MAX_AUTO:.0f} · 2.0⇒$8 · 2.5⇒$7.4 · 5⇒$6.2), "
           f"y la ventaja REAL del RFQ sobre los legs lo ajusta; si el RFQ no mejora el mercado, AUTO no apuesta ($0).\n"
           f"*FIJO ${STAKE_POR_TRADE:.2f}* — siempre igual (cámbialo con /stake 7).")
    return enviar(chat_id, txt, {"inline_keyboard": kb})


# ============================================
# v12.3: NIVEL DE PROBABILIDAD PARA AUTO + CIERRE REAL DE POSICIONES
# ============================================
PROB_ALTA = 0.65        # etiqueta "alta 🟢"
PROB_MEDIA_ALTA = 0.60  # nivel por defecto de AUTO (elección del user)
PROB_MEDIA = 0.50       # etiqueta "media 🟡"
PROB_NIVELES = (PROB_ALTA, PROB_MEDIA_ALTA, PROB_MEDIA)
PROB_MIN_AUTO = PROB_MEDIA_ALTA   # global vigente (persistido en estado)
ABIERTAS_CACHE = {}     # h8 -> (ts, clave_grupo) para los botones 🔒

def prob_nivel_txt(p):
    """Nombre del nivel de probabilidad."""
    if p >= PROB_ALTA:
        return f"alta 🟢 ≥{int(PROB_ALTA * 100)}%"
    if p >= PROB_MEDIA_ALTA:
        return f"media-alta 🟢 ≥{int(PROB_MEDIA_ALTA * 100)}%"
    return f"media+ 🟡 ≥{int(PROB_MEDIA * 100)}%"

def prob_min_auto(estado=None):
    """v12.3: probabilidad mínima que AUTO exige al combo entero."""
    if estado is None:
        estado = cargar_estado()
    try:
        v = float(estado.get("prob_min_auto", PROB_MIN_AUTO))
    except Exception:
        v = PROB_MIN_AUTO
    if v not in PROB_NIVELES:
        return PROB_MEDIA_ALTA
    return v

def set_prob_min_auto(chat_id, tanto_por_ciento):
    """Fija el nivel de probabilidad de AUTO (65 / 60 / 50)."""
    global PROB_MIN_AUTO
    try:
        pct = int(tanto_por_ciento)
    except Exception:
        return enviar(chat_id, "❌ Niveles: 65 (alta), 60 (media-alta) o 50 (media+)")
    val = pct / 100.0
    if val not in PROB_NIVELES:
        return enviar(chat_id, "❌ Niveles: 65 (alta), 60 (media-alta) o 50 (media+)")
    PROB_MIN_AUTO = val
    estado = cargar_estado()
    estado["prob_min_auto"] = val
    guardar_estado(estado)
    cuota_top = round(1 / val, 2)
    log(f"prob AUTO -> {prob_nivel_txt(val)}")
    return enviar(chat_id, f"🎯 *AUTO solo con probabilidad {prob_nivel_txt(val)}*\n"
                           f"Cuota máxima equivalente: *{cuota_top}* (prob = 1/cuota)\n"
                           f"Los candidatos que no lleguen se descartan y se pasa al siguiente.")

def prob_menu(chat_id):
    """🎯 Menú del nivel de probabilidad exigido a AUTO."""
    estado = cargar_estado()
    actual = prob_min_auto(estado)
    kb = []
    for v in PROB_NIVELES:
        pct = int(round(v * 100))
        mark = "✅ " if v == actual else ""
        kb.append([{"text": f"{mark}{prob_nivel_txt(v)} · cuota ≤{1 / v:.2f}",
                    "callback_data": f"pb:{pct}"}])
    kb.append([{"text": "❌ Cerrar", "callback_data": "pb:x"}])
    txt = (f"🎯 *PROBABILIDAD MÍNIMA PARA AUTO*\n\n"
           f"Ahora: *{prob_nivel_txt(actual)}*\n\n"
           f"AUTO solo ejecuta combos cuya probabilidad (producto de sus legs) llegue al nivel. "
           f"Si no llega, *se descarta y se pasa al siguiente* candidato.\n"
           f"_Probabilidad y cuota son dos caras de lo mismo: prob = 1/cuota. "
           f"Exigir ≥65% limita la cuota a ≤1.54; ≥60% a ≤1.67; ≥50% a ≤2.00._\n"
           f"🚀 Extendidas y 💥 Súper siguen siendo manuales (sin este filtro).")
    return enviar(chat_id, txt, {"inline_keyboard": kb})


def seleccionar_combo(legs, estado):
    """v12.0: elige la mejor combinación SOLO DE FRANJA BASE (la automática):
    2-3 legs, eventos distintos, cuota est. [CUOTA_MIN, CUOTA_MAX], prefiriendo
    2 legs. Las franjas 🚀 extendida y 💥 súper son MANUALES (botones) y no
    se eligen aquí."""
    _mx = max_ops(estado)
    if ops_pagadas_hoy(estado) >= _mx:
        log(f"  tope diario alcanzado ({ops_pagadas_hoy(estado)}/{_mx} ops)")
        return None
    pool = []
    for c in legs:
        p = c.get("yes_price") or 0
        if not (LEG_PRICE_MIN <= p <= LEG_PRICE_MAX):
            continue
        if (c.get("volumen") or 0) < LEG_VOL_MIN:
            continue
        if c.get("pending"):
            continue
        if not fecha_slug_ok(c.get("slug")):
            continue
        if not c.get("yes_token"):
            continue
        if leg_reciente(estado, c.get("yes_token")):
            continue
        pool.append(c)
    pool.sort(key=lambda x: -(x.get("volumen") or 0))
    pool = pool[:POOL_TOP_N]
    huellas = estado.get("combos_rfq", {}).get("huellas", {})
    _pmin = prob_min_auto(estado)          # v12.3: solo probabilidad suficiente
    descartados_prob = 0
    base = []
    for n in range(LEGS_POR_COMBO[0], LEGS_POR_COMBO[1] + 1):
        if n > len(pool):
            break
        for sel in itertools.combinations(pool, n):
            eventos = {evento_de(c.get("slug")) for c in sel}
            if len(eventos) != n:
                continue
            pids = [str(c["yes_token"]) for c in sel]
            if huella_combo(pids) in huellas:
                continue
            prod = 1.0
            for c in sel:
                prod *= c.get("yes_price") or 0
            cuota = round(1 / prod, 2) if prod > 0 else 0
            if not (CUOTA_MIN <= cuota <= CUOTA_MAX):
                continue
            # v12.3: probabilidad insuficiente -> se descarta y se pasa al siguiente
            if prod < _pmin:
                descartados_prob += 1
                continue
            vol_min = min(c.get("volumen") or 0 for c in sel)
            base.append((vol_min, cuota, list(sel)))
    def _mejor(lst):
        lst = sorted(lst, key=lambda x: -x[0])
        return lst[0] if lst else None
    m2 = _mejor([c for c in base if len(c[2]) == 2])   # preferir 2 legs
    if m2:
        return m2[2]
    m3 = _mejor([c for c in base if len(c[2]) == 3])
    if m3:
        return m3[2]
    if descartados_prob:
        log(f"  {descartados_prob} candidato(s) descartados por probabilidad < {prob_nivel_txt(_pmin)}")
    return None


def reservar_combo(pids):
    """v11.3: marca la huella y los legs COMO OPERADOS antes de crear el RFQ,
    para que ninguna otra pasada (ni un reintento) elija el mismo combo
    mientras este intento está en vuelo."""
    estado = cargar_estado()
    rfq = estado.setdefault("combos_rfq", {"huellas": {}, "legs": {}, "historial": []})
    ahora = datetime.now(timezone.utc).isoformat()
    rfq.setdefault("huellas", {})[huella_combo(pids)] = ahora
    legs = rfq.setdefault("legs", {})
    for pid in pids:
        legs[str(pid)] = ahora
    guardar_estado(estado)


def liberar_combo(pids):
    """v11.3: deshace la reserva si el intento falló de forma terminal
    (para que el combo pueda reintentarse en pasadas futuras)."""
    estado = cargar_estado()
    rfq = estado.get("combos_rfq", {})
    rfq.get("huellas", {}).pop(huella_combo(pids), None)
    legs = rfq.get("legs", {})
    for pid in pids:
        legs.pop(str(pid), None)
    guardar_estado(estado)


def programar_paso(ts):
    """v11.4: fija NEXT_PASADA_TS y lo PERSISTE (proximo_paso_ts) para que
    reinicios/despliegues respeten el horario en vez de empezar a 0."""
    global NEXT_PASADA_TS
    NEXT_PASADA_TS = ts
    try:
        estado = cargar_estado()
        estado["proximo_paso_ts"] = ts
        guardar_estado(estado)
    except Exception:
        pass


def restaurar_modo(estado=None):
    """🟡 v12.8.4: al arrancar recupera el MODO guardado (AUTO/SEMI/OFF).
    main() NO lo leía: el bot volvía SIEMPRE en AUTO aunque hubieras pulsado
    🟡 SEMI, así que cualquier reinicio, despliegue o caída te devolvía al
    automático sin avisar (buena parte de por qué "el SEMI no funcionaba")."""
    global MODO_OPERACION
    try:
        est = estado if estado is not None else cargar_estado()
        md = str(est.get("modo") or "").upper()
    except Exception:
        md = ""
    if md in ("AUTO", "SEMI", "OFF"):
        MODO_OPERACION = md
        log(f"  modo restaurado del estado: {md}")
    else:
        log(f"  modo sin guardar en el estado → sigo en {MODO_OPERACION}")
    return MODO_OPERACION


def restaurar_horario():
    """v11.4: al arrancar, recupera chat_id y la próxima pasada programada.
    Si el horario caducó o no existe → now + intervalo (NUNCA inmediata)."""
    global CHAT_ID, NEXT_PASADA_TS
    estado = cargar_estado()
    cid = estado.get("chat_id")
    if cid:
        CHAT_ID = cid
    ts = estado.get("proximo_paso_ts") or 0
    try:
        ts = float(ts)
    except Exception:
        ts = 0.0
    if ts > time.time():
        NEXT_PASADA_TS = ts
        log(f"  horario restaurado: próxima pasada en {int((ts - time.time()) // 60)} min")
    else:
        NEXT_PASADA_TS = time.time() + INTERVALO_AUTO_S
        log(f"  horario inicial: próxima pasada en {INTERVALO_AUTO_S // 60} min")
    return NEXT_PASADA_TS


def programar_pasada_ahora():
    """v11.3: pide una pasada inmediata SIN lanzar un hilo paralelo: el
    auto_loop (único ejecutor) la recoge en ≤5s vía NEXT_PASADA_TS."""
    global NEXT_PASADA_TS
    if NEXT_PASADA_TS > time.time():
        NEXT_PASADA_TS = time.time()


def ejecutar_combo_rfq(sel, chat_id=None, dry_run=False, franja="base", stake=None, manual=False):
    """Flujo RFQ completo: crear → validar cuota real → firmar v3 → aceptar
    → esperar FILLED → registrar + notificar. dry_run=True NO acepta (gratis).
    franja (v12.0): 'base' | 'extendida' 🚀 | 'super' 💥 — cada una con su
    ventana de cuota real y su etiquetado en estado/estadísticas.
    stake (v12.2): None = lo decide el bot — inicial según la cuota est.,
    definitivo tras la cotización con la cuota REAL y la ventaja (AUTO
    $5-10; omitido si el RFQ no mejora el mercado); un número fuerza ese
    stake exacto. manual=True (botón ▶️) siempre opera, mínimo $5."""
    pids = [str(c["yes_token"]) for c in sel]
    titulo = " + ".join((c.get("question") or "")[:38] for c in sel)
    prod = 1.0
    for c in sel:
        prod *= c.get("yes_price") or 0
    cuota_est = round(1 / prod, 2) if prod > 0 else 0
    # v12.2: stake DINÁMICO $5-10 — inicial según la cuota (para pedir el
    # quote); tras la cotización se reajusta con la cuota REAL y la ventaja
    _est_st = cargar_estado()
    _auto = str(_est_st.get("stake_mode", "AUTO")).upper() == "AUTO"
    _stake_forzado = stake is not None
    if stake is None:
        if _auto:
            stake = round(min(max(5.0 + 6.0 / cuota_est, STAKE_MIN_AUTO), STAKE_MAX_AUTO), 2) if cuota_est > 1 else STAKE_MIN_AUTO
        else:
            stake = stake_operacion(_est_st, cuota_est, cuota_est)
    log(f"[COMBO] {len(sel)} legs · cuota est. {cuota_est} · stake ${stake} ({'AUTO' if _auto else 'FIJO'})")
    for c in sel:
        log(f"  · {(c.get('question') or '')[:56]} (p={c.get('yes_price'):.2f} vol=${(c.get('volumen') or 0)/1000:.0f}k)")
    if chat_id:
        enviar(chat_id, f"🎰 *COMBO {len(sel)} LEGS* (cuota est. ~{cuota_est})\n" +
               "\n".join(f"· {(c.get('question') or '')[:55]} (p={c.get('yes_price'):.2f})" for c in sel))
    reservar_combo(pids)   # v11.3: anti-duplicidad (antes de cualquier red)
    identidad = obtener_identidad_rfq()
    if not identidad:
        liberar_combo(pids)
        return False, "sin_identidad"
    status, resp = crear_rfq(pids, stake, identidad)
    log(f"  RFQ create -> {status} {str(resp)[:160]}")
    try:
        d = json.loads(resp)
    except Exception:
        d = {}
    # v12.5: SIZE_TOO_LARGE = el maker no cubre ese tamaño. REINTENTO ÚNICO con
    # el stake mínimo ($5) si el pedido era mayor; si ya íbamos al mínimo, no se
    # reintenta (volvería a fallar). Solo en APERTURA: en la rama de CIERRE (SELL)
    # no se reintenta con menos porque vendería solo una parte de la posición y
    # dejaría el resto colgando (mejor avisar y que el user decida).
    _e0 = d.get("error") if isinstance(d, dict) else None
    _cod0 = (_e0.get("code") if isinstance(_e0, dict) else str(_e0 or "")) or ""
    if _cod0 == "SIZE_TOO_LARGE" and float(stake or 0) > STAKE_MIN_AUTO + 0.001:
        _stake_prev = float(stake)
        stake = STAKE_MIN_AUTO
        log(f"  ⚠️ RFQ SIZE_TOO_LARGE con ${_stake_prev:.2f} -> reintento único con ${stake:.2f} (suelo)")
        if chat_id:
            enviar(chat_id, f"🔁 *El RFQ rechazó el tamaño* (${_stake_prev:.2f})\n"
                            f"Reintento único con ${stake:.2f} (mínimo)…")
        status, resp = crear_rfq(pids, stake, identidad)
        log(f"  RFQ create (reintento) -> {status} {str(resp)[:160]}")
        try:
            d = json.loads(resp)
        except Exception:
            d = {}
    if status != 200 or not isinstance(d, dict) or not d:
        liberar_combo(pids)
        return False, f"rfq_http_{status}:{str(resp)[:150]}"
    err = d.get("error")
    if d.get("status") == "FAILED" or err:
        liberar_combo(pids)
        code = err.get("code") if isinstance(err, dict) else str(err)
        return False, f"rfq_{code or 'failed'}"
    quote = d.get("quote") or {}
    req = d.get("request") or {}
    rfq_id = d.get("rfq_id")
    quote_id = quote.get("quote_id")
    try:
        blended = int(quote.get("blended_price_e6", 0)) / 1e6
        shares = int(quote.get("net_receive_e6", 0)) / 1e6
        total_req = int(quote.get("total_required_e6", 0)) / 1e6
    except Exception:
        liberar_combo(pids)
        return False, f"quote_ilegible:{str(quote)[:120]}"
    cuota_real = round(1 / blended, 2) if blended > 0 else 0
    log(f"  quote: cuota={cuota_real} blended={blended:.3f} shares={shares:.2f} total=${total_req:.2f}")
    if dry_run:
        liberar_combo(pids)   # el test no debe bloquear el combo real
        log("  dry-run: quote OK, NO se acepta (expira solo, coste 0)")
        if chat_id:
            enviar(chat_id, f"🧪 *TEST COMBO OK*\n💱 Cuota real: *{cuota_real}* · {shares:.2f} shares · ${total_req:.2f}\nNo aceptado (coste $0). rfq_id `{str(rfq_id)[:18]}`")
        return True, {"dry_run": True, "cuota": cuota_real, "rfq_id": rfq_id}
    if franja == "super":
        min_real, max_real = SUPER_REAL_MIN, SUPER_REAL_MAX
    elif franja == "extendida":
        min_real, max_real = CUOTA_MIN, CUOTA_REAL_MAX_EXT
    else:
        min_real, max_real = CUOTA_MIN, CUOTA_MAX
    if not (min_real <= cuota_real <= max_real):
        banda = f"[{min_real}-{max_real}]" + {"base": "", "extendida": " 🚀", "super": " 💥"}.get(franja, "")
        log(f"  NO acepto: cuota real {cuota_real} fuera de {banda}")
        if chat_id:
            enviar(chat_id, f"⚠️ Cuota real {cuota_real} fuera de rango {banda} — quote NO aceptado ($0)")
        liberar_combo(pids)
        return False, f"cuota_real_{cuota_real}_fuera"
    # ⚖️ v12.8.4: FILTRO DE VENTAJA (esperanza positiva). prob = 1/cuota_est es el
    # precio implícito de los legs, así que EV = prob × cuota_real − 1. Exigimos
    # ≥5%: un RFQ que sólo iguala al mercado (EV≈0) no compensa. Los botones
    # manuales 🚀/💥 (manual=True) siguen operando siempre: los eliges tú.
    if not manual and cuota_est > 0:
        _ev = (cuota_real / cuota_est) - 1.0
        if _ev < VENTAJA_MIN_EV:
            liberar_combo(pids)
            log(f"  ⚖️ ventaja insuficiente: RFQ {cuota_real} vs mercado ~{cuota_est} "
                f"= EV {_ev * 100:+.1f}% < {VENTAJA_MIN_EV * 100:.0f}% exigidos — NO se acepta ($0)")
            if chat_id:
                enviar(chat_id, f"⚖️ *Combo omitido por falta de ventaja* ($0)\n"
                                f"Cuota real {cuota_real} vs mercado ~{cuota_est} = "
                                f"EV {_ev * 100:+.1f}% · se exigen ≥{VENTAJA_MIN_EV * 100:.0f}% "
                                f"(cuota ≥{cuota_est * (1 + VENTAJA_MIN_EV):.2f}).\n"
                                f"_Comprar algo que sólo empata es perder: no se acepta._")
            return False, f"ventaja_{_ev * 100:+.1f}_insuficiente"
    # v12.2: stake definitivo con la cuota REAL y la ventaja sobre los legs
    if _auto and not _stake_forzado:
        _nuevo = stake_para(cuota_real, cuota_est, manual=manual)
        if _nuevo <= 0:
            liberar_combo(pids)
            log(f"  stake AUTO 0: RFQ {cuota_real} sin ventaja vs legs (est {cuota_est}) — NO se acepta ($0)")
            if chat_id:
                enviar(chat_id, f"⏭ *Combo omitido* ($0)\nCuota real {cuota_real} vs legs ~{cuota_est}: el RFQ no mejora el mercado, no compensa apostar.")
            return False, "stake_auto_0_sin_margen"
        if abs(_nuevo - stake) > 0.005:
            log(f"  stake AUTO ajustado con cuota real: ${stake} -> ${_nuevo}")
        stake = _nuevo
    # v11.2: saldo CLOB antes de firmar (evita accepts que fallan por reserva)
    saldo = saldo_disponible_clob()
    if saldo is not None and saldo + 0.01 < total_req:
        liberar_combo(pids)
        log(f"  saldo CLOB insuficiente: {saldo:.2f} < {total_req:.2f}")
        if chat_id:
            enviar(chat_id, f"💸 *Saldo CLOB insuficiente*: ${saldo:.2f} disponibles < ${total_req:.2f} del quote. Se omite este combo.")
        return False, f"saldo_insuficiente_{saldo:.2f}"
    if saldo is not None:
        log(f"  saldo CLOB ok: ${saldo:.2f} >= ${total_req:.2f}" )
    # firmar + aceptar RÁPIDO (ventana ~5s)
    try:
        signed = firmar_orden_v3(req, quote, identidad)
    except Exception as e:
        liberar_combo(pids)
        log(f"  firma v3 error: {e}")
        return False, f"firma_v3:{str(e)[:150]}"
    status, resp = aceptar_rfq(rfq_id, quote_id, signed, identidad)
    log(f"  RFQ accept -> {status} {str(resp)[:160]}")
    # v11.2: fallo transitorio de reserva → reintento único (idempotente por rfq_id)
    try:
        da0 = json.loads(resp)
    except Exception:
        da0 = {}
    code0 = (da0.get("error") or {}).get("code") if isinstance(da0, dict) else None
    if status == 503 or code0 in ("PRE_EXECUTION_BALANCE_RESERVATION_FAILED",
                                  "SERVICE_UNAVAILABLE", "TRADE_SUBMISSION_FAILED"):
        log(f"  accept transitorio ({status}/{code0}): reintento único en 6s")
        time.sleep(6)
        status, resp = aceptar_rfq(rfq_id, quote_id, signed, identidad)
        log(f"  RFQ accept retry -> {status} {str(resp)[:160]}")
    if status != 200:
        liberar_combo(pids)
        return False, f"accept_http_{status}:{str(resp)[:150]}"
    try:
        da = json.loads(resp)
    except Exception:
        da = {}
    if isinstance(da, dict) and da.get("status") == "FAILED":
        liberar_combo(pids)
        err = da.get("error") or {}
        return False, f"accept_{err.get('code') if isinstance(err, dict) else err}"
    st, ultimo = esperar_fill(rfq_id, identidad)
    tx = ultimo.get("tx_hash", "") if isinstance(ultimo, dict) else ""
    log(f"  RFQ status final: {st} tx={str(tx)[:26]}")
    ok = st in ("FILLED", "CONFIRMED")
    pendiente = st in ("EXECUTING", "MINED", "RETRYING", "AWAITING_MAKER_CONFIRMATION", "TIMEOUT_LOCAL")
    if not ok and not pendiente:
        liberar_combo(pids)   # fallo terminal: el combo queda reintentable
    registro = {
        "tipo": "combo_rfq",
        "copiado_en": datetime.now(timezone.utc).isoformat(),
        "question": titulo,
        "n_legs": len(sel),
        "legs": [{"question": c.get("question"), "slug": c.get("slug"),
                  "yes_price": c.get("yes_price"), "position_id": str(c.get("yes_token")),
                  "condition_id": c.get("condition_id"),
                  "outcome": c.get("outcome")} for c in sel],   # v12.6: cara comprada
        "rfq_id": rfq_id,
        "quote_id": quote_id,
        "combo_condition_id": req.get("condition_id"),
        "combo_yes_position_id": req.get("yes_position_id"),
        "precio_ejecutado": blended,
        "cuota_ejecutada": cuota_real,
        "cuota_estimada": cuota_est,
        "size_shares": round(shares, 2),
        "stake_dolares": round(total_req, 2),
        "order_id": rfq_id,
        "tx_hash": tx,
        "status": "filled" if ok else ("pendiente" if pendiente else "fallido"),
        "estado_rfq": st,
        "slug": "", "market_id": "", "condition_id": req.get("condition_id", ""),
        "real_token": req.get("yes_position_id"),
        "volumen": min((c.get("volumen") or 0) for c in sel),
        "tags": ["combo-rfq"] + ([franja] if franja != "base" else []),
        "franja": franja,
        "extendida": franja == "extendida",
        "super": franja == "super",
    }
    estado = cargar_estado()
    rfq = estado.setdefault("combos_rfq", {"huellas": {}, "legs": {}, "historial": []})
    rfq.setdefault("huellas", {})
    rfq.setdefault("legs", {})
    rfq.setdefault("historial", [])
    ahora_iso = datetime.now(timezone.utc).isoformat()
    rfq["huellas"][huella_combo(pids)] = ahora_iso
    for pid in pids:
        rfq["legs"][pid] = ahora_iso
    rfq["historial"].append({"fecha": ahora_iso, "rfq_id": rfq_id, "status": registro["status"],
                             "cuota": cuota_real, "stake": registro["stake_dolares"],
                             "legs": titulo, "franja": franja,
                             "extendida": franja == "extendida"})
    estado.setdefault("trades_copiados", []).append(registro)
    guardar_estado(estado)
    if chat_id:
        if ok:
            mk_ll = {"base": "", "extendida": "🚀 EXTENDIDO ", "super": "💥 SÚPER "}.get(franja, "")
            enviar(chat_id, f"✅ *COMBO REAL LLENADO* {mk_ll}🎉\n📌 {titulo[:80]}\n"
                            f"💵 {shares:.2f} shares @ {blended:.3f} (cuota {cuota_real})\n"
                            f"💰 ${total_req:.2f}\n🔗 tx `{str(tx)[:24]}`")
        elif pendiente:
            enviar(chat_id, f"⏳ *COMBO ACEPTADO, esperando fill* ({st})\n📌 {titulo[:70]}\n"
                            f"Consulta /fills para confirmar (timeout local ≠ fallo)")
        else:
            enviar(chat_id, f"❌ *COMBO {st}*\n📌 {titulo[:70]}\nrfq `{str(rfq_id)[:18]}`")
    return ok, {"oid": rfq_id, "status": st, "cuota": cuota_real}


# v12.8.3: INTERVALOS_MIN se define arriba, junto al teclado (lo usa el ✅)

def cmd_intervalo(chat_id, texto):
    """⏱ Cambia el intervalo entre pasadas AUTO (botones del teclado fijo).
    Se persiste en combos_estado.json para sobrevivir reinicios."""
    global INTERVALO_AUTO_S, NEXT_PASADA_TS
    nums = "".join(ch for ch in texto if ch.isdigit())
    try:
        mins = int(nums)
    except Exception:
        return enviar(chat_id, "❌ Usa los botones ⏱ 5m/10m/20m/30m/60m")
    if mins not in INTERVALOS_MIN:
        return enviar(chat_id, f"❌ Intervalos disponibles: {', '.join(str(m) for m in INTERVALOS_MIN)} min")
    INTERVALO_AUTO_S = mins * 60
    programar_paso(time.time() + INTERVALO_AUTO_S)   # v11.4: persistido
    estado = cargar_estado()
    estado["intervalo_min"] = mins
    guardar_estado(estado)
    log(f"intervalo AUTO -> {mins} min")
    return enviar(chat_id, f"⏱ *Pasada cada {mins} min*\nPróxima lectura: ~{datetime.fromtimestamp(NEXT_PASADA_TS, tz=timezone.utc).strftime('%H:%M:%S')} UTC\n(guardado; sobrevive reinicios)\n✅ El botón *⏱ {mins}m* del teclado queda marcado como el activo")


def cmd_testcombo(chat_id):
    """🧪 RFQ completo SIN aceptar: valida el pipeline a coste cero."""
    def _run():
        try:
            legs = listar_combos()
            if not legs:
                return enviar(chat_id, "🧪 Sin legs disponibles ahora")
            sel = seleccionar_combo(legs, cargar_estado())
            if not sel:
                return enviar(chat_id, "🧪 No hay combos viables ahora (cuota/cooldown/tope diario/eventos)")
            ejecutar_combo_rfq(sel, chat_id, dry_run=True)
        except Exception as e:
            log(f"testcombo error: {e}")
            enviar(chat_id, f"🧪 Error: {str(e)[:150]}")
    threading.Thread(target=_run, daemon=True).start()
    return enviar(chat_id, "🧪 Pidiendo quote de un combo real (sin aceptar, $0)...")


def cmd_fills(chat_id):
    """🔎 Rellena estados pendientes de RFQ + reconcilia fills con data-api."""
    def _run():
        try:
            lineas = []
            estado = cargar_estado()
            cambiados = 0
            identidad = None
            for r in estado.get("trades_copiados", []):
                if r.get("tipo") == "combo_rfq" and r.get("status") == "pendiente" and r.get("rfq_id"):
                    if identidad is None:
                        identidad = obtener_identidad_rfq()
                    if not identidad:
                        break
                    st, ult = esperar_fill(r["rfq_id"], identidad, timeout_s=6)
                    if st in ("FILLED", "CONFIRMED", "FAILED", "EXPIRED", "CANCELED"):
                        r["status"] = "filled" if st in ("FILLED", "CONFIRMED") else "fallido"
                        r["estado_rfq"] = st
                        r["tx_hash"] = ult.get("tx_hash", r.get("tx_hash", ""))
                        cambiados += 1
            if cambiados:
                guardar_estado(estado)
                lineas.append(f"♻️ {cambiados} combo(s) pendiente(s) actualizado(s)")
            url = f"{DATA_API}/trades?user={WALLET}&limit=40"
            status, body = http_get(url, timeout=20)
            try:
                trades = json.loads(body) if status == 200 else []
            except Exception:
                trades = []
            grupos = {}
            for t in trades:
                ts = t.get("timestamp") or 0
                try:
                    dia = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
                except Exception:
                    dia = "?"
                k = (dia, (t.get("title") or "?")[:42])
                g = grupos.setdefault(k, {"n": 0, "usd": 0.0, "sh": 0.0})
                g["n"] += 1
                g["usd"] += float(t.get("size") or 0) * float(t.get("price") or 0)
                g["sh"] += float(t.get("size") or 0)
            ultimos = sorted(grupos.items(), key=lambda kv: kv[0][0], reverse=True)[:10]
            if ultimos:
                lineas.append("🔎 *Fills en la wallet (data-api)*")
                for (dia, tit), g in ultimos:
                    lineas.append(f"`{dia[5:]}` {tit} — {g['n']}x {g['sh']:.1f}sh ≈ ${g['usd']:.2f}")
            hoy = datetime.now(timezone.utc).date().isoformat()
            combos_h = [r for r in estado.get("combos_rfq", {}).get("historial", [])
                        if str(r.get("fecha", "")).startswith(hoy)]
            if combos_h:
                lineas.append(f"\n🎰 *Combos RFQ hoy*: {len(combos_h)}")
                for c in combos_h[-5:]:
                    lineas.append(f"· {c.get('status')} cuota {c.get('cuota')} ${c.get('stake')}")
            if not lineas:
                lineas = ["Sin fills encontrados"]
            enviar(chat_id, "\n".join(lineas))
        except Exception as e:
            log(f"fills error: {e}")
            enviar(chat_id, f"🔎 Error: {str(e)[:150]}")
    threading.Thread(target=_run, daemon=True).start()
    return enviar(chat_id, "🔎 Consultando fills...")


# ============================================
# MERCADOS ACTIVOS EN TIEMPO REAL
# ============================================
def detectar_deporte_por_titulo(titulo):
    """Detecta el deporte a partir del titulo del mercado."""
    t = titulo.lower()
    for deporte, kws in DEPORTES_KEYWORDS.items():
        if any(k in t for k in kws):
            return deporte
    return None

def listar_combos():
    """v11: el endpoint /v1/rfq/combo-markets devuelve el CATALOGO DE LEGS
    (mercados simples 'combinables'), NO combos formados. Cada entrada es una
    posible pata; los combos reales se construyen por RFQ (seccion v11)."""
    combos = []
    cursor = ""
    paginas = 0
    while paginas < 5:  # hasta 5 paginas
        url = f"{COMBOS_API}/v1/rfq/combo-markets?limit=50"
        if cursor:
            url += f"&cursor={urllib.parse.quote(cursor)}"
        status, body = http_get(url, timeout=15)
        if status != 200:
            log(f"  combo-markets status {status}")
            break
        try:
            data = json.loads(body)
        except:
            break
        batch = data.get("markets", [])
        if not batch:
            break
        for m in batch:
            titulo = m.get("title") or m.get("question") or ""
            tags = m.get("tags") or []
            slug = m.get("slug", "")
            # tags son listas: ["sports", "soccer", "games"]
            # Filtrar solo deportes
            tags_str = " ".join(tags).lower() if isinstance(tags, list) else str(tags).lower()
            es_deporte = any(t in tags_str for t in ["sport", "soccer", "football", "basketball",
                                                      "baseball", "tennis", "mma", "ufc",
                                                      "cricket", "esports", "nfl", "nba", "mlb",
                                                      "ncaaf", "ncaab", "wnba", "nhl", "fight"])
            if not es_deporte:
                continue
            # outcome_prices = [precio_yes, precio_no]
            try:
                prices = m.get("outcome_prices", [])
                if isinstance(prices, str):
                    prices = json.loads(prices)
            except:
                prices = []
            if not prices:
                continue
            try:
                yes_price = float(prices[0])
            except:
                continue
            if not (0.02 <= yes_price <= 0.97):
                continue
            # position_ids = [token_yes, token_no]
            try:
                tokens = m.get("position_ids", [])
                if isinstance(tokens, str):
                    tokens = json.loads(tokens)
            except:
                tokens = []
            # v12.6: nombres de las caras (MISMO ORDEN que los tokens del CLOB)
            try:
                outs = m.get("outcomes", [])
                if isinstance(outs, str):
                    outs = json.loads(outs)
            except:
                outs = []
            if not tokens or len(tokens) < 1:
                continue
            vol = float(m.get("volume") or 0)
            market_id = m.get("id", "")
            condition_id = m.get("condition_id", "")
            combos.append({
                "market_id": market_id,
                "condition_id": condition_id,
                "question": titulo,
                "slug": slug,
                "yes_token": str(tokens[0]),  # position_id del catálogo (NO es el token_id CLOB)
                "outcome": (str(outs[0]) if outs else "Yes"),   # v12.6: cara que compramos
                "no_token": str(tokens[1]) if len(tokens) > 1 else str(tokens[0]),
                "yes_price": yes_price,
                "cuota": round(1/yes_price, 2) if yes_price > 0 else 0,
                "volumen": vol,
                "pending": bool(m.get("pending")),
                "tags": tags,
                # Estos se llenan despues via /markets/{condition_id}
                "real_token": None,
            })
        log(f"  pagina {paginas + 1}: +{len(batch)} mercados, {len(combos)} legs de deportes")
        # siguiente pagina
        cursor = data.get("next_cursor", "")
        if not cursor:
            break
        paginas += 1
    combos.sort(key=lambda x: -x["volumen"])
    return combos


def listar_mercados_deportes():
    """[LEGACY v7] Lee mercados individuales. Mantenido como fallback."""
    return listar_combos()  # en v9 todo es combos

def get_precio_actual(token_id):
    try:
        url = f"{HOST_CLOB}/midpoint?token_id={token_id}"
        status, body = http_get(url, timeout=10)
        if status == 200:
            data = json.loads(body)
            mid = data.get("mid") or data.get("midpoint")
            if mid:
                return float(mid)
        url = f"{HOST_CLOB}/book?token_id={token_id}"
        status, body = http_get(url, timeout=10)
        if status == 200:
            data = json.loads(body)
            if data.get("asks"):
                return float(data["asks"][0]["price"])
            if data.get("bids"):
                return float(data["bids"][0]["price"])
    except: pass
    return None


def resolver_token_real(condition_id):
    """v10: dado el condition_id de un combo, devuelve el token_id real
    tradable en el CLOB. None si falla."""
    try:
        url = f"{HOST_CLOB}/markets/{condition_id}"
        status, body = http_get(url, timeout=10)
        if status != 200:
            return None
        data = json.loads(body)
        if not data.get("accepting_orders") or data.get("closed"):
            return None
        tokens = data.get("tokens", [])
        if not tokens:
            return None
        # tokens[0] = YES, tokens[1] = NO
        yes = tokens[0]
        return yes.get("token_id")
    except Exception as e:
        log(f"  resolver_token_real err: {e}")
        return None


# ============================================
# EJECUCIÓN DE TRADES
# ============================================
def enviar_orden(token_id, precio, stake_dolares):
    """v10.9: create_and_post_order() NATIVO del SDK (patrón bot de Elon)
    con el cliente httpx del SDK forzado a salir por el proxy del PC."""
    global ULTIMO_TRADE_TS
    ahora = time.time()
    if ahora - ULTIMO_TRADE_TS < 10:
        return False, "throttle"
    size_shares = round(stake_dolares / precio, 2)
    if size_shares < MIN_SHARES:
        stake_necesario = MIN_SHARES * precio * 1.01
        return False, f"size_{size_shares}_necesita_stake_${stake_necesario:.2f}"

    env = cargar_env()
    signer = env.get("POLY_PRIVATE_KEY", "").strip()
    api_key = env.get("POLY_API_KEY", "").strip()
    api_secret = env.get("POLY_API_SECRET", "").strip()
    api_passphrase = env.get("POLY_API_PASSPHRASE", "").strip()
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET).strip()
    if not signer:
        return False, "sin_credenciales"

    # 1) v10.9: cliente SDK con proxy INYECTADO en httpx + envío NATIVO.
    #    El POST manual de v10.6-10.8 estaba doblemente roto:
    #      a) el cuerpo no es el signed order crudo: la API v2 espera el
    #         envelope {"order":{...},"owner":...,"orderType":...} que
    #         construye order_to_json_v2() del SDK
    #      b) los headers L2 iban vacíos (api_key/passphrase del env no
    #         existen) y faltaba POLY_SIGNATURE (HMAC con el secret
    #         derivado, calculado sobre el cuerpo EXACTO serializado)
    #    Con create_and_post_order() el SDK hace todo eso solo; nosotros
    #    solo garantizamos que su httpx salga por el proxy del PC.
    try:
        proxy_ok = inyectar_proxy_sdk()
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds, OrderArgs
        from py_clob_client_v2 import SignatureTypeV2
        # Igual que el bot de Elon: si no hay creds, las derivamos de la private key
        kwargs_client = {
            "key": signer,
            "funder": wallet,
            "signature_type": int(SignatureTypeV2.POLY_PROXY) if wallet else int(SignatureTypeV2.EOA),
        }
        if api_key and api_secret and api_passphrase:
            kwargs_client["creds"] = ApiCreds(api_key, api_secret, api_passphrase)
        client = ClobClient(host=HOST_CLOB, chain_id=137, **kwargs_client)
        if "creds" not in kwargs_client:
            try:
                creds = client.derive_api_key()
                client.set_api_creds(creds)
                log(f"  · Creds derivadas automaticamente (proxy_sdk={'OK' if proxy_ok else 'FALLO'})")
            except Exception as e:
                return False, f"derive_error:{str(e)[:200]}"

        order_args = OrderArgs(token_id=token_id, price=precio,
                                size=size_shares, side="BUY")

        # 2) v10.9: POST nativo del SDK (patrón exacto del bot de Elon)
        log(f"  enviando orden via SDK (httpx+proxy)...")
        resp = client.create_and_post_order(order_args)
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
            except Exception:
                pass
        log(f"  SDK resp: {json.dumps(resp, default=str)[:220] if isinstance(resp, (dict, list)) else str(resp)[:220]}")
        if isinstance(resp, dict):
            if resp.get("success") is True or resp.get("orderID") or resp.get("orderId"):
                oid = resp.get("orderID") or resp.get("orderId") or resp.get("id") or "?"
                ULTIMO_TRADE_TS = ahora
                return True, {"oid": oid, "size": size_shares, "precio": precio,
                              "status": resp.get("status", "?")}
            err = resp.get("errorMsg") or resp.get("error") or str(resp)[:150]
            return False, f"api_rechazo:{str(err)[:200]}"
        return False, f"resp_desconocida:{str(resp)[:150]}"
    except Exception as e:
        # PolyApiException trae status_code y error_msg reales de la API
        status = getattr(e, "status_code", None)
        errmsg = getattr(e, "error_msg", None)
        if status is not None or errmsg is not None:
            return False, f"PolyApi[{status}]:{str(errmsg)[:200]}"
        return False, f"sdk_error:{str(e)[:200]}"

def vender_clob(token_id, precio, shares):
    """v12.3: orden CLOB de VENTA (side=SELL) para cerrar una posición SIMPLE.
    Mismo bootstrap que enviar_orden (SDK nativo + proxy del PC), pero con
    side=SELL y el tamaño en shares que ya poseemos."""
    env = cargar_env()
    signer = env.get("POLY_PRIVATE_KEY", "").strip()
    api_key = env.get("POLY_API_KEY", "").strip()
    api_secret = env.get("POLY_API_SECRET", "").strip()
    api_passphrase = env.get("POLY_API_PASSPHRASE", "").strip()
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET).strip()
    if not signer:
        return False, "sin_credenciales"
    if not token_id:
        return False, "sin_token"
    if shares <= 0:
        return False, "sin_shares"
    if not (0.01 <= precio <= 0.99):
        return False, f"precio_venta_{precio}_invalido"
    try:
        proxy_ok = inyectar_proxy_sdk()
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds, OrderArgs
        from py_clob_client_v2 import SignatureTypeV2
        kwargs_client = {
            "key": signer,
            "funder": wallet,
            "signature_type": int(SignatureTypeV2.POLY_PROXY) if wallet else int(SignatureTypeV2.EOA),
        }
        if api_key and api_secret and api_passphrase:
            kwargs_client["creds"] = ApiCreds(api_key, api_secret, api_passphrase)
        client = ClobClient(host=HOST_CLOB, chain_id=137, **kwargs_client)
        if "creds" not in kwargs_client:
            try:
                creds = client.derive_api_key()
                client.set_api_creds(creds)
            except Exception as e:
                return False, f"derive_error:{str(e)[:200]}"
        order_args = OrderArgs(token_id=str(token_id), price=round(float(precio), 2),
                               size=round(float(shares), 2), side="SELL")
        log(f"  [VENTA] token={str(token_id)[:18]} size={shares} precio={precio} (proxy_sdk={'OK' if proxy_ok else 'FALLO'})")
        resp = client.create_and_post_order(order_args)
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
            except Exception:
                pass
        log(f"  SDK resp venta: {json.dumps(resp, default=str)[:220] if isinstance(resp, (dict, list)) else str(resp)[:220]}")
        if isinstance(resp, dict):
            if resp.get("success") is True or resp.get("orderID") or resp.get("orderId"):
                oid = resp.get("orderID") or resp.get("orderId") or resp.get("id") or "?"
                return True, {"oid": oid, "size": round(float(shares), 2),
                              "precio": round(float(precio), 2),
                              "status": resp.get("status", "?")}
            err = resp.get("errorMsg") or resp.get("error") or str(resp)[:150]
            return False, f"api_rechazo:{str(err)[:200]}"
        return False, f"resp_desconocida:{str(resp)[:150]}"
    except Exception as e:
        status = getattr(e, "status_code", None)
        errmsg = getattr(e, "error_msg", None)
        if status is not None or errmsg is not None:
            return False, f"PolyApi[{status}]:{str(errmsg)[:200]}"
        return False, f"sdk_error:{str(e)[:200]}"


def ejecutar_trade(mercado, chat_id=None):
    """Ejecuta un trade en un mercado activo (v10: combo con token real)."""
    titulo = mercado["question"]
    log(f"[TRADE] {titulo[:60]}")
    # v10: resolver token real desde condition_id
    real_token = mercado.get("real_token")
    if not real_token:
        condition_id = mercado.get("condition_id", "")
        if not condition_id:
            log(f"  SKIP: no condition_id")
            return False, "no_condition_id"
        real_token = resolver_token_real(condition_id)
        if not real_token:
            log(f"  SKIP: no pude resolver token real de {condition_id[:10]}...")
            return False, "token_real_no_resuelto"
        mercado["real_token"] = real_token
        log(f"  token real resuelto: {real_token[:18]}...")
    # re-leer precio actual con el token real
    precio = get_precio_actual(real_token)
    if not precio or precio <= 0 or precio >= 1:
        log(f"  SKIP: precio no disponible")
        return False, "precio_no_disponible"
    if not (0.02 <= precio <= 0.95):
        log(f"  SKIP: precio {precio} fuera de mercado activo")
        return False, "mercado_inactivo"
    cuota = round(1/precio, 2)
    if not (CUOTA_MIN <= cuota <= CUOTA_MAX):
        log(f"  SKIP: cuota {cuota} fuera de [{CUOTA_MIN}-{CUOTA_MAX}]")
        return False, f"cuota_{cuota}_fuera"
    # enviar
    log(f"  precio={precio:.3f} cuota={cuota:.2f} stake=${STAKE_POR_TRADE}")
    ok, resultado = enviar_orden(real_token, precio, STAKE_POR_TRADE)
    if not ok:
        log(f"  ERROR: {resultado}")
        return False, resultado
    # guardar
    registro = {
        "tipo": "combo",
        "copiado_en": datetime.now().isoformat(),
        "question": titulo,
        "slug": mercado.get("slug"),
        "market_id": mercado.get("market_id", ""),
        "condition_id": mercado.get("condition_id", ""),
        "real_token": real_token,
        "precio_ejecutado": precio,
        "cuota_ejecutada": cuota,
        "size_shares": resultado["size"],
        "stake_dolares": STAKE_POR_TRADE,
        "order_id": resultado["oid"],
        "volumen": mercado.get("volumen", 0),
        "tags": mercado.get("tags", []),
        "status": "ejecutado",
    }
    estado = cargar_estado()
    estado["trades_copiados"].append(registro)
    guardar_estado(estado)
    if chat_id:
        tags_str = ", ".join(mercado.get("tags", [])[:3])
        enviar(chat_id, f"✅ *COMBO EJECUTADO*\n"
                      f"📌 {titulo[:60]}\n"
                      f"💵 {resultado['size']} shares @ {precio:.2f} (cuota {cuota:.2f})\n"
                      f"💰 Stake: ${STAKE_POR_TRADE}\n"
                      f"🏷 {tags_str}\n"
                      f"📊 Vol: ${mercado.get('volumen', 0):.0f}\n"
                      f"🆔 `{str(resultado['oid'])[:18]}`")
    return True, "ok"


# ============================================
# ESTADO
# ============================================
def cargar_estado():
    if not os.path.exists(ESTADO_FILE):
        return {"modo": MODO_OPERACION, "stake": STAKE_POR_TRADE,
                "stake_mode": "AUTO", "max_ops_dia": MAX_COMBOS_DIA,
                "trades_copiados": [], "historial": []}
    try:
        with open(ESTADO_FILE) as f:
            d = json.load(f)
        d.setdefault("modo", MODO_OPERACION)
        d.setdefault("stake", STAKE_POR_TRADE)
        d.setdefault("stake_mode", "AUTO")
        d.setdefault("max_ops_dia", MAX_COMBOS_DIA)
        d.setdefault("prob_min_auto", PROB_MEDIA_ALTA)
        d.setdefault("trades_copiados", [])
        d.setdefault("historial", [])
        return d
    except:
        return {"modo": MODO_OPERACION, "stake": STAKE_POR_TRADE,
                "stake_mode": "AUTO", "max_ops_dia": MAX_COMBOS_DIA,
                "trades_copiados": [], "historial": []}

def guardar_estado(estado):
    try:
        if os.path.exists(ESTADO_FILE):
            shutil.copy2(ESTADO_FILE, BACKUP_FILE)
    except Exception:
        pass  # el backup no debe romper el guardado
    with open(ESTADO_FILE, "w") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


# ============================================
# ESTADÍSTICAS
# ============================================
def calcular_stats():
    estado = cargar_estado()
    copiados = estado.get("trades_copiados", [])
    historial = estado.get("historial", [])
    s = {
        "total": len(copiados), "wins": 0, "losses": 0, "anuladas": 0,
        # v12.8.4: brutos para las cuentas de compensación (📊 Stats)
        "pnl_wins": 0.0, "pnl_losses": 0.0, "stake_wins": 0.0, "stake_losses": 0.0,
        "pnl": 0.0, "stake": 0.0, "mejor": None, "peor": None,
        "por_franja": {f: {"ops": 0, "wins": 0, "pnl": 0.0, "stake": 0.0}
                       for f in ("base", "extendida", "super")},
    }
    for op in copiados + historial:
        pnl = op.get("pnl")
        stake = op.get("stake_dolares") or op.get("stake_total") or 0
        if pnl is not None:
            s["pnl"] += pnl
            s["stake"] += stake
            # ↩️ v12.8.3: las anuladas (mercado devuelto) no son ni ✅ ni ❌
            if str(op.get("resultado")) == "anulada":
                s["anuladas"] += 1
            elif pnl > 0:
                s["wins"] += 1
                s["pnl_wins"] += pnl        # v12.8.4
                s["stake_wins"] += stake
            else:
                s["losses"] += 1
                s["pnl_losses"] += pnl      # v12.8.4
                s["stake_losses"] += stake
            pf = s["por_franja"][franja_of(op)]
            pf["ops"] += 1
            pf["pnl"] += pnl
            pf["stake"] += stake
            if pnl > 0: pf["wins"] += 1
            if s["mejor"] is None or pnl > s["mejor"].get("pnl", -9999):
                s["mejor"] = op
            if s["peor"] is None or pnl < s["peor"].get("pnl", 9999):
                s["peor"] = op
    return s


# ============================================
# v11.5: OPERACIONES EN VIVO (CLOB público)
# ============================================
CLOB_PUB = "https://clob.polymarket.com"
_MERCADO_CACHE = {}   # condition_id -> (ts, datos)


def _madrid(iso_utc):
    """ISO UTC -> 'DD/MM HH:MM' en hora de Madrid."""
    try:
        dt = datetime.fromisoformat(str(iso_utc).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            dt = dt.astimezone(ZoneInfo("Europe/Madrid"))
        except Exception:
            from datetime import timedelta
            dt = dt.astimezone(timezone(timedelta(hours=2)))
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return None


def mercado_clob(cid):
    """GET público clob.polymarket.com/markets/<cid> (sin auth), cache 5 min.
    Devuelve {closed, tokens:[{token_id,outcome,winner,price}], end_date_iso}."""
    cid = str(cid or "")
    if not cid.startswith("0x"):
        return None
    ahora = time.time()
    hit = _MERCADO_CACHE.get(cid)
    if hit and ahora - hit[0] < 300:
        return hit[1]
    data = None
    try:
        req = urllib.request.Request(f"{CLOB_PUB}/markets/{cid}",
                                     headers={"User-Agent": "poly-combos-bot"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode())
    except Exception:
        data = None
    _MERCADO_CACHE[cid] = (ahora, data)
    return data


def mercado_por_slug(slug):
    """Fallback gamma para registros antiguos sin condition_id."""
    try:
        req = urllib.request.Request(f"https://gamma-api.polymarket.com/markets?slug={slug}",
                                     headers={"User-Agent": "poly-combos-bot"})
        with urllib.request.urlopen(req, timeout=12) as r:
            arr = json.loads(r.read().decode())
        if not arr:
            return None
        m = arr[0]
        prices = m.get("outcomePrices") or []
        if isinstance(prices, str):
            prices = json.loads(prices or "[]")
        toks = m.get("clobTokenIds") or []
        if isinstance(toks, str):
            toks = json.loads(toks or "[]")
        tokens = [{"token_id": str(t),
                   "winner": (i < len(prices) and float(prices[i]) >= 0.999)}
                  for i, t in enumerate(toks)]
        return {"closed": bool(m.get("closed")), "tokens": tokens,
                "end_date_iso": m.get("endDate")}
    except Exception:
        return None


# ============================================
# v12.6: VERDAD REAL (cobros REDEEM de la wallet + saldo on-chain del combo)
# ============================================
_COBROS_CACHE = [0.0, {}, {}]   # [ts, {token: usdc}, {titulo_norm: {usdc,ts,n}}]  (v12.8.1)
_SALDO_CACHE = {}              # token -> (ts, shares|None)


def _rpc_eth_call_ex(to, data, frm=None, timeout=8):
    """v12.8: eth_call a Polygon devolviendo (resultado, error).
    Distinguir "revert" de "RPC caído" es imprescindible en el pre-flight de
    redeem: un revert significa que el contrato rechazó la llamada (no hay red)."""
    params = {"to": to, "data": data}
    if frm:
        params["from"] = frm
    cuerpo = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                         "params": [params, "latest"]}).encode()
    ultimo = None
    for rpc in RPCS_POLYGON:
        try:
            req = urllib.request.Request(rpc, data=cuerpo,
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": "poly-combos-bot"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode())
            v = d.get("result")
            if isinstance(v, str) and v not in ("", "0x"):
                return v, None
            if d.get("error"):
                ultimo = str(d["error"].get("message", ""))[:200]
        except Exception as e:
            ultimo = str(e)[:200]
            leer_err = getattr(e, "read", None)
            if leer_err:
                try:
                    cuerpo_err = leer_err().decode("utf-8", errors="replace")
                    msg = json.loads(cuerpo_err).get("error", {}).get("message", "")
                    if msg:
                        ultimo = str(msg)[:200]
                except Exception:
                    pass
    return None, ultimo


def _rpc_eth_call(to, data, timeout=8):
    """eth_call a Polygon probando varios RPC públicos. → hex|None."""
    v, _err = _rpc_eth_call_ex(to, data, timeout=timeout)
    return v


def _norm_titulo(s):
    """v12.8.1: título normalizado para casar una op con su cobro REDEEM.
    data-api titula el parlay "A AND B" y el bot guarda "A + B"; además quita
    signos y pasa a minúsculas. Se recorta a 120 chars (títulos largos)."""
    t = str(s or "").lower().replace(" and ", " + ")
    for ch in "?.!,:'\"()[]–—":
        t = t.replace(ch, " ")
    return _re.sub(r"\s+", " ", t).strip()[:120]


def _op_ts(op):
    """v12.8.1: epoch de la op (para la ventana temporal del casado por título)."""
    for k in ("copiado_en", "cerrado_en", "fecha"):
        v = op.get(k)
        if not v:
            continue
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            continue
    return None


def cobros_wallet(refrescar=False, limite=500):
    """v12.6/v12.8.1: cobros REDEEM reales de la wallet (data-api /activity).
    usdcSize>0 ⇒ esa posición GANÓ y el dinero YA está en la cartera (Polymarket
    autocobra las ganadoras; el bot no hace redeem). Cache 10 min; si la API
    falla devuelve lo último que tuvo.
    v12.8.1: (a) se pide con type=REDEEM y COBROS_PAGINAS páginas ⇒ histórico
    COMPLETO (77 cobros desde abril) en vez de los últimos 500 registros
    MEZCLADOS, donde los trades dejaban fuera los cobros antiguos; (b) además del
    índice por token se guarda otro por TÍTULO normalizado: las ops de la era
    copy-trading guardan un id que NO es el `asset` del cobro (las 4 de Cagliari
    se cobraron en UN redeem de $27.13) y por id nunca casaban."""
    ahora = time.time()
    if not refrescar and _COBROS_CACHE[1] and ahora - _COBROS_CACHE[0] < 600:
        return _COBROS_CACHE[1]
    cobros, titulos, act = {}, {}, []
    try:
        for pag in range(COBROS_PAGINAS):
            url = (f"{DATA_API}/activity?user={WALLET}&limit={limite}"
                   f"&offset={pag * limite}&type=REDEEM")
            req = urllib.request.Request(url, headers={"User-Agent": "poly-combos-bot"})
            with urllib.request.urlopen(req, timeout=20) as r:
                parte = json.loads(r.read().decode())
            act += parte or []
            if len(parte or []) < limite:
                break
        for a in act:
            if str(a.get("type", "")).upper() != "REDEEM":
                continue
            try:
                usdc = float(a.get("usdcSize") or 0)
            except Exception:
                usdc = 0.0
            tok = str(a.get("asset") or "")
            if tok:
                cobros[tok] = max(cobros.get(tok, 0.0), usdc)
            tit = _norm_titulo(a.get("title"))
            if tit:
                g = titulos.get(tit) or {"usdc": 0.0, "ts": 0, "n": 0}
                g["usdc"] = round(g["usdc"] + usdc, 6)
                try:
                    g["ts"] = max(g["ts"], int(a.get("timestamp") or 0))
                except Exception:
                    pass
                g["n"] += 1
                titulos[tit] = g
        _COBROS_CACHE[0], _COBROS_CACHE[1], _COBROS_CACHE[2] = ahora, cobros, titulos
        log(f"  verdad: {sum(1 for v in cobros.values() if v > 0)} cobros REDEEM>0 "
            f"por token + {len(titulos)} por título ({len(act)} registros)")
    except Exception as e:
        log(f"  cobros_wallet: sin datos ({str(e)[:60]})")
    return cobros or _COBROS_CACHE[1]





def saldo_combo_token(token_id, refrescar=False, contrato=None):
    """v12.6: balanceOf del token de COMBO en su ERC1155 (0x006f…efef).
    >0 ⇒ los tokens SIGUEN en la cartera (posición no liquidada).
    0 ⇒ ya no están (cobrados, vendidos o perdidos). None si ningún RPC responde.
    Cache 5 min. v12.8.1: `contrato` permite mirar OTRO ERC1155 (el CTF para
    mercados simples) y la cache pasa a keyed por contrato+token."""
    tok = str(token_id or "")
    if not tok.isdigit():
        return None
    con = str(contrato or PARLAY_ERC1155).lower()
    clave = f"{con}:{tok}"
    ahora = time.time()
    hit = _SALDO_CACHE.get(clave)
    if hit and not refrescar and ahora - hit[0] < 300:
        return hit[1]
    sal = None
    try:
        data = ("0x00fdd58e" + WALLET[2:].rjust(64, "0")
                + hex(int(tok))[2:].rjust(64, "0"))
        time.sleep(0.15)                 # v12.8.2: espaciar eth_call (anti 429)
        v = _rpc_eth_call(con, data)
        if v:
            sal = int(v, 16) / 1e6
    except Exception:
        sal = None
    _SALDO_CACHE[clave] = (ahora, sal)
    return sal


def saldo_token_op(op, refrescar=False):
    """v12.8.1: saldo on-chain del token de una op en SU contrato: los COMBOS
    viven en el ERC1155 de parlays y los mercados SIMPLES en el CTF. Mirar el
    contrato equivocado daba siempre 0 (y eso ocultaba posiciones sin cobrar)."""
    tok = _token_de(op)
    es_combo = bool(op.get("legs")) or str(op.get("tipo") or "") == "combo_rfq"
    return saldo_combo_token(tok, refrescar=refrescar,
                             contrato=(PARLAY_ERC1155 if es_combo else CTF_ERC1155))


# ============================================
# v12.8: 💰 RECLAMAR — ganadas con el dinero aún en tokens
# ============================================
_PREFLIGHT_CACHE = [0.0, None, ""]      # [ts, ok|None, detalle]
_EVENTO_CACHE = {}                      # condition_id -> (ts, url)


def _md_limpio(s):
    """v12.8: quita los caracteres que romperían el Markdown de Telegram."""
    return str(s or "").replace("*", "").replace("_", " ").replace("`", "").strip()


def _token_de(op):
    """v12.8: token id del combo (position id real del CLOB de parlays)."""
    return str(op.get("combo_yes_position_id") or op.get("real_token") or "")


def _ya_cobrada(op):
    """v12.8: la op ya tiene dinero REAL recibido (REDEEM) o se dio por reclamada."""
    try:
        if float(op.get("cobro_real") or 0) > 0.000001:
            return True
    except Exception:
        pass
    if str(op.get("fuente_verdad") or "") == "cobro_real":
        return True
    return str(op.get("reclamo") or "") == "reclamado"


def calldata_redeem(tokens, owner=None):
    """💰 v12.8: calldata de redeem(address[] owners, uint256[] tokenIds) del
    adaptador de parlays. Arrays PARALELOS: owners[i] ↔ tokenIds[i] (longitudes
    distintas ⇒ revert). Reproducido BYTE A BYTE contra cobros reales de la
    wallet (tx 0x296d4dbb60a05221539fec73e76a96cbfa1c4f8ec6996f0beec4562982ce16f0).
    El "conditionId" que da la data-api para un parlay ES este token id."""
    ow = str(owner or WALLET).lower()
    toks = [str(t) for t in (tokens or []) if str(t).isdigit()]
    if not toks or not ow.startswith("0x") or len(ow) != 42:
        return None
    n = len(toks)
    h = "0x" + REDEEM_SEL
    h += hex(0x40)[2:].rjust(64, "0")                       # offset owners[]
    h += hex(0x40 + 0x20 + 0x20 * n)[2:].rjust(64, "0")     # offset tokenIds[]
    h += hex(n)[2:].rjust(64, "0")                          # owners.length
    h += ow[2:].rjust(64, "0") * n
    h += hex(n)[2:].rjust(64, "0")                          # tokenIds.length
    for t in toks:
        h += hex(int(t))[2:].rjust(64, "0")
    return h


def preflight_redeem(token, forzar=False):
    """💰 v12.8: ¿puede la wallet ejecutar el cobro ELLA SOLA?
    eth_call desde la proxy wallet al adaptador con el calldata real de redeem.
    Hoy (11-sep-2026) REVERT: Polymarket sólo acepta la llamada de su cuenta
    ERC-4337 OPERADOR_REDEEM_4337, que cobra las ganadoras vía EntryPoint
    handleOps. Probado también desde una EOA cualquiera y desde 0x1: mismo revert.
    → (True|False|None, detalle). Cacheado RECLAMO_PREFLIGHT_H horas."""
    ahora = time.time()
    if (not forzar and _PREFLIGHT_CACHE[1] is not None
            and ahora - _PREFLIGHT_CACHE[0] < RECLAMO_PREFLIGHT_H * 3600):
        return _PREFLIGHT_CACHE[1], _PREFLIGHT_CACHE[2]
    data = calldata_redeem([token]) if token else None
    if not data:
        return None, "sin token que probar"
    v, err = _rpc_eth_call_ex(PARLAY_REDEEM_ADAPTER, data, frm=WALLET)
    if v is not None:
        ok, det = True, "el adaptador ya acepta la llamada de tu wallet"
    elif err and "revert" in err.lower():
        ok = False
        det = (f"revert: sólo la cuenta de Polymarket {OPERADOR_REDEEM_4337[:10]}…"
               f"{OPERADOR_REDEEM_4337[-4:]} puede ejecutar redeem()")
    elif err:
        ok, det = None, f"RPC respondió: {err[:90]}"
    else:
        ok, det = None, "ningún RPC respondió"
    _PREFLIGHT_CACHE[0], _PREFLIGHT_CACHE[1], _PREFLIGHT_CACHE[2] = time.time(), ok, det
    log(f"  💰 pre-flight redeem: {'SÍ puede' if ok else ('NO puede' if ok is False else 'sin datos')}"
        f" · {det[:80]}")
    return ok, det


def _enlace_evento(op):
    """v12.8: enlace al evento en polymarket.com (gamma: condition_id → events[0].slug)."""
    cid = ""
    for lg in (op.get("legs") or []):
        c = str(lg.get("condition_id") or "")
        if c.startswith("0x"):
            cid = c
            break
    if not cid:
        return ""
    hit = _EVENTO_CACHE.get(cid)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    url = ""
    try:
        req = urllib.request.Request(f"{GAMMA_API}/markets?condition_ids={cid}",
                                     headers={"User-Agent": "poly-combos-bot"})
        with urllib.request.urlopen(req, timeout=12) as r:
            arr = json.loads(r.read().decode())
        evs = (arr[0].get("events") or []) if arr else []
        slug = str(evs[0].get("slug") or "") if evs else ""
        if slug:
            url = f"https://polymarket.com/event/{slug}"
    except Exception:
        url = ""
    _EVENTO_CACHE[cid] = (time.time(), url)
    return url


def _primer_token(estado=None):
    """v12.8: cualquier token de combo del histórico (para el pre-flight)."""
    estado = estado or cargar_estado()
    for op in (estado.get("historial") or []) + (estado.get("trades_copiados") or []):
        t = _token_de(op)
        if t.isdigit():
            return t
    return ""


def pendientes_reclamar(con_saldo=True, estado=None):
    """💰 v12.8: combos GANADOS cuyo dinero SIGUE en la cartera (sin cobrar).
    Recorre TODO (histórico + abiertas): los cobros de Polymarket no caducan, así
    que aquí NO se aplica el límite de días de la auto-curación.
    Criterio: sin cobro REDEEM + saldo on-chain del token > 0 + legs ganadoras
    (resolver_operacion). con_saldo=False usa el saldo guardado (sin RPC).
    → {"reclamables":[{op,token,saldo,importe,stake,titulo,desde,fuente}],
       "sin_datos":int, "importe":float, "revisadas":int}"""
    estado = estado or cargar_estado()
    ops = list(estado.get("historial") or []) + list(estado.get("trades_copiados") or [])
    reclamables, vistos = [], set()
    revisadas = sin_datos = 0
    for op in ops:
        tok = _token_de(op)
        if not tok.isdigit() or tok in vistos or _ya_cobrada(op):
            continue
        vistos.add(tok)
        revisadas += 1
        sal = saldo_token_op(op) if con_saldo else op.get("saldo_tokens")
        if sal is None and con_saldo:
            # v12.8.2: un None suele ser un 429/timeout del RPC, no "sin saldo".
            # Se reintenta UNA vez saltando la caché (que guardaba el None 5 min).
            time.sleep(1.2)
            sal = saldo_token_op(op, refrescar=True)
        if sal is None:
            if con_saldo:
                sin_datos += 1
            continue
        try:
            sal = float(sal)
        except Exception:
            continue
        if sal <= 0.000001:
            continue                       # sin tokens: cobrado, vendido o perdido
        r = resolver_operacion(op)
        if not (r.get("resuelta") and r.get("ganada")):
            continue                       # en juego o perdida: nada que reclamar
        if r.get("fuente") == "cobro_real":
            continue                       # ya cobrado (REDEEM en /activity)
        reclamables.append({
            "op": op, "token": tok, "saldo": round(sal, 6),
            "importe": round(sal, 2),      # 1 token ganador = $1 pUSD al redimir
            "stake": round(float(op.get("stake_dolares") or 0), 2),
            "titulo": _md_limpio(op.get("question"))[:74] or "?",
            "desde": _madrid(op.get("copiado_en") or op.get("cerrado_en") or "") or "—",
            "fuente": r.get("fuente"),
        })
    reclamables.sort(key=lambda x: -x["importe"])
    return {"reclamables": reclamables, "sin_datos": sin_datos,
            "importe": round(sum(x["importe"] for x in reclamables), 2),
            "revisadas": revisadas}


def _texto_reclamar(res, ok=None, det=""):
    """v12.8: mensaje de /reclamar."""
    rec = res.get("reclamables") or []
    txt = ("💰 *RECLAMAR v12.9.0*\n\n"
           f"Ops revisadas: {res.get('revisadas', 0)}"
           + (f" · sin datos on-chain: {res.get('sin_datos')}" if res.get("sin_datos") else "")
           + "\n\n")
    if not rec:
        txt += "✅ *Nada sin cobrar*: todo lo ganado ya está en la cartera.\n"
    else:
        txt += (f"🏦 *GANADAS SIN COBRAR: {len(rec)}* → *${res.get('importe', 0):.2f}*\n"
                "_El dinero sigue en tokens: al redimir, 1 token ganador = $1._\n")
        for x in rec[:RECLAMO_MAX_LISTA]:
            enl = _enlace_evento(x["op"])
            txt += (f"\n• {x['desde']} — {x['titulo']}\n"
                    f"   pagado ${x['stake']:.2f} → a cobrar *${x['importe']:.2f}* "
                    f"({x['saldo']:.2f} sh)\n")
            if enl:
                txt += f"   {enl}\n"
            txt += f"   token `{x['token'][:24]}…`\n"
        if len(rec) > RECLAMO_MAX_LISTA:
            txt += f"\n_… y {len(rec) - RECLAMO_MAX_LISTA} más_\n"
    txt += "\n🔌 *¿Puede el bot cobrarlo on-chain?* "
    if ok is True:
        txt += f"*SÍ* — {det}.\n_Dímelo y preparo la ejecución del redeem._\n"
    elif ok is False:
        txt += ("*NO* (probado ahora con eth_call).\n"
                f"El adaptador de parlays sólo acepta la llamada de la cuenta de "
                f"Polymarket `{OPERADOR_REDEEM_4337[:10]}…{OPERADOR_REDEEM_4337[-4:]}` "
                f"(ERC-4337): es ella quien cobra las ganadoras.\n")
    else:
        txt += f"*sin datos* — {det[:80]}\n"
    if rec and ok is not True:
        txt += ("\n👉 *Cómo cobrarlo tú* (1 minuto):\n"
                "1. polymarket.com → *Portfolio* → *Positions*\n"
                "2. En la posición ganada, botón *Claim* / *Redeem*\n"
                "3. Si no aparece el botón: soporte de Polymarket con el token id\n"
                "_Los cobros no caducan: ese dinero es tuyo hasta que lo reclames._")
    return txt


def _marcar_avisados(res, estado=None):
    """v12.8: guarda qué reclamos ya se avisaron (la auto-curación no los repite)."""
    try:
        estado = estado or cargar_estado()
        av = estado.setdefault("reclamos_avisados", {})
        ahora = datetime.now(timezone.utc).isoformat()
        for x in res.get("reclamables") or []:
            av[x["token"]] = {"ts": ahora, "importe": x["importe"],
                              "titulo": x["titulo"][:80]}
        guardar_estado(estado)
    except Exception as e:
        log(f"  [reclamar] marcar error: {e}")


def reclamar_check(silencioso=True, confirmar=True):
    """💰 v12.8/v12.8.1: lo llama la auto-curación. Detecta ops ganadas SIN
    cobro real, lo CONFIRMA on-chain (saldo > 0 en el contrato que
    toca: combos → ERC1155 de parlays, simples → CTF) y avisa sólo de las NUEVAS.
    confirmar=False se salta la comprobación on-chain. → nº de ops avisadas."""
    if not CHAT_ID:
        return 0
    try:
        estado = cargar_estado()
    except Exception:
        return 0
    av = estado.setdefault("reclamos_avisados", {})
    grupos = {}
    for op in (estado.get("historial") or []) + (estado.get("trades_copiados") or []):
        tok = _token_de(op)
        # v12.8.1: agrupado por token (4 ops de Cagliari son UN solo position)
        if not tok.isdigit() or tok in av or _ya_cobrada(op):
            continue
        fv = str(op.get("fuente_verdad") or "")
        if fv == "legs_ganadas" or (str(op.get("resultado") or "") == "ganada"
                                    and fv != "cobro_real"):
            grupos.setdefault(tok, []).append(op)
    # v12.8.1: confirmar ON-CHAIN antes de avisar. Sin este paso, ops antiguas
    # cuyo cobro no casaba por id provocaban falsas alarmas (7 ops "sin cobrar"
    # que en realidad tenían saldo 0 en el CTF y en el ERC1155 de parlays).
    # El importe es el SALDO real del token: varias ops pueden compartirlo (las
    # 4 compras de Cagliari son un único position de 27.13 shares).
    nuevos, importes = [], {}
    for tok, grupo in grupos.items():
        sal = saldo_token_op(grupo[0]) if confirmar else None
        if sal is not None and float(sal) <= 0.000001:
            av[tok] = {"ts": datetime.now(timezone.utc).isoformat(), "auto": True,
                       "importe": 0.0, "nota": "saldo 0 on-chain: ya cobrada/vendida"}
            continue
        if sal is not None:
            importes[tok] = round(float(sal), 2)
        else:                          # sin RPC: no se descarta a ciegas
            importes[tok] = round(sum(float(o.get("size_shares") or 0) for o in grupo), 2)
        nuevos.append(grupo[0])
    if not nuevos:
        try:
            guardar_estado(estado)
        except Exception:
            pass
        return 0
    imp = sum(importes.values())
    log(f"  💰 reclamar: {len(nuevos)} ganada(s) sin cobrar (~${imp:.2f}) → aviso")
    try:
        enviar(CHAT_ID, f"💰 *RECLAMAR*: hay *{len(nuevos)}* combo(s) ganados sin "
                        f"cobrar (~${imp:.2f} siguen en tokens).\n"
                        f"Envía /reclamar para el detalle y cómo cobrarlos.")
    except Exception:
        pass
    ahora = datetime.now(timezone.utc).isoformat()
    for o in nuevos:
        t = _token_de(o)
        av[t] = {"ts": ahora, "auto": True, "importe": importes.get(t, 0.0),
                 "titulo": _md_limpio(o.get("question"))[:80]}
    try:
        guardar_estado(estado)
    except Exception:
        pass
    return len(nuevos)


def cmd_reclamar(chat_id, texto=""):
    """💰 v12.8: /reclamar — qué hay GANADO SIN COBRAR, cuánto y cómo cobrarlo.
    /reclamar prueba = fuerza la prueba on-chain (sin usar la caché de 24h).
    Hilo propio con los locks de la auto-curación (hace llamadas RPC)."""
    forzar = any(k in str(texto).lower() for k in ("prueba", "test", "forzar"))

    def _run():
        try:
            enviar(chat_id, "💰 Buscando combos GANADOS sin cobrar (saldo on-chain "
                            "+ cobros REDEEM + legs ganadoras)… "
                            "_puede tardar unos segundos_")
            cobros_wallet(refrescar=True)
            with AUDITORIA_LOCK:
                with PASADA_LOCK:
                    res = pendientes_reclamar(con_saldo=True)
                    tok = (res["reclamables"][0]["token"] if res["reclamables"]
                           else _primer_token())
                    ok, det = preflight_redeem(tok, forzar=forzar)
                    _marcar_avisados(res)
            enviar(chat_id, _texto_reclamar(res, ok, det))
            log(f"  💰 /reclamar: {len(res['reclamables'])} sin cobrar "
                f"(${res['importe']:.2f}) · revisadas {res['revisadas']}")
        except Exception as e:
            log(f"  [reclamar] error: {e}")
            try:
                enviar(chat_id, f"❌ /reclamar falló: {str(e)[:200]}")
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()


def verdad_real(op, con_saldo=False):
    """v12.6/v12.8.1: contraste con la fuente de verdad de Polymarket.
    → {"token", "cobro": float|None, "saldo": float|None, "cobro_por"}
    con_saldo=True añade la consulta on-chain (sólo /reauditar y /reclamar: el
    bucle AUTO no debe esperar a un RPC).
    v12.8.1: si el token no casa con ningún cobro se intenta por TÍTULO (con
    ventana temporal), que es como casan las ops antiguas de mercados simples.
    El cobro anotado son SUS shares (1 token ganador = $1), nunca el total del
    redeem: un mismo redeem puede agrupar varias ops del mismo mercado."""
    tok = _token_de(op)
    out = {"token": tok, "cobro": None, "saldo": None, "cobro_por": None}
    if tok:
        out["cobro"] = cobros_wallet().get(tok)
        if out["cobro"]:
            out["cobro_por"] = "token"
    if not out["cobro"]:
        tit = _norm_titulo(op.get("question"))
        grupo = (_COBROS_CACHE[2] or {}).get(tit) if tit else None
        if grupo and float(grupo.get("usdc") or 0) > 0.000001:
            ts_op, ts_cobro = _op_ts(op), int(grupo.get("ts") or 0)
            dentro = True
            if ts_op and ts_cobro:
                dentro = (ts_op - 43200) <= ts_cobro <= (
                    ts_op + COBRO_TITULO_VENTANA_D * 86400)
            shares = float(op.get("size_shares") or 0)
            if dentro and shares > 0:
                out["cobro"] = round(shares, 6)
                out["cobro_por"] = "titulo"
                out["cobro_grupo"] = round(float(grupo["usdc"]), 6)
    if con_saldo:
        out["saldo"] = saldo_token_op(op)
    return out


def estado_leg(m, nombre_nuestro=None):
    """v12.6: estado REAL de una leg según su mercado CLOB.
    → ("ganada"|"perdida"|"pendiente", info)
    OJO: los position_ids del catálogo de combos NO son los token_id del CLOB,
    así que comparar ids nunca acierta. El ganador se identifica por el NOMBRE
    de la cara (outcome); si la op no lo guarda, por el ÍNDICE 0 (el bot compra
    la primera cara, la misma que position_ids[0])."""
    if not m:
        return "pendiente", "sin datos CLOB"
    toks = m.get("tokens") or []
    win_idx = None
    win_out = None
    for i, tk in enumerate(toks):
        if tk.get("winner"):
            win_idx = i
            win_out = str(tk.get("outcome") or "").strip()
    if win_idx is None:
        # cerrado o no, pero SIN ganador declarado ⇒ resolución pendiente (UMA)
        return "pendiente", ("cerrado, ganador sin declarar" if m.get("closed") else "en juego")
    nuestro = str(nombre_nuestro or "").strip()
    if nuestro:
        g = nuestro.lower() == win_out.lower()
    else:
        g = (win_out.lower() in OUTCOME_NUESTRO) or win_idx == 0
    return ("ganada" if g else "perdida"), f"ganó '{win_out}'"


def resolver_operacion(op):
    """Estado en vivo de un registro. → {"resuelta", "ganada", "pnl", "fin",
    "detalle":[(question, None|True|False)], "fuente"}.
    Combos: se resuelven por LEGS (el token combo no cotiza en el CLOB);
    single: por su condition_id/token.
    v12.6: sólo se archiva como PERDIDA si una leg perdió DE VERDAD. Con alguna
    leg aún sin ganador declarado queda ⏳ PENDIENTE (antes se daba por perdido
    en cuanto un mercado cerraba). Y si la wallet ya COBRÓ el combo (REDEEM),
    manda el dinero real recibido."""
    shares = float(op.get("size_shares") or 0)
    stake = float(op.get("stake_dolares") or 0)
    legs = op.get("legs") or []
    out = {"resuelta": False, "ganada": None, "pnl": None, "fin": None,
           "detalle": [], "fuente": None}
    fines = []
    if legs:
        ganadas = perdidas = pendientes = sin_datos = 0
        for lg in legs:
            m = mercado_clob(lg.get("condition_id"))
            q = lg.get("question", "?")
            if not m:
                sin_datos += 1     # v12.7: sin datos del CLOB ⇒ NO se puede juzgar
            st_leg, _info = estado_leg(m, lg.get("outcome"))
            if m and m.get("end_date_iso"):
                fines.append(m["end_date_iso"])
            if st_leg == "ganada":
                ganadas += 1
            elif st_leg == "perdida":
                perdidas += 1
            else:
                pendientes += 1
            out["detalle"].append((q, True if st_leg == "ganada"
                                   else (False if st_leg == "perdida" else None)))
        if fines:
            out["fin"] = _madrid(max(fines))
        verdad = verdad_real(op)
        cobro = verdad.get("cobro")
        if cobro is not None and cobro > 0.000001:
            # 💰 dinero REAL recibido en la wallet: manda sobre cualquier deducción
            out.update(resuelta=True, ganada=True, pnl=round(cobro - stake, 2),
                       fuente="cobro_real", cobro_real=round(cobro, 6))
            return out
        if perdidas:
            out.update(resuelta=True, ganada=False, pnl=round(-stake, 2),
                       fuente="leg_perdida")
            return out
        if pendientes == 0 and ganadas == len(legs):
            out.update(resuelta=True, ganada=True, pnl=round(shares - stake, 2),
                       fuente="legs_ganadas")
            return out
        out["pendiente_info"] = f"{ganadas}✅ {perdidas}❌ {pendientes}⏳"
        out["sin_datos"] = sin_datos
        if verdad.get("saldo") is not None:
            out["saldo_tokens"] = round(float(verdad["saldo"]), 6)
        return out          # ⏳ PENDIENTE: no se archiva
    # ---- mercado simple ----
    m = mercado_clob(op.get("condition_id"))
    if not m and op.get("slug"):
        m = mercado_por_slug(op.get("slug"))
    if not m:
        return out
    if m.get("end_date_iso"):
        out["fin"] = _madrid(m["end_date_iso"])
    win_tok = None
    for tk in (m.get("tokens") or []):
        if tk.get("winner"):
            win_tok = str(tk.get("token_id"))
    if not win_tok:
        # ↩️ v12.8.3: cerrado/suspendido SIN ganador declarado. Antes se esperaba
        # para siempre aunque la wallet YA hubiera cobrado: los mercados ANULADOS
        # (partido no jugado) devuelven ~$0.50 por token y ese REDEEM no casa con
        # ningún ganador. Si hay cobro real (casado por token o por título) se
        # archiva con el dinero DE VERDAD recibido, REPARTIDO entre los fills del
        # mismo mercado en proporción a sus shares — nunca el cobro entero a cada
        # fill, que es lo que habría inflado el PnL.
        rep = reparto_cobro(op)
        por_share = (rep or {}).get("por_share")
        if por_share and shares > 0:
            cobro = round(float(por_share) * shares, 6)
            if cobro > 0.000001:
                gan = cobro >= shares * 0.999
                out.update(resuelta=True, ganada=gan, pnl=round(cobro - stake, 2),
                           fuente="cobro_real_simple", cobro_real=cobro,
                           anulada=(not gan),
                           ratio_cobro=(round(cobro / shares, 4) if shares else None))
                return out
        if m.get("closed"):
            out["sin_ganador"] = True    # cerrado sin ganador: sigue en espera
        return out          # v12.6: cerrado sin ganador declarado ⇒ se espera
    mio = str(op.get("real_token") or "")
    if mio:
        g = (win_tok == mio)
    else:
        g = (estado_leg(m, None)[0] == "ganada")
    out.update(resuelta=True, ganada=g, fuente="mercado_simple",
               pnl=round(shares - stake, 2) if g else round(-stake, 2))
    return out


def sincronizar_operaciones():
    """Mueve las ops resueltas de trades_copiados a historial con pnl/resultado.
    → (abiertas, nuevas_cerradas, estado)."""
    estado = cargar_estado()
    curar_abiertas(estado, aplicar=True)     # 🧹 v12.8.3: basura + duplicados
    _reparto_mapa(estado, forzar=True)       # 💰 v12.8.3: cobro real repartido
    ops = estado.get("trades_copiados", [])
    if not ops:
        return [], [], estado
    quedan, nuevas = [], []
    for op in ops:
        if op.get("status") == "fallido":
            quedan.append(op)
            continue
        r = resolver_operacion(op)
        if r["resuelta"]:
            op["status"] = "cerrado"
            # ↩️ v12.8.3: mercado anulado/devuelto = ni ganada ni perdida
            op["resultado"] = ("anulada" if r.get("anulada")
                               else ("ganada" if r["ganada"] else "perdida"))
            op["pnl"] = r["pnl"]
            op["fin_real"] = r.get("fin")
            op["fuente_verdad"] = r.get("fuente")       # v12.8.4
            if r.get("cobro_real"):
                op["cobro_real"] = r["cobro_real"]      # v12.8.4: dinero real recibido
            op["cerrado_en"] = datetime.now(timezone.utc).isoformat()
            nuevas.append(op)
        else:
            if r.get("fin"):
                op["fin_previsto"] = r["fin"]
            quedan.append(op)
    if nuevas:
        estado["trades_copiados"] = quedan
        estado.setdefault("historial", []).extend(nuevas)
        guardar_estado(estado)
        log(f"  sync: {len(nuevas)} op(s) cerradas ({sum(1 for o in nuevas if o['resultado'] == 'ganada')} ganadas, "
            f"PnL ${sum(o['pnl'] for o in nuevas):+.2f})")
    return quedan, nuevas, estado


_PRECIO_CACHE = {}   # v12.1: token_id -> (ts, mid)


def precio_mid(token_id):
    """v12.1: midpoint CLOB público = precio/probabilidad actual del token.
    Cache 60s. None si no disponible."""
    tok = str(token_id or "")
    if not tok.isdigit():
        return None
    ahora = time.time()
    hit = _PRECIO_CACHE.get(tok)
    if hit and ahora - hit[0] < 60:
        return hit[1]
    mid = None
    try:
        req = urllib.request.Request(f"{CLOB_PUB}/midpoint?token_id={tok}",
                                     headers={"User-Agent": "poly-combos-bot"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode())
        mid = float(d.get("mid"))
        if not (0 < mid < 1):
            mid = None
    except Exception:
        mid = None
    _PRECIO_CACHE[tok] = (ahora, mid)
    return mid


def agrupar_abiertas(abiertas):
    """v12.1: agrupa fills duplicados de la MISMA posición (misma apuesta o
    misma conjunta) → una sola entrada con sus ops."""
    grupos, orden = {}, []
    for op in abiertas:
        legs = op.get("legs") or []
        if legs:
            clave = ("combo", huella_combo(sorted(str(l.get("position_id")) for l in legs)))
        else:
            clave = ("single", str(op.get("real_token") or op.get("condition_id") or op.get("question")))
        g = grupos.get(clave)
        if not g:
            g = {"ops": []}
            grupos[clave] = g
            orden.append(clave)
        g["ops"].append(op)
    return [grupos[c] for c in orden]


_LEGTOK_CACHE = {}

def token_clob_de_leg(lg):
    """🔴 v12.8.2: TOKEN_ID REAL del CLOB para una leg.
    El `position_id` que guarda la op es el del CATÁLOGO de combos y NO sirve
    para pedir precio (`/midpoint` responde 404 SIEMPRE con él) — el mismo error
    de ids que en v12.6 rompía los resultados, pero en la ruta de precios. Se
    resuelve por condition_id + outcome (o índice 0 si la op es antigua y no
    guardó su outcome), con caché de 15 min."""
    lg = lg or {}
    cid = str(lg.get("condition_id") or "")
    if not cid.startswith("0x"):
        return None
    out = str(lg.get("outcome") or "").strip().lower()
    clave = f"{cid}|{out}"
    ahora = time.time()
    hit = _LEGTOK_CACHE.get(clave)
    if hit and ahora - hit[0] < 900:
        return hit[1]
    tok = None
    try:
        m = mercado_clob(cid)
        toks = (m or {}).get("tokens") or []
        if toks:
            idx = 0
            if out:
                for i, t in enumerate(toks):
                    if str(t.get("outcome") or "").strip().lower() == out:
                        idx = i
                        break
            tok = str(toks[idx].get("token_id") or "") or None
    except Exception:
        tok = None
    _LEGTOK_CACHE[clave] = (ahora, tok)
    return tok


def vivo_de(op):
    """Precio vivo: single = mid de su token; combo = producto de mids de legs.
    🔴 v12.8.2: el mid de cada leg se pide con su TOKEN REAL del CLOB — antes se
    usaba el position_id del catálogo (404 siempre), así que NINGÚN combo tenía
    precio vivo y no se podía cerrar ni valorar."""
    legs = op.get("legs") or []
    if legs:
        prod = 1.0
        for lg in legs:
            mm = precio_mid(token_clob_de_leg(lg) or lg.get("position_id"))
            if mm is None:
                # v12.8.2: leg ya DECIDIDA ⇒ su mid real es 1.0/0.0 y precio_mid
                # lo descarta (sólo acepta 0<mid<1). Se cuenta por su veredicto,
                # así un combo con una leg terminada y el resto en juego SÍ tiene
                # valor en el panel en vez de "n/d". Sin veredicto ⇒ None.
                est, _ = estado_leg(mercado_clob(str(lg.get("condition_id") or "")),
                                    lg.get("outcome"))
                if est == "ganada":
                    mm = 1.0
                elif est == "perdida":
                    mm = 0.0
                else:
                    return None
            prod *= mm
        return prod
    return precio_mid(op.get("real_token"))


def _din(d):
    """+$1.58 / -$0.75 (formato legible de dinero con signo)."""
    return ("+$" if d >= 0 else "-$") + f"{abs(d):.2f}"


def clave_grupo(g):
    """v12.3: clave identificativa de un grupo de ABIERTAS (misma regla que
    agrupar_abiertas) — sirve para reencontrar la posición al pulsar 🔒."""
    op0 = g["ops"][0]
    legs = op0.get("legs") or []
    if legs:
        return ("combo", huella_combo(sorted(str(l.get("position_id")) for l in legs)))
    return ("single", str(op0.get("real_token") or op0.get("condition_id") or op0.get("question")))


def h8_clave(clave):
    return hashlib.sha1(str(clave).encode()).hexdigest()[:8]


def _prune_abiertas():
    global ABIERTAS_CACHE
    ahora = time.time()
    ABIERTAS_CACHE = {k: v for k, v in ABIERTAS_CACHE.items() if ahora - v[0] < 3600}
    if len(ABIERTAS_CACHE) > 60:
        viejas = sorted(ABIERTAS_CACHE, key=lambda k: ABIERTAS_CACHE[k][0])
        for k in viejas[:len(ABIERTAS_CACHE) - 60]:
            ABIERTAS_CACHE.pop(k, None)


def grupos_abiertos_actuales():
    """v12.3: sincroniza y devuelve (estado, grupos) con los OBJETOS del estado
    cargado (importante: el cierre archiva sobre esos mismos objetos)."""
    try:
        sincronizar_operaciones()
    except Exception as e:
        log(f"  [CIERRE] sync previo falló: {e}")
    estado = cargar_estado()
    ops = [o for o in estado.get("trades_copiados", [])
           if o.get("status") != "fallido"
           and str(o.get("question", "")).strip() not in ("", "?")
           and (float(o.get("stake_dolares") or 0) > 0 or o.get("legs"))]
    return estado, agrupar_abiertas(ops)


def archivar_cierre(ops, neto, estado, motivo="cerrada_manual", tx=""):
    """v12.3: mueve las ops cerradas manualmente de ABIERTAS a historial con
    su PnL real. Una posición puede ser VARIOS fills (agrupados): la venta es
    una sola, así que lo recibido se REPARTE proporcionalmente a las shares de
    cada fill y el PnL de cada uno es (su parte - lo que pagó). Así la suma de
    los PnL cuadra con el cierre conjunto y las estadísticas no cuentan doble.
    → PnL conjunto."""
    neto = float(neto)
    stake_total = sum(float(o.get("stake_dolares") or 0) for o in ops)
    shares_total = sum(float(o.get("size_shares") or 0) for o in ops)
    pnl_conjunto = round(neto - stake_total, 2)
    ids = {id(o) for o in ops}
    quedan = [o for o in estado.get("trades_copiados", []) if id(o) not in ids]
    ahora_iso = datetime.now(timezone.utc).isoformat()
    repartido = 0.0
    for i, o in enumerate(ops):
        sh = float(o.get("size_shares") or 0)
        if i == len(ops) - 1:
            parte = round(neto - repartido, 2)      # el último se lleva el resto (sin descuadres)
        elif shares_total > 0:
            parte = round(neto * (sh / shares_total), 2)
        else:
            parte = round(neto / len(ops), 2)
        repartido += parte
        st_o = float(o.get("stake_dolares") or 0)
        pnl_o = round(parte - st_o, 2)
        o["status"] = "cerrado"
        o["resultado"] = "ganada" if pnl_o >= 0 else "perdida"
        o["pnl"] = pnl_o
        o["cerrada_manual"] = True
        o["motivo_cierre"] = motivo
        o["neto_recibido"] = parte
        o["cerrada_en_grupo"] = len(ops)
        o["cerrado_en"] = ahora_iso
        if tx:
            o["tx_cierre"] = str(tx)[:66]
    estado["trades_copiados"] = quedan
    estado.setdefault("historial", []).extend(ops)
    guardar_estado(estado)
    log(f"  [CIERRE] archivada(s) {len(ops)} op(s) · recibido ${neto:.2f} · pagado ${stake_total:.2f} · PnL conjunto ${pnl_conjunto:+.2f}")
    return pnl_conjunto


def cerrar_grupo(g, chat_id=None, dry_run=False, estado=None):
    """v12.3: CIERRA DE VERDAD una posición abierta.
    · COMBO  → RFQ con direction=SELL + orden Exchange v3 side=1 (atómico).
    · SIMPLE → orden CLOB SELL al precio actual.
    dry_run=True pide la cotización de venta y NO la acepta (coste $0).
    → (ok, detalle)."""
    ops = g["ops"]
    op0 = ops[0]
    legs = op0.get("legs") or []
    shares = sum(float(o.get("size_shares") or 0) for o in ops)
    stake = sum(float(o.get("stake_dolares") or 0) for o in ops)
    titulo = str(op0.get("question", "?"))
    n = len(ops)
    if shares <= 0:
        return False, "sin_shares"
    # v12.8.2: GUARDIA DE RESUELTA ANTES DE NADA. Con las legs ya decididas el
    # producto de mids puede dar 1.00 (todo ganado) y el bot intentaría VENDER
    # una posición que ya no cotiza: lo resuelto no se vende, se COBRA.
    r = resolver_operacion(op0)
    if r.get("resuelta"):
        g = r.get("ganada")
        log(f"  [CIERRE] posición ya resuelta (ganada={g}): no se puede vender")
        if chat_id:
            if g is True and r.get("fuente") == "cobro_real":
                enviar(chat_id, "✅ Esa posición ya está RESUELTA, GANADA y COBRADA: el dinero ya "
                                "está en tu cartera. No hay nada que vender.")
            elif g is True:
                enviar(chat_id, "✅ Esa posición ya está RESUELTA y GANADA: no se puede vender, "
                                "se COBRA. Polymarket la cobra solo en cuanto el mercado cierra; "
                                "compruébalo con /reclamar.")
            elif g is False:
                enviar(chat_id, "❌ Esa posición ya está RESUELTA y PERDIDA: su valor es 0, no hay "
                                "nada que vender. Si sigue apareciendo como abierta, /reauditar la corrige.")
            else:
                enviar(chat_id, "🏁 Esa posición ya está resuelta: no se puede vender.")
        return False, "ya_resuelta"
    vivo = vivo_de(op0)
    if vivo is not None and vivo <= 0:
        # v12.8.2: alguna leg ya perdió ⇒ el parlay no vale nada (no cotiza).
        log("  [CIERRE] combo sin valor: alguna leg ya perdió")
        if chat_id:
            enviar(chat_id, "❌ Ese combo ya tiene una leg PERDIDA: su valor es 0 y no hay nada que "
                            "vender. Si sigue como abierta en el panel, /reauditar la corrige.")
        return False, "sin_valor"
    if not vivo:
        log("  [CIERRE] sin precio vivo: no se puede dimensionar la venta")
        if chat_id:
            enviar(chat_id, "⚠️ No hay precio vivo de esta posición ahora mismo; no puedo dimensionar la venta. Inténtalo en unos minutos.")
        return False, "sin_precio_vivo"
    valor = round(shares * vivo, 2)
    log(f"[CIERRE] {titulo[:70]} · {shares:.2f} sh · mid {vivo:.3f} · valor ${valor:.2f} · dry_run={dry_run}")

    # ---------------- COMBO: RFQ SELL ----------------
    if legs:
        pids = [str(l.get("position_id")) for l in legs if l.get("position_id")]
        if len(pids) < 2:
            return False, "legs_insuficientes_para_sell"
        identidad = obtener_identidad_rfq()
        if not identidad:
            if chat_id:
                enviar(chat_id, "⚠️ Sin identidad RFQ (credenciales/proxy) — no se puede cerrar el combo.")
            return False, "sin_identidad"
        status, resp = crear_rfq(pids, valor, identidad, direction="SELL")
        log(f"  RFQ sell create -> {status} {str(resp)[:160]}")
        try:
            d = json.loads(resp)
        except Exception:
            d = {}
        if status != 200 or not isinstance(d, dict) or not d:
            return False, f"rfq_sell_http_{status}:{str(resp)[:150]}"
        err = d.get("error")
        if d.get("status") == "FAILED" or err:
            code = err.get("code") if isinstance(err, dict) else str(err)
            # v12.5: aquí NO hay reintento con menos tamaño (ni ante SIZE_TOO_LARGE):
            # vendería solo parte de la posición y dejaría el resto sin archivar.
            return False, f"rfq_sell_{code or 'failed'}"
        quote = d.get("quote") or {}
        req = d.get("request") or {}
        rfq_id = d.get("rfq_id")
        quote_id = quote.get("quote_id")
        try:
            blended = int(quote.get("blended_price_e6", 0)) / 1e6
            neto = int(quote.get("net_receive_e6", 0)) / 1e6
            total_req = int(quote.get("total_required_e6", 0)) / 1e6
        except Exception:
            return False, f"quote_sell_ilegible:{str(quote)[:120]}"
        if neto <= 0:
            return False, f"neto_recibido_0:{str(quote)[:120]}"
        precio_venta = neto / shares if shares else 0
        pnl_est = round(neto - stake, 2)
        log(f"  quote sell: neto=${neto:.2f} blended={blended:.3f} precio_venta={precio_venta:.3f} (mid {vivo:.3f}) total_req={total_req:.2f}")
        # guarda: no regalar la posición por una cotización pésima
        if precio_venta < 0.60 * vivo:
            log(f"  NO acepto venta: {precio_venta:.3f} < 60% del mid {vivo:.3f}")
            if chat_id:
                enviar(chat_id, f"⚠️ *Cotización de venta demasiado baja*\n📌 {titulo[:80]}\nOfrecen ${precio_venta:.3f}/sh frente a un precio actual de {vivo:.3f} (<60%). No vendo: prueba en unos minutos.")
            return False, f"precio_venta_bajo_{precio_venta:.3f}"
        if dry_run:
            log("  dry-run: quote de venta OK, NO se acepta (coste $0)")
            if chat_id:
                enviar(chat_id, f"🧪 *TEST CIERRE OK* (sin vender, $0)\n📌 {titulo[:90]}\n"
                                f"📦 {shares:.2f} sh · precio actual {vivo:.3f} · valor ${valor:.2f}\n"
                                f"💵 Recibirías: *${neto:.2f}* (${precio_venta:.3f}/sh)\n"
                                f"💰 Pagaste ${stake:.2f} → PnL *${pnl_est:+.2f}*\n"
                                f"rfq `{str(rfq_id)[:18]}`")
            return True, {"dry_run": True, "neto": round(neto, 2), "pnl": pnl_est, "rfq_id": rfq_id}
        try:
            signed = firmar_orden_v3(req, quote, identidad, side=1)   # side 1 = SELL
        except Exception as e:
            log(f"  firma v3 (sell) error: {e}")
            return False, f"firma_v3_sell:{str(e)[:150]}"
        status, resp = aceptar_rfq(rfq_id, quote_id, signed, identidad)
        log(f"  RFQ sell accept -> {status} {str(resp)[:160]}")
        try:
            da0 = json.loads(resp)
        except Exception:
            da0 = {}
        code0 = (da0.get("error") or {}).get("code") if isinstance(da0, dict) else None
        if status == 503 or code0 in ("PRE_EXECUTION_BALANCE_RESERVATION_FAILED",
                                      "SERVICE_UNAVAILABLE", "TRADE_SUBMISSION_FAILED"):
            log(f"  accept sell transitorio ({status}/{code0}): reintento único en 6s")
            time.sleep(6)
            status, resp = aceptar_rfq(rfq_id, quote_id, signed, identidad)
            log(f"  RFQ sell accept retry -> {status} {str(resp)[:160]}")
        if status != 200:
            return False, f"accept_sell_http_{status}:{str(resp)[:150]}"
        try:
            da = json.loads(resp)
        except Exception:
            da = {}
        if isinstance(da, dict) and da.get("status") == "FAILED":
            e2 = da.get("error") or {}
            return False, f"accept_sell_{e2.get('code') if isinstance(e2, dict) else e2}"
        st, ultimo = esperar_fill(rfq_id, identidad)
        tx = ultimo.get("tx_hash", "") if isinstance(ultimo, dict) else ""
        log(f"  RFQ sell status final: {st} tx={str(tx)[:26]}")
        if st not in ("FILLED", "CONFIRMED"):
            if chat_id:
                enviar(chat_id, f"⏳ *Cierre aceptado pero sin confirmar* ({st})\n📌 {titulo[:70]}\nConsulta /fills para confirmar.")
            return False, f"cierre_pendiente_{st}"
        if estado is None:
            estado = cargar_estado()
        pnl = archivar_cierre(ops, neto, estado, motivo="cerrada_rfq_sell", tx=tx)
        if chat_id:
            enviar(chat_id, f"🔒 *POSICIÓN CERRADA* {'🟢' if pnl >= 0 else '🔴'}\n📌 {titulo[:90]}\n"
                            f"💵 Recibido ${neto:.2f} (${precio_venta:.3f}/sh × {shares:.2f})\n"
                            f"💰 Pagaste ${stake:.2f} → PnL *${pnl:+.2f}*\n🔗 tx `{str(tx)[:24]}`")
        return True, {"oid": rfq_id, "status": st, "neto": round(neto, 2), "pnl": pnl}

    # ---------------- SIMPLE: orden CLOB SELL ----------------
    token = op0.get("real_token") or op0.get("condition_id")
    if not token:
        return False, "sin_token_para_vender"
    precio_venta = round(min(max(vivo - 0.01, 0.02), 0.98), 2)   # un tick por debajo del mid para que cruce
    if dry_run:
        neto_est = round(precio_venta * shares, 2)
        pnl_est = round(neto_est - stake, 2)
        log(f"  dry-run: venta CLOB simulada a {precio_venta} x {shares:.2f} sh = ${neto_est:.2f} (NO se envía)")
        if chat_id:
            enviar(chat_id, f"🧪 *TEST CIERRE OK* (simple, sin vender, $0)\n📌 {titulo[:90]}\n"
                            f"📦 {shares:.2f} sh · precio actual {vivo:.3f} · valor ${valor:.2f}\n"
                            f"💵 Recibirías ~*${neto_est:.2f}* (venta a ${precio_venta:.2f}/sh)\n"
                            f"💰 Pagaste ${stake:.2f} → PnL *${pnl_est:+.2f}*")
        return True, {"dry_run": True, "neto": neto_est, "pnl": pnl_est}
    ok, res = vender_clob(token, precio_venta, shares)
    if not ok:
        log(f"  [CIERRE] venta CLOB rechazada: {res}")
        if chat_id:
            enviar(chat_id, f"❌ *No se pudo cerrar*\n📌 {titulo[:80]}\nMotivo: `{str(res)[:90]}`")
        return False, str(res)
    neto = round(precio_venta * shares, 2)
    if estado is None:
        estado = cargar_estado()
    pnl = archivar_cierre(ops, neto, estado, motivo="cerrada_clob_sell", tx=str(res.get("oid", ""))[:66])
    if chat_id:
        enviar(chat_id, f"🔒 *POSICIÓN CERRADA (venta CLOB)* {'🟢' if pnl >= 0 else '🔴'}\n📌 {titulo[:90]}\n"
                        f"💵 {shares:.2f} sh @ ${precio_venta:.2f} → ${neto:.2f}\n"
                        f"💰 Pagaste ${stake:.2f} → PnL *${pnl:+.2f}*\n🆔 `{str(res.get('oid'))[:18]}`")
    return True, {"oid": res.get("oid"), "neto": neto, "pnl": pnl}


def cerrar_desde_boton(h8, chat_id, dry_run=False):
    """v12.3: 🔒 del panel ABIERTAS → cierra esa posición. Hilo propio
    SERIALIZADO con el auto_loop (PASADA_LOCK) para no pisar una pasada."""
    hit = ABIERTAS_CACHE.get(h8)
    if not hit or time.time() - hit[0] > 3600:
        return enviar(chat_id, "⚠️ Panel caducado: pulsa 📂 Abiertas otra vez y vuelve a intentar el cierre.")
    clave = hit[1]

    def _run():
        try:
            with PASADA_LOCK:
                estado, grupos = grupos_abiertos_actuales()
                g = None
                for x in grupos:
                    if clave_grupo(x) == clave:
                        g = x
                        break
                if not g:
                    return enviar(chat_id, "ℹ️ Esa posición ya no está abierta (se resolvió o ya se cerró). Pulsa 📂 Abiertas para ver el estado actual.")
                titulo = str(g["ops"][0].get("question", "?"))[:80]
                if not dry_run:
                    enviar(chat_id, f"🔒 *CERRANDO POSICIÓN*\n📌 {titulo}\n_Pidiendo cotización de venta…_")
                ok, res = cerrar_grupo(g, chat_id=chat_id, dry_run=dry_run, estado=estado)
                if not ok and not str(res).startswith("cierre_pendiente"):
                    log(f"  [CIERRE] fallo: {str(res)[:120]}")
                    if not dry_run:
                        enviar(chat_id, f"❌ *Cierre no ejecutado*\n📌 {titulo}\nMotivo: `{str(res)[:90]}`")
        except Exception as e:
            log(f"[CIERRE] error: {e}")
            try:
                enviar(chat_id, f"❌ Error cerrando la posición: {str(e)[:90]}")
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()


def render_grupo(g, num=None):
    """v12.1: UNA línea por posición única: título entero, ×N si hay fills
    duplicados, precio actual, probabilidad viva, valor vs pago y consejo.
    v12.3: el ESTADO va A LA DERECHA de cada línea (✅ ganada / ❌ perdida /
    ⏳ en juego) y cada posición se numera (#1, #2…) para casar con los 🔒."""
    ops = g["ops"]
    op0 = ops[0]
    n = len(ops)
    stake = sum(float(o.get("stake_dolares") or 0) for o in ops)
    shares = sum(float(o.get("size_shares") or 0) for o in ops)
    r = resolver_operacion(op0)
    es_combo = bool(op0.get("legs"))
    fr = franja_of(op0)
    ico = {"extendida": "🚀🎫", "super": "💥🎫"}.get(fr, "🎫" if es_combo else "🎯")
    titulo = str(op0.get("question", "?"))[:240]
    # v12.3: icono de estado A LA DERECHA de la línea de la apuesta
    if r.get("resuelta"):
        der = "  ✅" if r.get("ganada") else "  ❌"
    else:
        der = "  ⏳"
    pref = f"#{num} · " if num else ""
    txt = f"{ico} {pref}{titulo}"
    if n > 1:
        txt += f"  ×{n}"
    txt += der
    txt += f"\n   ${stake:.2f}"
    cuota = op0.get("cuota_ejecutada") or 0
    if cuota:
        txt += f" · cuota {float(cuota):.2f}"
    if shares > 0:
        txt += f" · {shares:.2f} sh"
    if r.get("fin"):
        txt += f" · 🏁 fin {r['fin']}"
    txt += "\n"
    # v12.8.3: situación REAL (viva/suspendida/anulada/resuelta/muerta) + último
    # precio publicado cuando el libro está cerrado (/midpoint da 404).
    sit_cl, sit_tx = situacion_op(op0)
    if sit_cl in ("suspendida", "anulada", "muerta", "sin_datos"):
        txt += f"   {sit_tx}\n"
    vivo, fte_precio = precio_vivo_op(op0)
    if vivo and shares > 0:
        valor = shares * vivo
        payout = shares
        etiqueta = "📈 precio ahora" if fte_precio == "mid" else "📈 últ. precio (libro cerrado)"
        txt += (f"   {etiqueta} {vivo:.3f} (~{vivo * 100:.0f}%) · "
                f"valor ${valor:.2f} vs pago ${payout:.2f}\n")
        if sit_cl in ("suspendida", "muerta"):
            txt += f"   ⏸ No se puede vender ahora ({_din(valor - stake)} latente)\n"
        elif payout > 0 and valor >= 0.90 * payout:
            txt += f"   💰 CERRAR anticipado aseguraría ~{_din(valor - stake)} (≥90% del pago)\n"
        elif valor <= 0.55 * stake:
            txt += f"   🔴 Muy caída ({_din(valor - stake)}) — plantéate cortar\n"
        else:
            txt += f"   🟢 Mantener ({_din(valor - stake)} latente)\n"
    else:
        # v12.8.2: "n/d" a secas confundía — si ya está resuelta no cotiza
        if r.get("resuelta"):
            txt += "   📈 precio ahora: n/d (posición resuelta: ya no cotiza)\n"
        elif sit_cl == "suspendida":
            txt += "   📈 precio ahora: n/d (mercado suspendido: sin libro)\n"
        else:
            txt += "   📈 precio ahora: n/d\n"
    if es_combo:
        for q, gg in r.get("detalle", []):
            gi = "⏳" if gg is None else ("✅" if gg else "❌")
            txt += f"   {str(q)[:160]} {gi}\n"
    if op0.get("status") == "pendiente":
        txt += "   ⏳ fill por confirmar (/fills)\n"
    return txt + "\n"


def render_abierta(op):
    """Una línea de operación abierta con detalle de legs y hora de fin."""
    r = resolver_operacion(op)
    stake = float(op.get("stake_dolares") or 0)
    cuota = op.get("cuota_ejecutada") or 0
    es_combo = bool(op.get("legs"))
    fr_op = franja_of(op)
    ico_op = {"extendida": "🚀🎫", "super": "💥🎫"}.get(fr_op, "🎫" if es_combo else "🎯")
    txt = f"{ico_op} {str(op.get('question', '?'))[:58]}\n   ${stake:.2f}"
    if cuota:
        txt += f" · cuota {float(cuota):.2f}"
    if r.get("fin"):
        txt += f" · 🏁 fin {r['fin']}"
    txt += "\n"
    if es_combo:
        for q, g in r.get("detalle", []):
            gi = "⏳" if g is None else ("✅" if g else "❌")
            txt += f"   {gi} {str(q)[:48]}\n"
    if op.get("status") == "pendiente":
        txt += "   ⏳ fill por confirmar (/fills)\n"
    return txt + "\n"


# ============================================
# COMANDOS
# ============================================
def cmd_start(chat_id):
    texto = (f"🤖 *POLY COMBOS BOT v12.9.0*\n\n"
             f"Modo: *{MODO_OPERACION}*\n"
             f"Stake: *{stake_txt()}*\n"
             f"🔢 Máx ops/día: *{max_ops()}*\n"
             f"Cuota: *{CUOTA_MIN}-{CUOTA_MAX}*\n\n"
             f"📌 *Estrategia v11* (COMBOS REALES):\n"
             f"   · Construye parlays de 2-3 legs deportivos\n"
             f"   · Pide quote a market makers (RFQ oficial)\n"
             f"   · Solo acepta si la cuota real entra en rango\n"
             f"   · Fill confirmado con tx_hash (FILLED)\n"
             f"   · Sin repetir legs (cooldown {COOLDOWN_LEG_H:.0f}h) · tope {max_ops()}/día (🔢)\n\n"
             f"🤖 AUTO = solo base ({CUOTA_MIN}-{CUOTA_MAX}) · el tope 🔢 cuenta todas las ops\n"
             f"🚀 Extendidas (≤{CUOTA_MAX_EXT}) y 💥 Súper (≥{SUPER_CUOTA_MIN:.0f}): SOLO botones manuales, cupos {MAX_EXT_DIA}+{MAX_SUPER_DIA}/día, estadísticas aparte\n"
             f"💵 Stake AUTO ${STAKE_MIN_AUTO:.0f}-${STAKE_MAX_AUTO:.0f} — decide el bot según la cuota y cómo va la combinada (botones 💵 para fijarlo)\n"
             f"🔢 Máx ops/día ({max_ops()} ahora) — desde {OPS_PIN_DESDE} exige código de 4 cifras 🔐\n"
             f"🎯 Prob AUTO ({prob_nivel_txt(prob_min_auto())} ahora) — si no llega, se descarta y pasa al siguiente\n"
             f"🔒 Botones en 📂 Abiertas — cierran la posición DE VERDAD (combos por RFQ SELL, simples por CLOB) · /testcerrar = gratis\n"
             f"⏩ Botones ⏱ — intervalo entre pasadas ({INTERVALO_AUTO_S // 60} min ahora) · el ACTIVO lleva ✅\n"
             f"🔍 *Leer ahora* — lectura inmediata (bankroll, catálogo, qué abriría y estado real de cada posición). SÓLO MIRAR: no abre ni vende nada · /leer\n"
             f"🟡 *SEMI* — busco y te PROPONGO el combo con ✅ Aceptar / ❌ Descartar (caduca a los {int(PROPUESTA_VALIDA_S // 60)} min). Nada se compra sin tu ✅\n"
             f"🏆 *Top* — ranking REAL de Polymarket (lb-api) con botones 24 h / 7 días / 30 días / histórico y la wallet de cada trader. Ya no es una lista escrita a mano\n"
             f"📡 *Copy* — FASE 1 EN PAPEL ($0): vigilo los fills de los {COPY_N_TRADERS} mejores filtrados (fuera market makers, inactivos y concentrados) y anoto cada compra como señal con su precio y el nuestro; /copy da acierto, ROI y desglose por trader. No compro nada todavía\n"
             f"⚖️ Ventaja mínima *{int(VENTAJA_MIN_EV * 100)}%*: sólo compra si la cotización real mejora el mercado (prob × cuota ≥ {1 + VENTAJA_MIN_EV:.2f}). Vale en 🟢 AUTO y 🟡 SEMI; los botones 🚀/💥 siempre operan\n"
             f"🧪 /testcombo — prueba gratis (quote sin aceptar)\n"
             f"🩺 Auto-curación ACTIVA: cada {AUDITORIA_CADA_H:.0f}h (y al arrancar) contrasta ✅ Cerradas con la realidad de Polymarket y corrige sola · /reauditar = a mano\n"
             f"💰 /reclamar — ganadas SIN cobrar: cuánto hay pendiente, enlace al evento y cómo cobrarlo (el bot no puede redimir parlays: el adaptador es sólo para la cuenta de Polymarket)\n"
             f"🔎 /fills — fills reales de la wallet\n"
             f"📊 /stats — estadisticas")
    return enviar(chat_id, texto)

def cmd_trades(chat_id):
    """📋 v12.0: catálogo informativo BASE + 🚀 EXTENDIDA (manual), un mensaje
    por combo con SU botón ▶️ debajo. Operaciones: 📂 Abiertas / ✅ Cerradas."""
    legs = listar_combos()
    if not legs:
        return enviar(chat_id, "❌ No hay catálogo de combos disponible ahora mismo.")
    cands = generar_combos_catalogo(legs, 10)
    if not cands:
        return enviar(chat_id, f"📋 *COMBOS POSIBLES*\n_Ahora mismo ningún combo cae en cuota {CUOTA_MIN}-{CUOTA_MAX_EXT}._\n\n"
                               f"💥 SúperCombos (cuota ≥{SUPER_CUOTA_MIN:.0f}) → su botón\n📂/✅ → tus operaciones")
    cabecera = (f"📋 *TOP {len(cands)} COMBOS POSIBLES* 🎰\n"
                f"_🤖 base {CUOTA_MIN}-{CUOTA_MAX} · 🚀 extendida ≤{CUOTA_MAX_EXT} (manual {MAX_EXT_DIA}/día) · tope {max_ops()}/día · por volumen $_\n"
                f"_Un mensaje por combo, con su botón ▶️ debajo_")
    cierre = ("_Prob = producto de precios (implícita): a más cuota, menos probabilidad._\n"
              f"▶️ Botón = ejecutar ESE combo ya vía RFQ (stake {stake_txt()}, anti-duplicados)\n"
              f"💥 SúperCombos (cuota ≥{SUPER_CUOTA_MIN:.0f}) → su botón\n"
              "📂 Abiertas / ✅ Cerradas → tus operaciones")
    enviar_catalogo(chat_id, cands, "ej", cabecera, cierre)
    # v12.2: ajustes rápidos — stake y tope diario
    _kb = {"inline_keyboard": [[
        {"text": "💵 Stake: " + ("AUTO $5-10" if str(cargar_estado().get("stake_mode", "AUTO")).upper() == "AUTO" else f"FIJO ${STAKE_POR_TRADE:.0f}"),
         "callback_data": "st:menu"},
        {"text": f"🔢 Máx/día: {max_ops()}", "callback_data": "mx:menu"}]]}
    enviar(chat_id, "⚙️ _Ajustes rápidos:_", _kb)


def cmd_super(chat_id):
    """💥 v12.0: SÚPER combos (cuota ≥5, 3-5 legs) — informativos, ejecución
    SOLO manual con su botón, cupo y estadísticas aparte. Máx 10."""
    legs = listar_combos()
    if not legs:
        return enviar(chat_id, "❌ No hay catálogo disponible ahora mismo.")
    cands = generar_super_catalogo(legs, 10)
    if not cands:
        return enviar(chat_id, f"💥 *SÚPERCOMBOS*\n_Ahora mismo ningún combo de {SUPER_LEGS[0]}-{SUPER_LEGS[1]} legs alcanza"
                               f" cuota ≥{SUPER_CUOTA_MIN:.0f} (legs p ≥{SUPER_P_MIN})._\n\nℹ️ Solo manuales · cupo {MAX_SUPER_DIA}/día · estadísticas aparte")
    cabecera = (f"💥 *TOP {len(cands)} SÚPERCOMBOS* 🎰\n"
                f"_cuota ≥{SUPER_CUOTA_MIN:.0f} · {SUPER_LEGS[0]}-{SUPER_LEGS[1]} legs · prob ~{100 / SUPER_CUOTA_MAX:.0f}-{100 / SUPER_CUOTA_MIN:.0f}% · por volumen $_\n"
                f"_SOLO MANUALES (no entran en AUTO) · cupo {MAX_SUPER_DIA}/día · estadísticas aparte_")
    cierre = (f"⚠️ Cuota muy alta = probabilidad baja (lotería de {stake_txt()})\n"
              "▶️ Botón = ejecutar ESE súper combo ya vía RFQ")
    enviar_catalogo(chat_id, cands, "sp", cabecera, cierre)

def cmd_saldo(chat_id):
    env = cargar_env()
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET)
    rpcs = ["https://polygon-rpc.com", "https://1rpc.io/matic"]
    tokens = [
        ("pUSD",   "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB", 6),
        ("USDC.e", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", 6),
        ("USDC",   "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6),
    ]
    data = "0x70a08231" + "0" * 24 + wallet.lower()[2:]
    saldos = {}
    for simbolo, contrato, dec in tokens:
        saldos[simbolo] = 0.0
        for rpc in rpcs:
            try:
                body = json.dumps({"jsonrpc": "2.0", "method": "eth_call",
                                   "params": [{"to": contrato, "data": data}, "latest"], "id": 1})
                out = subprocess.run(
                    ["curl", "-s", "--max-time", "8", "-X", "POST", rpc,
                     "-H", "Content-Type: application/json", "-d", body],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=12).stdout
                r = json.loads(out)
                if "result" in r and r["result"] not in ("0x", "0x0", None):
                    saldos[simbolo] = int(r["result"], 16) / (10 ** dec)
                    break
            except: continue
    cash = sum(saldos.values())
    texto = f"💰 *SALDO*\n\n*Cash:* ${cash:.2f}\n"
    for tok, val in saldos.items():
        texto += f"   {tok}: ${val:.2f}\n"
    return enviar(chat_id, texto)

def cmd_stats(chat_id):
    s = calcular_stats()
    total = s["wins"] + s["losses"]
    wr = (s["wins"]/total*100) if total > 0 else 0
    _anu = s.get("anuladas", 0)          # ↩️ v12.8.3
    roi = (s["pnl"]/s["stake"]*100) if s["stake"] > 0 else 0
    texto = f"📊 *ESTADÍSTICAS*\n\n"
    texto += f"Operaciones: {s['total']}\n"
    if total > 0:
        texto += (f"Cerradas: {total} (✅{s['wins']} ❌{s['losses']})"
                  + (f" · ↩️{_anu} anuladas/devueltas" if _anu else "") + "\n")
        texto += f"Win rate: *{wr:.1f}%*\n"
        texto += f"PnL: *${s['pnl']:+.2f}*\n"
        texto += f"Stake: ${s['stake']:.2f}\n"
        texto += f"ROI: *{roi:+.1f}%*\n"
        pf = s.get("por_franja", {})
        texto += "\n_Por franja:_\n"
        for nombre, fr in (("🤖 Base/AUTO", "base"), ("🚀 Extendidas", "extendida"), ("💥 Súper", "super")):
            d = pf.get(fr) or {"ops": 0, "wins": 0, "pnl": 0.0}
            texto += f"{nombre}: {d['ops']} ops · ✅{d['wins']} · PnL ${d['pnl']:+.2f}\n"
    # 🧮 v12.8.4: cuántas victorias compensan una derrota, con TU libro real
    if s["wins"] and s["losses"] and s["pnl_wins"] > 0 and s["pnl_losses"] < 0:
        _mw = s["pnl_wins"] / s["wins"]              # media ganada (+)
        _ml = -s["pnl_losses"] / s["losses"]         # media perdida (+)
        _sw = (s["stake_wins"] / s["wins"]) if s["wins"] else 0.0
        _wr_eq = (_ml / (_mw + _ml) * 100) if (_mw + _ml) > 0 else 0.0
        _wr_tu = s["wins"] / (s["wins"] + s["losses"]) * 100
        texto += ("\n🧮 *CUENTAS DE COMPENSACIÓN* (tu libro real)\n"
                  f"Media por ganada: *+${_mw:.2f}* ({s['wins']} ops)\n"
                  f"Media por pérdida: *-${_ml:.2f}* ({s['losses']} ops)\n"
                  f"⇒ *{_ml / _mw:.2f} victorias* por cada derrota\n"
                  f"Win-rate de equilibrio: *{_wr_eq:.1f}%* · el tuyo: *{_wr_tu:.1f}%* "
                  + ("✅ por encima\n" if _wr_tu >= _wr_eq else "❌ por debajo\n"))
        if _sw > 0:
            _t = []
            for _q in (1.5, 2.0, 2.5):
                _b = _sw * (_q - 1)
                _t.append(f"cuota {_q:.1f} → {_ml / _b:.1f}" if _b > 0 else f"cuota {_q:.1f} → ∞")
            texto += (f"_Victorias para recuperar una derrota media (-${_ml:.2f}) "
                      f"apostando ${_sw:.2f}: " + " · ".join(_t) + "_\n")
        texto += (f"_Sólo se compra con ventaja: prob × cuota ≥ {1 + VENTAJA_MIN_EV:.2f} "
                  f"(filtro activo en 🟢 AUTO y 🟡 SEMI)_\n")
    if s["mejor"]:
        m = s["mejor"]
        texto += f"\n🏆 Mejor: {m.get('question','?')[:40]} → ${m.get('pnl',0):+.2f}\n"
    if s["peor"]:
        m = s["peor"]
        texto += f"💀 Peor: {m.get('question','?')[:40]} → ${m.get('pnl',0):+.2f}\n"
    if s["total"] == 0:
        texto += "\n_Aún no hay operaciones. Espera la próxima pasada AUTO._"
    return enviar(chat_id, texto)

def enviar_largo(chat_id, texto, limite=3900):
    """v12.2: Telegram corta mensajes >4096 chars — los paneles largos se
    dividen en varios mensajes para que los títulos salgan ENTEROS."""
    if len(texto) <= limite:
        return enviar(chat_id, texto)
    bloques = texto.split("\n\n")
    partes = []
    cur = ""
    for b in bloques:
        cand = (cur + "\n\n" + b) if cur else b
        if len(cand) <= limite:
            cur = cand
        else:
            if cur:
                partes.append(cur)
            cur = b
    if cur:
        partes.append(cur)
    total = len(partes)
    for i, p in enumerate(partes, 1):
        cab = f"_{i}/{total}_" if total > 1 else ""
        enviar(chat_id, (cab + "\n" + p) if cab else p)


def cmd_abiertas(chat_id):
    """📂 v11.5: abiertas reales (single + combos) con hora de fin; sincroniza."""
    try:
        abiertas, _, _ = sincronizar_operaciones()
    except Exception:
        abiertas = cargar_estado().get("trades_copiados", [])
    abiertas = [o for o in abiertas if o.get("status") != "fallido"
                and str(o.get("question", "")).strip() not in ("", "?")
                and (float(o.get("stake_dolares") or 0) > 0 or o.get("legs"))]
    if not abiertas:
        return enviar(chat_id, "📭 Sin operaciones abiertas (las resueltas pasan a ✅ Cerradas).")
    grupos = agrupar_abiertas(abiertas)   # v12.1: sin duplicados
    extra = f" · {len(abiertas)} fills" if len(abiertas) != len(grupos) else ""
    texto = f"📂 *ABIERTAS ({len(grupos)} posiciones{extra})*"
    for i, g in enumerate(grupos[:12], 1):
        texto += "\n\n" + render_grupo(g, i).rstrip("\n")
    texto += ("\n\n_A la derecha: ✅ ganada · ❌ perdida · ⏳ en juego_"
              "\n_⏸ SUSPENDIDO = mercado sin libro (no se puede vender ni resolver; se muestra la fecha prevista)_"
              "\n_↩️ ANULADO = cerrado sin ganador: los tokens se devuelven a ~$0.50_")
    enviar_largo(chat_id, texto)
    # v12.3: un botón 🔒 por posición para CERRARLA de verdad
    filas = []
    for i, g in enumerate(grupos[:12], 1):
        cl = clave_grupo(g)
        h8 = h8_clave(cl)
        ABIERTAS_CACHE[h8] = (time.time(), cl)
        op0 = g["ops"][0]
        sh = sum(float(o.get("size_shares") or 0) for o in g["ops"])
        vivo = vivo_de(op0)
        val = f" · ~${sh * vivo:.2f}" if vivo else ""
        filas.append([{"text": f"🔒 #{i} · {str(op0.get('question', '?'))[:24]}{val}",
                       "callback_data": f"cc:{h8}"}])
    _prune_abiertas()
    return enviar(chat_id, "🔒 *CERRAR POSICIÓN* — vende ya al mercado y cobras su valor actual:\n"
                           "_Elige la línea que quieras cerrar (los números casan con el panel)_\n"
                           "_🧪 /testcerrar N pide la cotización SIN vender ($0)_",
                  {"inline_keyboard": filas})

def cmd_testcerrar(chat_id, texto=""):
    """🧪 v12.3: pide la cotización de VENTA de una posición abierta SIN
    aceptarla (coste $0). Valida el cierre real antes de usar el botón 🔒."""
    def _run():
        try:
            estado, grupos = grupos_abiertos_actuales()
            if not grupos:
                return enviar(chat_id, "🧪 No hay posiciones abiertas que cerrar.")
            nums = "".join(ch for ch in str(texto) if ch.isdigit())
            idx = 0
            if nums:
                idx = max(0, min(int(nums) - 1, len(grupos) - 1))
            cerrar_grupo(grupos[idx], chat_id=chat_id, dry_run=True, estado=estado)
        except Exception as e:
            log(f"testcerrar error: {e}")
            enviar(chat_id, f"🧪 Error: {str(e)[:150]}")
    threading.Thread(target=_run, daemon=True).start()
    return enviar(chat_id, "🧪 Pidiendo cotización de venta (sin aceptar, $0)…")


def cmd_cerrar(chat_id, texto=""):
    """🔒 v12.3: cierra DE VERDAD la posición nº N de 📂 Abiertas. Exige el
    número para evitar cierres accidentales (también vale el botón 🔒)."""
    nums = "".join(ch for ch in str(texto) if ch.isdigit())
    if not nums:
        return enviar(chat_id, "❌ Indica el número de la posición: */cerrar 1*\n"
                               "_(los números salen en 📂 Abiertas, y también tienes el botón 🔒 debajo de cada línea)_")

    def _run():
        try:
            with PASADA_LOCK:
                estado, grupos = grupos_abiertos_actuales()
                if not grupos:
                    return enviar(chat_id, "ℹ️ No hay posiciones abiertas.")
                idx = max(0, min(int(nums) - 1, len(grupos) - 1))
                g = grupos[idx]
                enviar(chat_id, f"🔒 *CERRANDO POSICIÓN #{idx + 1}*\n📌 {str(g['ops'][0].get('question', '?'))[:80]}\n_Pidiendo cotización de venta…_")
                ok, res = cerrar_grupo(g, chat_id=chat_id, dry_run=False, estado=estado)
                if not ok and not str(res).startswith("cierre_pendiente"):
                    # v12.8.2: el motivo en cristiano (antes salía el código crudo)
                    MOT = {"ya_resuelta": "la posición ya está resuelta — no se vende, se cobra",
                           "sin_valor": "el combo ya tiene una leg perdida (su valor es 0)",
                           "sin_precio_vivo": "sin cotización en este momento (reintentable)",
                           "sin_shares": "sin shares registradas",
                           "legs_insuficientes_para_sell": "faltan legs para venderla por RFQ"}
                    mot = MOT.get(str(res)) or f"`{str(res)[:90]}`"
                    enviar(chat_id, f"❌ *Cierre no ejecutado*\nMotivo: {mot}")
        except Exception as e:
            log(f"cerrar error: {e}")
            enviar(chat_id, f"❌ Error cerrando: {str(e)[:120]}")
    threading.Thread(target=_run, daemon=True).start()
    return enviar(chat_id, f"🔒 Cerrando la posición nº {nums}…")


def programar_auditoria_inicial():
    """v12.7: fija NEXT_AUDITORIA_TS según la última auditoría guardada: si ya
    corrió hace poco (reinicios seguidos) no la repite; si es la primera vez,
    la lanza a los AUDITORIA_ARRANQUE_S segundos."""
    global NEXT_AUDITORIA_TS
    try:
        ult = cargar_estado().get("ultima_auditoria")
        if ult:
            dt = datetime.fromisoformat(str(ult).replace("Z", "+00:00"))
            hace = time.time() - dt.timestamp()
            if hace < AUDITORIA_MIN_ENTRE_S:
                NEXT_AUDITORIA_TS = time.time() + max(60, AUDITORIA_CADA_S - hace)
                log(f"  auto-curación: la última fue hace {hace / 60:.0f} min → próxima en "
                    f"{(NEXT_AUDITORIA_TS - time.time()) / 3600:.1f}h")
                return
        NEXT_AUDITORIA_TS = time.time() + AUDITORIA_ARRANQUE_S
        log(f"  auto-curación: primera auditoría en {AUDITORIA_ARRANQUE_S}s "
            f"(después cada {AUDITORIA_CADA_H:.0f}h)")
    except Exception as e:
        NEXT_AUDITORIA_TS = time.time() + AUDITORIA_ARRANQUE_S
        log(f"  auto-curación: programada sin histórico ({str(e)[:60]})")


def _aud_dentro_rango(op):
    """v12.7: sólo se re-auditan ops de los últimos AUDITORIA_DIAS_MAX días."""
    for k in ("copiado_en", "cerrado_en"):
        v = op.get(k)
        if not v:
            continue
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).days <= AUDITORIA_DIAS_MAX
        except Exception:
            continue
    return True


def reauditar_estado(chat_id=None, aplicar=True, con_saldo=False, origen="manual",
                     silencioso=False):
    """🩺 v12.6/v12.7 — NÚCLEO de la re-auditoría: contrasta TODAS las ops con
    la realidad de Polymarket y corrige el estado.
      · Archivadas que siguen EN JUEGO → vuelven a 📂 Abiertas.
      · Resultado/PnL mal calculados → se corrigen (se guarda el valor anterior).
      · Cierres manuales 🔒 → intactos.
      · Abiertas ya resueltas de verdad → se cierran con su PnL real.
    Verdad real = cobros REDEEM de la wallet (data-api) + ganador por OUTCOME de
    cada leg + (opcional) saldo on-chain del token de combo.
    aplicar=False ⇒ sólo informa. silencioso=True ⇒ sólo avisa si cambió algo.
    → {"reabiertas", "corregidas", "confirmadas", "manuales", "nuevas_cerradas",
       "pnl_antes", "pnl_despues", "stats", "texto"}."""
    estado = cargar_estado()
    # 🧹 v12.8.3: ANTES de resolver nada, limpiar Abiertas (basura + duplicados
    # fantasma sin fill real en cadena) y recalcular el reparto de los cobros con
    # la lista YA limpia (si no, cada fill fantasma se llevaría su parte).
    _limpias, _cura = curar_abiertas(estado, aplicar=aplicar)
    _reparto_mapa(estado, forzar=True)
    hist = estado.get("historial", []) or []
    abiertas = estado.get("trades_copiados", []) or []
    pnl_antes_total = round(sum(float(o.get("pnl") or 0) for o in hist), 2)
    reabiertas, corregidas, confirmadas, nuevas_cerr = [], [], [], []
    manuales = fuera_rango = sin_datos = 0
    nueva_hist = []
    for op in hist:
        if op.get("cerrada_manual") or str(op.get("motivo_cierre") or "").startswith("cerrada"):
            manuales += 1
            nueva_hist.append(op)
            continue
        if not _aud_dentro_rango(op):
            fuera_rango += 1
            nueva_hist.append(op)
            continue
        pnl_antes = op.get("pnl")
        res_antes = op.get("resultado")
        r = resolver_operacion(op)
        if not r.get("resuelta"):
            if r.get("sin_datos"):
                # v12.7: el CLOB no dio datos de alguna leg (caída/429) ⇒ NO se
                # toca: reabrir aquí sería inventarse un estado con datos a medias
                sin_datos += 1
                nueva_hist.append(op)
                continue
            # ⏳ sigue en juego: NO debía estar en ✅ Cerradas
            op["pnl_antes_auditoria"] = pnl_antes
            op["resultado_antes"] = res_antes
            for k in ("resultado", "pnl", "cerrado_en", "fin_real"):
                op.pop(k, None)
            op["status"] = "filled" if op.get("tx_hash") else (op.get("status") or "filled")
            op["pendiente_info"] = r.get("pendiente_info")
            if con_saldo:
                _sal = verdad_real(op, con_saldo=True).get("saldo")
                if _sal is not None:
                    op["saldo_tokens"] = round(float(_sal), 6)
            if r.get("fin"):
                op["fin_previsto"] = r["fin"]
            op["reauditada"] = datetime.now(timezone.utc).isoformat()
            reabiertas.append(op)
            continue
        res_ahora = ("anulada" if r.get("anulada")        # ↩️ v12.8.3
                     else ("ganada" if r.get("ganada") else "perdida"))
        pnl_ahora = float(r.get("pnl") or 0)
        if res_ahora != res_antes or abs(pnl_ahora - float(pnl_antes or 0)) > 0.005:
            op["resultado_antes"] = res_antes
            op["pnl_antes"] = pnl_antes
            op["resultado"] = res_ahora
            op["pnl"] = r.get("pnl")
            op["fin_real"] = r.get("fin") or op.get("fin_real")
            op["fuente_verdad"] = r.get("fuente")
            if r.get("cobro_real"):
                op["cobro_real"] = r["cobro_real"]
            op["reauditada"] = datetime.now(timezone.utc).isoformat()
            corregidas.append(op)
        else:
            op["fuente_verdad"] = r.get("fuente") or op.get("fuente_verdad")
            confirmadas.append(op)
        nueva_hist.append(op)
    quedan_ab = []
    for op in abiertas:
        if op.get("status") == "fallido":
            quedan_ab.append(op)
            continue
        r = resolver_operacion(op)
        if r.get("resuelta"):
            op["status"] = "cerrado"
            op["resultado"] = ("anulada" if r.get("anulada")     # ↩️ v12.8.3
                               else ("ganada" if r.get("ganada") else "perdida"))
            op["pnl"] = r.get("pnl")
            op["fin_real"] = r.get("fin")
            op["fuente_verdad"] = r.get("fuente")
            if r.get("cobro_real"):
                op["cobro_real"] = r["cobro_real"]
            op["cerrado_en"] = datetime.now(timezone.utc).isoformat()
            nuevas_cerr.append(op)
        else:
            if r.get("fin"):
                op["fin_previsto"] = r["fin"]
            quedan_ab.append(op)
    pnl_despues = round(pnl_antes_total
                        + sum(float(o.get("pnl") or 0) - float(o.get("pnl_antes") or 0) for o in corregidas)
                        - sum(float(o.get("pnl_antes_auditoria") or 0) for o in reabiertas)
                        + sum(float(o.get("pnl") or 0) for o in nuevas_cerr), 2)
    cambios = len(reabiertas) + len(corregidas) + len(nuevas_cerr)
    stats = None
    if aplicar:
        estado["historial"] = nueva_hist + nuevas_cerr
        estado["trades_copiados"] = quedan_ab + reabiertas
        estado["ultima_auditoria"] = datetime.now(timezone.utc).isoformat()
        estado["ultimo_auditoria_resumen"] = {
            "reabiertas": len(reabiertas), "corregidas": len(corregidas),
            "confirmadas": len(confirmadas), "manuales": manuales,
            "nuevas_cerradas": len(nuevas_cerr), "origen": origen,
            "pnl_antes": pnl_antes_total, "pnl_despues": pnl_despues}
        guardar_estado(estado)
        try:
            stats = calcular_stats()
        except Exception:
            stats = None
    txt = (f"🩺 *{'AUTO-CURACIÓN' if origen == 'auto' else 'RE-AUDITORÍA'} v12.7*"
           f"{'' if aplicar else ' (modo SECO)'}\n\n"
           f"Archivadas revisadas: *{len(hist) - manuales - fuera_rango}* "
           f"(🔒 manuales {manuales}"
           + (f", fuera de rango {fuera_rango}" if fuera_rango else "")
           + (f", sin datos CLOB {sin_datos}" if sin_datos else "") + ")\n"
           f"  ⏳ Reabiertas (seguían en juego): *{len(reabiertas)}*\n"
           f"  ✏️ Corregidas (resultado/PnL): *{len(corregidas)}*\n"
           f"  ✔️ Confirmadas: {len(confirmadas)}\n"
           f"  🏁 Abiertas resueltas ahora: {len(nuevas_cerr)}\n"
           + (f"  🧹 Limpieza v12.8.3: {_cura.get('basura', 0)} basura · "
              f"{_cura.get('fantasma', 0)} duplicados fantasma · "
              f"{_cura.get('casadas', 0)} casadas con fill real · "
              f"{_cura.get('sin_evidencia', 0)} sin evidencia (intactas)\n"
              if (_cura.get("basura") or _cura.get("fantasma")
                  or _cura.get("casadas") or _cura.get("sin_evidencia")) else "")
           + f"PnL archivadas: ${pnl_antes_total:+.2f} → *${pnl_despues:+.2f}*\n")
    if reabiertas:
        txt += "\n*⏳ Vuelven a 📂 Abiertas (antes dadas por perdidas):*\n"
        for o in reabiertas[:14]:
            extra = (f" · tokens en cartera {float(o.get('saldo_tokens') or 0):.2f}"
                     if o.get("saldo_tokens") else "")
            txt += (f"\n• {str(o.get('question', '?'))[:74]}\n"
                    f"   decía ${float(o.get('pnl_antes_auditoria') or 0):+.2f} → "
                    f"EN JUEGO ${float(o.get('stake_dolares') or 0):.2f} "
                    f"({float(o.get('size_shares') or 0):.2f} sh · "
                    f"{o.get('pendiente_info') or 'legs sin resolver'}{extra})")
        if len(reabiertas) > 14:
            txt += f"\n_… y {len(reabiertas) - 14} más_"
    if corregidas:
        txt += "\n\n*✏️ Resultado corregido con la verdad real:*\n"
        for o in corregidas[:14]:
            extra = (f" · cobro real ${float(o.get('cobro_real') or 0):.2f}"
                     if o.get("cobro_real") else "")
            txt += (f"\n• {str(o.get('question', '?'))[:74]}\n"
                    f"   {o.get('resultado_antes') or '?'} "
                    f"${float(o.get('pnl_antes') or 0):+.2f} → "
                    f"*{o.get('resultado')}* ${float(o.get('pnl') or 0):+.2f}{extra}")
        if len(corregidas) > 14:
            txt += f"\n_… y {len(corregidas) - 14} más_"
    if nuevas_cerr:
        txt += (f"\n\n*🏁 Abiertas que YA se resolvieron:* {len(nuevas_cerr)} → "
                f"${sum(float(o.get('pnl') or 0) for o in nuevas_cerr):+.2f}\n")
    if aplicar and stats:
        txt += (f"\n💾 Estado guardado (copia previa en combos_estado.bak.json)\n"
                f"📊 Stats: ✅{stats['wins']} ❌{stats['losses']} · PnL ${stats['pnl']:+.2f} · "
                f"ROI {(stats['pnl'] / stats['stake'] * 100) if stats['stake'] else 0:+.1f}%\n"
                f"📂 Abiertas ahora: {len(estado['trades_copiados'])}")
    elif not aplicar:
        txt += "\n\n🧪 _Modo SECO: no se ha modificado nada. Envía /reauditar para aplicarlo._"
    log(f"  [auditoria:{origen}]{' APLICADA' if aplicar else ' SECO'} "
        f"reabiertas={len(reabiertas)} corregidas={len(corregidas)} "
        f"confirmadas={len(confirmadas)} manuales={manuales} nuevas={len(nuevas_cerr)} "
        f"sin_datos={sin_datos} "
        f"· PnL archivadas {pnl_antes_total:+.2f}→{pnl_despues:+.2f}")
    resumen = {"cura": _cura, "reabiertas": len(reabiertas), "corregidas": len(corregidas),
               "confirmadas": len(confirmadas), "manuales": manuales,
               "sin_datos": sin_datos,
               "nuevas_cerradas": len(nuevas_cerr), "pnl_antes": pnl_antes_total,
               "pnl_despues": pnl_despues, "stats": stats, "texto": txt}
    if chat_id:
        if not silencioso:
            enviar_largo(chat_id, txt)
        elif cambios:
            corto = (f"🩺 *AUTO-CURACIÓN* (corre sola cada {AUDITORIA_CADA_H:.0f}h)\n\n"
                     f"⏳ Reabiertas: *{len(reabiertas)}* · ✏️ Corregidas: *{len(corregidas)}* · "
                     f"🏁 Cerradas ahora: {len(nuevas_cerr)}\n"
                     f"PnL de las archivadas: ${pnl_antes_total:+.2f} → *${pnl_despues:+.2f}*\n"
                     f"_Envía /reauditar seco para ver el detalle o /cerradas para la lista._")
            enviar_largo(chat_id, corto)
    return resumen


def cmd_reauditar(chat_id, texto=""):
    """🩺 v12.6: re-auditoría A MANO (con detalle y saldo on-chain).
    /reauditar seco = sólo informa, no modifica nada.
    La versión automática (v12.7) corre sola al arrancar y cada 4h."""
    seco = any(k in str(texto).lower() for k in ("seco", "dry", "test"))

    def _run():
        try:
            if not seco:
                enviar(chat_id, "🩺 Re-auditando operaciones contra Polymarket "
                                "(cobros reales + legs + saldo on-chain)… "
                                "_puede tardar unos segundos_")
            cobros_wallet(refrescar=True)      # verdad fresca de la wallet
            with AUDITORIA_LOCK:
                with PASADA_LOCK:
                    reauditar_estado(chat_id=chat_id, aplicar=(not seco), con_saldo=True,
                                     origen=("seco" if seco else "manual"))
        except Exception as e:
            log(f"  [reauditar] error: {e}")
            try:
                enviar(chat_id, f"❌ Re-auditoría falló: {str(e)[:200]}")
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()


def cmd_cerradas(chat_id):
    """✅ v11.5: cerradas con 🟢/🔴 y PnL; sincroniza en vivo primero."""
    try:
        _, nuevas, estado = sincronizar_operaciones()
    except Exception:
        nuevas, estado = [], cargar_estado()
    historial = estado.get("historial", [])
    if not historial:
        return enviar(chat_id, "📭 Sin cerradas.")
    total = sum(float(h.get("pnl", 0) or 0) for h in historial)
    gan = sum(1 for h in historial if float(h.get("pnl", 0) or 0) > 0)
    # ↩️ v12.8.3: las anuladas (mercado devuelto) se cuentan aparte
    anu = sum(1 for h in historial if str(h.get("resultado")) == "anulada")
    texto = (f"✅ *CERRADAS ({len(historial)})* — 🟢 {gan} / 🔴 {len(historial) - gan - anu}"
             + (f" / ↩️ {anu} anuladas" if anu else "") + f"\n_PnL: ${total:+.2f}_\n")
    sub = {}
    for h in historial:
        d = sub.setdefault(franja_of(h), [0, 0.0])
        d[0] += 1
        d[1] += float(h.get("pnl", 0) or 0)
    partes = [f"{nombre}: {sub[fr][0]} · ${sub[fr][1]:+.2f}"
              for nombre, fr in (("🤖 base", "base"), ("🚀 ext", "extendida"), ("💥 súper", "super"))
              if fr in sub]
    texto += " · ".join(partes) + "\n\n"
    if nuevas:
        texto += f"_Recién cerradas en este chequeo: {len(nuevas)}_\n\n"
    for h in historial[-15:]:
        pnl = float(h.get("pnl", 0) or 0)
        ico = "↩️" if str(h.get("resultado")) == "anulada" else ("🟢" if pnl >= 0 else "🔴")
        titulo_h = str(h.get("question", "?"))[:240]
        texto += f"\n{ico} {FRANJA_ICO.get(franja_of(h), '')}{titulo_h} → ${pnl:+.2f}"
    return enviar_largo(chat_id, texto)

# ============================================
# v12.9.0: 🏆 TOP REAL EN VIVO + 📡 COPY-TRADING EN PAPEL (FASE 1)
# ============================================
# Estudiado con datos reales antes de escribir una línea (12-sep):
#   · lb-api.polymarket.com/profit?window={1d|7d|30d|all} → ranking con proxyWallet
#   · data-api /activity?user=<wallet>&type=TRADE → sus fills (retraso: minutos)
#   · copiar al "top 1" es la PEOR regla: el top-1 histórico activo (RN1) dio
#     −48.8% en sus últimas 48 h; en 30 días conviven +130% con −100%.
#   · el precio NO se mueve al instante en deporte (−0.6 pts a los 1-30 min),
#     así que la señal se puede aprovechar; en otros mercados sí (media +4.2%).
# Por eso esto arranca EN PAPEL: mide el ROI prospectivo antes de arriesgar nada.
LB_API = "https://lb-api.polymarket.com"
VENTANAS_LB = {"1d": "24 h", "7d": "7 días", "30d": "30 días", "all": "histórico"}
COPY_ACTIVO = True          # 📡 seguimiento en papel ON
COPY_DINERO = False         # ❌ Fase 2 APAGADA: ninguna señal se ejecuta
COPY_VENTANA = "30d"        # ranking de referencia para elegir traders
COPY_N_TRADERS = 5          # a cuántos vigilamos a la vez
COPY_TOPE_DIA = 5           # señales nuevas/día (tope PROPIO, no el de combos)
COPY_SONDEO_S = 180         # cada cuánto leemos sus fills
COPY_MIN_COMPRAS_48H = 5    # filtro: que esté activo
COPY_MAX_RATIO_VENTAS = 0.5  # filtro: no market maker
COPY_MIN_MERCADOS = 3       # filtro: no concentrado en 1-2 mercados
COPY_MIN_DEPORTE = 0.40     # filtro: que juegue donde sabemos combinar
COPY_DERIVA_MAX = 0.05      # si el precio ya se movió >5 pts, la señal es tardía
COPY_RESUMEN_CADA_S = 86400  # informe diario
COPY_STAKE_PAPEL = 5.0      # $ por señal en la simulación (tu stake mínimo)
COPY_ELEGIR_CADA_S = 86400   # la lista se reevalúa a diario
COPY_MAX_SEÑALES = 300      # tope del histórico en el estado (~60 días a 5/día)
COPY_RESOLVER_POR_RONDA = 10  # máx. mercados consultados al resolver por pasada
COPY_MAX_VISTOS = 4000        # tope del dedup de fills (se poda por antigüedad)
COPY_VISTOS_DIAS = 2          # días de dedup que se conservan
NEXT_COPY_TS = 0.0
NEXT_COPY_RESUMEN_TS = 0.0
_LB_CACHE = [0.0, {}]       # [ts, {ventana: [(puesto, nombre, wallet, profit, vol)]}]
_DEPORTE_CLAVES = ("nfl", "nba", "mlb", "nhl", "epl", "laliga", "ucl", "atp", "wta",
                   "f1", "seriea", "bundesliga", "ligue1", "mls", "wnba", "ufc",
                   "soccer", "football", "basketball", "baseball", "tennis", "mma",
                   "hockey", "cricket", "esports", "lol", "csgo", "dota", "ren-", "fl1")


def _lb_get(url, timeout=20):
    """GET público (sin proxy: leer el ranking no necesita el PC encendido)."""
    req = urllib.request.Request(url, headers={"User-Agent": "poly-combos-bot"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _din_lb(v):
    """$1.2M / $918K / $91 — para que el ranking quepa en el mensaje."""
    try:
        v = float(v or 0)
    except Exception:
        return "$0"
    a = abs(v)
    if a >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if a >= 1_000:
        return f"${v / 1_000:.1f}K"
    return f"${v:.0f}"


def nombre_lb(x, wallet=""):
    """lb-api a veces da como nombre la wallet con un número detrás
    (0x2c33…-1759935795465): eso no se enseña. Mejor el apodo; si no, la wallet."""
    for k in ("pseudonym", "name"):
        v = str((x or {}).get(k) or "").strip()
        if v and not v.startswith("0x") and len(v) <= 24:
            return v
    return str(wallet)[:10] or "anónimo"


def top_traders(ventana="1d", limite=10, refrescar=False):
    """🏆 v12.9.0: ranking REAL (beneficio + volumen + wallet). Cache 15 min.
    → [(puesto, nombre, wallet, profit, volumen)] · [] si no hay red."""
    if ventana not in VENTANAS_LB:
        ventana = "1d"
    ahora = time.time()
    if not refrescar and _LB_CACHE[1].get(ventana) and ahora - _LB_CACHE[0] < 900:
        return _LB_CACHE[1][ventana]
    try:
        prof = _lb_get(f"{LB_API}/profit?window={ventana}&limit={limite}") or []
        try:
            vol = _lb_get(f"{LB_API}/volume?window={ventana}&limit=100") or []
        except Exception:
            vol = []
        vmap = {str(x.get("proxyWallet", "")).lower(): float(x.get("amount") or 0)
                for x in vol}
        filas = []
        for i, x in enumerate(prof, 1):
            w = str(x.get("proxyWallet") or "")
            filas.append((i, nombre_lb(x, w), w,
                          float(x.get("amount") or 0), vmap.get(w.lower(), 0.0)))
        _LB_CACHE[0] = ahora
        _LB_CACHE[1][ventana] = filas
        return filas
    except Exception as e:
        log(f"  [top] lb-api sin respuesta: {str(e)[:60]}")
        return _LB_CACHE[1].get(ventana, [])


def es_deporte_copy(texto):
    t = str(texto or "").lower()
    return any(k in t for k in _DEPORTE_CLAVES)


def perfil_trader(wallet, horas=48, limite=300):
    """📡 Radiografía REAL de una wallet en las últimas horas: compras, ventas,
    mercados distintos, % deporte y tamaño mediano. Decide si entra en la lista."""
    if not wallet:
        return None
    try:
        act = _lb_get(f"{DATA_API}/activity?user={wallet}&limit={limite}&type=TRADE") or []
    except Exception as e:
        log(f"  [copy] sin actividad de {str(wallet)[:10]}…: {str(e)[:50]}")
        return None
    corte = time.time() - horas * 3600
    tr = [x for x in act if x.get("type") == "TRADE"
          and int(x.get("timestamp") or 0) >= corte]
    if not tr:
        return {"compras": 0, "ventas": 0, "ratio": 0.0, "mercados": 0, "deporte": 0.0,
                "mediana_usd": 0.0, "ultimo": 0, "n": 0}
    compras = [x for x in tr if x.get("side") == "BUY"]
    ventas = [x for x in tr if x.get("side") == "SELL"]
    mk = {str(x.get("conditionId")) for x in tr}
    esp = sum(1 for x in tr if es_deporte_copy(
        x.get("eventSlug") or x.get("slug") or x.get("title")))
    usd = sorted(float(x.get("usdcSize") or 0) for x in tr)
    return {"compras": len(compras), "ventas": len(ventas),
            "ratio": len(ventas) / max(len(compras), 1), "mercados": len(mk),
            "deporte": esp / len(tr),
            "mediana_usd": usd[len(usd) // 2] if usd else 0.0,
            "ultimo": max(int(x.get("timestamp") or 0) for x in tr), "n": len(tr)}


def filtros_perfil(p):
    """Por qué un trader entra o se descarta. → (ok, motivo en cristiano)"""
    if not p or int(p.get("compras") or 0) < COPY_MIN_COMPRAS_48H:
        return False, f"inactivo ({int((p or {}).get('compras') or 0)} compras en 48 h)"
    if float(p["ratio"]) > COPY_MAX_RATIO_VENTAS:
        return False, (f"market maker ({p['ventas']} ventas / {p['compras']} compras): "
                       "copiar sólo sus compras sería catastrófico")
    if int(p["mercados"]) < COPY_MIN_MERCADOS:
        return False, f"concentrado en {p['mercados']} mercado(s)"
    if float(p["deporte"]) < COPY_MIN_DEPORTE:
        return False, f"sólo {p['deporte'] * 100:.0f}% deporte"
    return True, (f"activo ({p['compras']} compras, {p['mercados']} mercados, "
                  f"{p['deporte'] * 100:.0f}% deporte)")


def copy_elegir(estado, chat_id=None):
    """📡 Elige a los COPY_N_TRADERS primeros del ranking que PASAN los filtros.
    Se reevalúa cada COPY_ELEGIR_CADA_S porque el top cambia (y porque el que hoy
    gana puede ser el que mañana pierda: por eso filtramos por conducta, no por puesto)."""
    top = top_traders(COPY_VENTANA, 12, refrescar=True)
    cp = estado_copy(estado)
    if not top:
        log("  [copy] sin ranking (lb-api no respondió): sigo con la lista anterior")
        return cp.get("traders") or []
    elegidos = []
    for puesto, nom, w, prof, vol in top:
        if not w:
            continue
        p = perfil_trader(w)
        okk, mot = filtros_perfil(p)
        log(f"  [copy] #{puesto} {str(nom)[:20]:<20} {'ELEGIDO' if okk else 'descartado'} · {mot}")
        if okk:
            elegidos.append({"nombre": str(nom)[:24], "wallet": w, "puesto": puesto,
                             "profit": round(prof, 2), "volumen": round(vol, 2),
                             "compras48h": p["compras"], "ventas48h": p["ventas"],
                             "ratio_ventas": round(p["ratio"], 2),
                             "mercados": p["mercados"],
                             "deporte_pct": round(p["deporte"] * 100),
                             "mediana_usd": round(p["mediana_usd"], 2),
                             "elegido_en": int(time.time())})
        time.sleep(0.2)
        if len(elegidos) >= COPY_N_TRADERS:
            break
    cp["traders"] = elegidos
    cp["ts_eleccion"] = time.time()
    guardar_estado(estado)
    log(f"  [copy] vigilando {len(elegidos)} traders: "
        + ", ".join(t["nombre"] for t in elegidos))
    if chat_id and elegidos:
        lines = "".join(f"   {i}. *{t['nombre']}* {_din_lb(t['profit'])} · "
                        f"{t['compras48h']} compras/48h · {t['deporte_pct']}% deporte\n"
                        for i, t in enumerate(elegidos, 1))
        enviar(chat_id, f"📡 *Copy-trading en papel*: ya vigilo a {len(elegidos)} traders\n"
                        f"{lines}_Top {COPY_VENTANA} filtrado (fuera market makers, "
                        f"inactivos y concentrados). Sus compras son SEÑALES: no compro nada._")
    return elegidos


def fills_recientes(wallet, desde_ts, limite=200):
    """Compras de una wallet posteriores a desde_ts (más recientes primero)."""
    try:
        act = _lb_get(f"{DATA_API}/activity?user={wallet}&limit={limite}&type=TRADE") or []
    except Exception:
        return []
    out = [x for x in act if x.get("type") == "TRADE" and x.get("side") == "BUY"
           and int(x.get("timestamp") or 0) > float(desde_ts)]
    out.sort(key=lambda x: -int(x.get("timestamp") or 0))
    return out


def estado_copy(estado):
    return estado.setdefault("copy", {"traders": [], "vistos": {}, "ts_ultimo": 0,
                                      "ts_inicio": 0, "ts_eleccion": 0, "informes": 0})


def señales_hoy(estado):
    """Señales registradas hoy (UTC): tope PROPIO, independiente del de combos."""
    hoy = time.strftime("%Y-%m-%d", time.gmtime())
    return sum(1 for s in (estado.get("copy_señales") or [])
               if str(s.get("dia") or "") == hoy)


def _caras_de(cid):
    """{token_id: {'winner': bool}} si el mercado YA tiene ganador; si está
    closed sin ganador → 'anulada'; si no, None (sigue vivo)."""
    m = mercado_clob(cid)
    if not isinstance(m, dict):
        return None
    caras = {str(tk.get("token_id")): {"winner": bool(tk.get("winner"))}
             for tk in (m.get("tokens") or [])}
    if not caras:
        return None
    if any(v["winner"] for v in caras.values()):
        return caras
    if m.get("closed"):
        return "anulada"          # ↩️ como las anuladas del panel: devuelve 0
    return None


def registrar_señal(estado, trader, wallet, fill, precio_nuestro):
    """📡 Anota una señal EN PAPEL con los DOS precios (el suyo y el nuestro).
    → registro, o None si el tope diario ya está cubierto.
    Si el trader ESCALA en la misma posición (mismo token, hoy, sin resolver) no se
    crea otra señal: se fusiona el importe y se deja el precio de la PRIMERA entrada
    (el momento en que nosotros habríamos entrado). Así el tope de señales/día cuenta
    MERCADOS distintos, no fills sueltos (medido: 102 fills = 4 posiciones)."""
    hoy = time.strftime("%Y-%m-%d", time.gmtime())
    tok, wal = str(fill.get("asset") or ""), str(wallet)
    for prev in reversed(estado.get("copy_señales") or []):
        if (prev.get("token") == tok and prev.get("wallet") == wal
                and prev.get("dia") == hoy and not prev.get("resuelta")):
            prev["escaladas"] = int(prev.get("escaladas") or 0) + 1
            prev["usd_trader"] = round(float(prev.get("usd_trader") or 0)
                                       + float(fill.get("usdcSize") or 0), 2)
            prev["size_trader"] = round(float(prev.get("size_trader") or 0)
                                        + float(fill.get("size") or 0), 4)
            prev["ts_ultimo_fill"] = int(fill.get("timestamp") or 0)
            prev["precio_nuestro_max"] = round(max(float(prev.get("precio_nuestro_max")
                                                         or prev.get("precio_nuestro") or 0),
                                                   float(precio_nuestro or 0)), 4)
            return prev
    if señales_hoy(estado) >= COPY_TOPE_DIA:
        return None
    p_el = float(fill.get("price") or 0)
    if not (0 < p_el < 1) or not precio_nuestro:
        return None
    ts_fill = int(fill.get("timestamp") or 0)
    reg = {
        "dia": time.strftime("%Y-%m-%d", time.gmtime()),
        "ts": int(time.time()), "ts_fill": ts_fill,
        "retraso_s": int(time.time()) - ts_fill,
        "trader": str(trader)[:24], "wallet": str(wallet),
        "titulo": str(fill.get("title") or "?")[:110],
        "slug": fill.get("slug"), "event_slug": fill.get("eventSlug"),
        "condition_id": str(fill.get("conditionId") or ""),
        "token": str(fill.get("asset") or ""), "outcome": fill.get("outcome"),
        "precio_trader": p_el,
        "cuota_trader": round(1 / p_el, 2),
        "usd_trader": round(float(fill.get("usdcSize") or 0), 2),
        "size_trader": round(float(fill.get("size") or 0), 4),
        "precio_nuestro": round(float(precio_nuestro), 4),
        "cuota_nuestro": round(1 / float(precio_nuestro), 2),
        "deriva_pts": round((float(precio_nuestro) - p_el) * 100, 2),
        "deporte": es_deporte_copy(fill.get("eventSlug") or fill.get("title")),
        # ¿serviría esta pierna para un combo nuestro? (Fase 2)
        "en_rango_combo": bool(1 / CUOTA_MAX <= float(precio_nuestro) <= 1 / CUOTA_MIN),
        "tx": str(fill.get("transactionHash") or "")[:24],
        "resuelta": False, "senal_acerto": None, "anulada": False,
        "pnl_papel_nuestro": None, "pnl_papel_trader": None,
        "ejecutada": False,       # Fase 2: si algún día se convierte en combo propio
        "escaladas": 0,           # compras posteriores en la MISMA posición (fusionadas)
        "precio_nuestro_max": round(float(precio_nuestro), 4),
        "ts_ultimo_fill": ts_fill,
    }
    estado.setdefault("copy_señales", []).append(reg)
    return reg


def resolver_señales(estado):
    """Cierra las señales cuyo mercado ya se resolvió: ¿acertó la SEÑAL? y qué PnL
    teórico habría dado a $5 al precio NUESTRO y al SUYO. → nº resueltas ahora."""
    pend = [s for s in (estado.get("copy_señales") or []) if not s.get("resuelta")]
    if not pend:
        return 0
    # Acotado: como máximo COPY_RESOLVER_POR_RONDA mercados mirados por pasada,
    # para que resolver señales no estire el PASADA_LOCK de los combos.
    n = 0
    for s in pend[:COPY_RESOLVER_POR_RONDA]:
        caras = _caras_de(s.get("condition_id"))
        if caras is None:
            continue
        if caras == "anulada":
            s["resuelta"], s["anulada"], s["senal_acerto"] = True, True, None
            s["pnl_papel_nuestro"] = s["pnl_papel_trader"] = 0.0
            n += 1
            continue
        info = caras.get(str(s.get("token")))
        if info is None:
            continue
        gano = bool(info.get("winner"))
        s["senal_acerto"] = gano
        for kp, kpnl in (("precio_nuestro", "pnl_papel_nuestro"),
                         ("precio_trader", "pnl_papel_trader")):
            p = float(s.get(kp) or 0)
            s[kpnl] = round(COPY_STAKE_PAPEL * (1 / p - 1) if gano
                            else -COPY_STAKE_PAPEL, 3) if 0 < p < 1 else None
        s["resuelta"] = True
        n += 1
    return n


def resumen_copy(estado):
    """Números del seguimiento. La cifra que importa: ROI AL PRECIO NUESTRO."""
    s = estado.get("copy_señales") or []
    res = [x for x in s if x.get("resuelta") and not x.get("anulada")]
    anu = [x for x in s if x.get("anulada")]
    ac = [x for x in res if x.get("senal_acerto")]
    pn_n = sum(float(x.get("pnl_papel_nuestro") or 0) for x in res)
    pn_t = sum(float(x.get("pnl_papel_trader") or 0) for x in res)
    der = [float(x["deriva_pts"]) for x in s if x.get("deriva_pts") is not None]
    ret = [int(x.get("retraso_s") or 0) for x in s if x.get("retraso_s")]
    por = {}
    for x in res:
        g = por.setdefault(x.get("trader", "?"), {"n": 0, "ac": 0, "pnl_n": 0.0, "pnl_t": 0.0})
        g["n"] += 1
        g["ac"] += 1 if x.get("senal_acerto") else 0
        g["pnl_n"] += float(x.get("pnl_papel_nuestro") or 0)
        g["pnl_t"] += float(x.get("pnl_papel_trader") or 0)
    cp = estado.get("copy") or {}
    dias = max(1, int((time.time() - float(cp.get("ts_inicio") or time.time())) // 86400) + 1)
    return {"senales": len(s), "resueltas": len(res), "anuladas": len(anu),
            "aciertos": len(ac),
            "acierto_pct": (len(ac) / len(res) * 100) if res else None,
            "pnl_nuestro": round(pn_n, 2), "pnl_trader": round(pn_t, 2),
            "roi_nuestro": (pn_n / (len(res) * COPY_STAKE_PAPEL) * 100) if res else None,
            "deriva_med": round(sum(der) / len(der), 2) if der else None,
            "retraso_med_s": int(sum(ret) / len(ret)) if ret else None,
            "por_trader": por, "dias": dias, "en_rango": sum(1 for x in s if x.get("en_rango_combo")),
            "hoy": señales_hoy(estado), "tope": COPY_TOPE_DIA,
            "escaladas": sum(int(x.get("escaladas") or 0) for x in s),
            "traders": cp.get("traders") or []}


def texto_copy(estado):
    """📡 /copy — panel del seguimiento en papel."""
    r = resumen_copy(estado)
    t = ("📡 *COPY-TRADING EN PAPEL* (Fase 1 · sin dinero)\n"
         f"_día {r['dias']} de seguimiento · el bot NO compra: sólo anota_\n\n")
    if r["traders"]:
        t += f"👥 *Vigilando* (top {COPY_VENTANA} filtrado):\n"
        for x in r["traders"][:COPY_N_TRADERS]:
            t += (f"   · *{x['nombre']}* {_din_lb(x.get('profit'))} · "
                  f"{x.get('compras48h', '?')} compras/48h · "
                  f"{x.get('deporte_pct', '?')}% deporte\n")
    else:
        t += "👥 _Aún sin traders elegidos (la próxima pasada los filtra)_\n"
    t += (f"\n📨 Señales: *{r['senales']}* · hoy {r['hoy']}/{r['tope']} · "
          f"útiles para un combo (cuota {CUOTA_MIN}-{CUOTA_MAX}): {r['en_rango']}")
    t += (f" · {r['escaladas']} compras repetidas fusionadas\n" if r["escaladas"] else "\n")
    if r["resueltas"]:
        t += (f"🏁 Resueltas: *{r['resueltas']}*"
              + (f" (+{r['anuladas']} ↩️ anuladas)" if r["anuladas"] else "")
              + f" · acierto *{r['acierto_pct']:.1f}%* ({r['aciertos']}/{r['resueltas']})\n")
        t += (f"💵 PnL teórico a ${COPY_STAKE_PAPEL:.0f}/señal: al precio NUESTRO "
              f"*${r['pnl_nuestro']:+.2f}* (ROI {r['roi_nuestro']:+.1f}%) · "
              f"al precio de ellos ${r['pnl_trader']:+.2f}\n")
        if r["deriva_med"] is not None:
            m, sg = divmod(int(r["retraso_med_s"] or 0), 60)
            t += (f"⏱ Llegamos {m} min {sg} s tarde de media · "
                  f"deriva de precio *{r['deriva_med']:+.2f} pts*\n")
        if r["por_trader"]:
            t += "\n*Por trader* (resueltas · acierto · PnL nuestro):\n"
            for nom, g in sorted(r["por_trader"].items(), key=lambda kv: -kv[1]["pnl_n"]):
                t += (f"   · {str(nom)[:20]:<20} {g['n']:>3} · "
                      f"{g['ac'] / max(g['n'], 1) * 100:>5.1f}% · ${g['pnl_n']:>+8.2f}\n")
    else:
        t += "\n🏁 _Ninguna resuelta aún: los mercados tardan horas o días._\n"
    t += ("\n🎯 *Para pasar a Fase 2* (convertir la señal en un combo propio por RFQ): "
          "≥30 señales resueltas y ROI positivo AL PRECIO NUESTRO.\n"
          "_Medido antes de arrancar: el top-1 histórico activo dio −48.8% en 48 h y "
          "en 30 días conviven +130% con −100%. Por eso en papel._")
    return t


def cmd_copy(chat_id):
    estado = cargar_estado()
    estado_copy(estado)
    return enviar(chat_id, texto_copy(estado))


def copy_pasada(chat_id):
    """📡 v12.9.0: una ronda de seguimiento EN PAPEL. LEE (ranking, fills, mid),
    anota señales con tope propio y resuelve las antiguas. NO firma nada: no hay
    ningún camino de esta función a enviar_orden/ejecutar_trade/ejecutar_combo_rfq."""
    global NEXT_COPY_RESUMEN_TS
    if not COPY_ACTIVO:
        return
    estado = cargar_estado()
    cp = estado_copy(estado)
    if not cp.get("ts_inicio"):
        cp["ts_inicio"] = time.time()
        NEXT_COPY_RESUMEN_TS = time.time() + COPY_RESUMEN_CADA_S
    traders = cp.get("traders") or []
    if not traders or time.time() - float(cp.get("ts_eleccion") or 0) > COPY_ELEGIR_CADA_S:
        # La PRIMERA elección se anuncia en el chat; las reevaluaciones diarias, no.
        primera = not float(cp.get("ts_eleccion") or 0)
        traders = copy_elegir(estado, chat_id=chat_id if primera else None)
    if not traders:
        guardar_estado(estado)
        return
    vistos = cp.setdefault("vistos", {})
    desde = float(cp.get("ts_ultimo") or (time.time() - 3600))
    nuevas = 0
    fusiones = 0
    tope = False
    for t in traders:
        if tope:
            break
        for f in fills_recientes(t.get("wallet"), desde):
            clave = f"{str(f.get('transactionHash') or '')[:24]}|{str(f.get('asset') or '')[:20]}"
            if clave in vistos:
                continue
            vistos[clave] = int(time.time())
            p_el = float(f.get("price") or 0)
            p_no = precio_mid(str(f.get("asset") or ""))
            titulo = str(f.get("title") or "?")[:60]
            if not (0 < p_el < 1):
                continue
            if p_no is None:
                log(f"  [copy] sin libro para {titulo} · señal no registrada")
                continue
            if abs(p_no - p_el) > COPY_DERIVA_MAX:
                log(f"  [copy] señal TARDÍA {titulo}: él {p_el:.3f} → ahora {p_no:.3f} "
                    f"({(p_no - p_el) * 100:+.1f} pts) · no cuenta")
                continue
            reg = registrar_señal(estado, t.get("nombre"), t.get("wallet"), f, p_no)
            if reg is None:
                log(f"  [copy] tope diario de señales ({COPY_TOPE_DIA}) alcanzado")
                tope = True
                break
            if int(reg.get("escaladas") or 0):
                fusiones += 1          # una sola línea de log por ronda (no 1 por fill)
                continue
            nuevas += 1
            m, sg = divmod(max(0, reg["retraso_s"]), 60)
            log(f"  [copy] 📡 señal #{reg['ts']} de {reg['trader']}: {titulo} · "
                f"él {p_el:.3f} / nosotros {p_no:.3f} ({reg['deriva_pts']:+.1f} pts) · "
                f"retraso {m}m{sg:02d}s · papel ${COPY_STAKE_PAPEL:.0f}")
            if chat_id:
                enviar(chat_id, f"📡 *SEÑAL (papel, $0)* · {reg['trader']} compró\n"
                                f"📌 {titulo} ({reg.get('outcome') or '?'})\n"
                                f"💵 él a {p_el:.3f} (${reg['usd_trader']:,.0f}) · "
                                f"nosotros entraríamos a {p_no:.3f} "
                                f"({reg['deriva_pts']:+.1f} pts) · cuota {reg['cuota_nuestro']:.2f}\n"
                                f"⏱ Retraso {m} min {sg} s · {'⚽ deporte' if reg['deporte'] else '🎲 no deporte'}"
                                f" · {'✅ sirve para un combo' if reg['en_rango_combo'] else '❌ fuera de tu rango de cuota'}\n"
                                f"_No se ha comprado nada. /copy → el resumen_")
        time.sleep(0.2)
    corte = int(time.time()) - COPY_VISTOS_DIAS * 86400
    limpios = {k: v for k, v in vistos.items() if int(v) >= corte}
    if len(limpios) > COPY_MAX_VISTOS:
        limpios = dict(sorted(limpios.items(), key=lambda kv: -int(kv[1]))[:COPY_MAX_VISTOS])
    cp["vistos"] = limpios
    cp["ts_ultimo"] = time.time()
    resueltas = resolver_señales(estado)
    señ = estado.get("copy_señales") or []
    if len(señ) > COPY_MAX_SEÑALES:
        estado["copy_señales"] = señ[-COPY_MAX_SEÑALES:]
    guardar_estado(estado)
    if nuevas or resueltas or fusiones:
        log(f"  [copy] ronda: {nuevas} señal(es) nueva(s) · {fusiones} compra(s) "
            f"repetida(s) fusionada(s) · {resueltas} resuelta(s) · "
            f"dedup {len(cp['vistos'])} fills")
    if chat_id and time.time() >= NEXT_COPY_RESUMEN_TS:
        NEXT_COPY_RESUMEN_TS = time.time() + COPY_RESUMEN_CADA_S
        cp["informes"] = int(cp.get("informes") or 0) + 1
        guardar_estado(estado)
        try:
            enviar(chat_id, texto_copy(estado))
        except Exception:
            pass


def programar_copy_inicio():
    """📡 Primera ronda ~90 s tras arrancar (deja terminar a la auto-curación)."""
    global NEXT_COPY_TS, NEXT_COPY_RESUMEN_TS
    NEXT_COPY_TS = time.time() + 90
    NEXT_COPY_RESUMEN_TS = time.time() + COPY_RESUMEN_CADA_S


def cmd_top(chat_id, ventana=None):
    """🏆 v12.9.0: ranking REAL y en vivo (antes era una lista escrita a mano y
    falsa). Con botones para cambiar de ventana y la wallet de cada trader."""
    v = ventana if ventana in VENTANAS_LB else "1d"
    filas = top_traders(v, 10)
    if not filas:
        return enviar(chat_id, "🏆 *TOP TRADERS POLYMARKET*\n\n"
                               "_lb-api no respondió ahora mismo (sin datos que enseñar). "
                               "Reintenta en unos minutos: el botón 🏆 no inventa cifras._")
    edad = int(time.time() - _LB_CACHE[0]) if _LB_CACHE[0] else 0
    t = (f"🏆 *TOP TRADERS POLYMARKET* · {VENTANAS_LB[v]}\n"
         f"_ranking real de lb-api · hace {edad // 60 if edad >= 60 else edad}"
         f"{' min' if edad >= 60 else ' s'}_\n\n")
    for i, nom, w, prof, vol in filas:
        margen = f"{prof / vol * 100:.0f}%" if vol > 0 else "n/d"
        t += (f"{i:>2}. *{str(nom)[:22]}* {_din_lb(prof)}\n"
              f"     vol {_din_lb(vol)} · margen {margen} · `{w[:10]}…{w[-6:]}`\n")
    t += ("\n⚠️ Estar arriba NO significa que vayan a seguir ganando: el top-1 histórico "
          "activo dio −48.8% en sus últimas 48 h.\n"
          "📡 /copy → a quiénes vigila el bot y qué dan sus señales (en papel, $0).")
    kb = {"inline_keyboard": [[{"text": ("✅ " if v == k else "") + lab,
                                "callback_data": f"lb:{k}"}
                               for k, lab in VENTANAS_LB.items()]]}
    return enviar(chat_id, t, kb)

def cmd_modo(chat_id, modo):
    """🟢/🟡/🔴 v12.8.4: cambia el modo Y explica qué hace cada uno de verdad.
    AUTO = abre solo. SEMI = propone con ✅/❌ y no compra sin tu visto bueno
    (antes SEMI no hacía NADA: era un OFF disfrazado). OFF = parado."""
    global MODO_OPERACION
    modo = modo.upper()
    if modo not in ("AUTO", "SEMI", "OFF"):
        return enviar(chat_id, "❌ AUTO, SEMI, OFF")
    MODO_OPERACION = modo
    estado = cargar_estado()
    estado["modo"] = modo
    guardar_estado(estado)
    log(f"modo -> {modo}")
    if modo == "AUTO":
        programar_pasada_ahora()   # v11.3: sin hilo paralelo
        return enviar(chat_id, f"🟢 *Modo: AUTO* ✅\n"
                               f"Abre combos solo cada {INTERVALO_AUTO_S // 60} min "
                               f"(cuota {CUOTA_MIN}-{CUOTA_MAX} · prob ≥{prob_nivel_txt(prob_min_auto(estado))} · "
                               f"tope {max_ops(estado)}/día) y sólo si la cotización mejora el "
                               f"mercado ≥{int(VENTAJA_MIN_EV * 100)}%.")
    if modo == "SEMI":
        # v12.8.4: en SEMI también hay pasadas, pero PROPONEN en vez de comprar
        programar_paso(time.time() + INTERVALO_AUTO_S)
        return enviar(chat_id, f"🟡 *Modo: SEMI* ✅\n"
                               f"Cada {INTERVALO_AUTO_S // 60} min busco y *te propongo* el mejor combo "
                               f"con botones ✅ Aceptar / ❌ Descartar.\n"
                               f"*Nada se compra sin tu ✅* · la propuesta caduca a los "
                               f"{int(PROPUESTA_VALIDA_S // 60)} min.\n"
                               f"_Al aceptar pido cotización nueva y sólo compro si mejora el "
                               f"mercado ≥{int(VENTAJA_MIN_EV * 100)}%; si no, te lo digo y no gasto nada._\n"
                               f"🔍 *Leer ahora* te enseña qué propondría, sin esperar.")
    return enviar(chat_id, "🔴 *Modo: OFF* ✅\nNo abro ni propongo nada. Siguen activos los "
                           "paneles, la auto-curación 🩺, /reclamar 💰 y los botones "
                           "manuales 🚀/💥.")

def cmd_stake(chat_id, valor):
    global STAKE_POR_TRADE
    if str(valor).strip().lower() in ("auto", "dinamico", "dinámico"):
        set_stake_mode("AUTO")
        estado = cargar_estado()
        estado["stake_mode"] = "AUTO"
        guardar_estado(estado)
        return enviar(chat_id, f"💵 *Stake AUTO ${STAKE_MIN_AUTO:.0f}-${STAKE_MAX_AUTO:.0f}*\n_Decide el bot según la cuota y cómo va la combinada (cuota baja ⇒ más stake; la ventaja real del RFQ ajusta)_")
    try:
        stake = float(valor)
        if stake < STAKE_MIN_AUTO or stake > 50:
            return enviar(chat_id, f"❌ Stake fijo entre ${STAKE_MIN_AUTO:.0f} y $50 (o /stake auto)")
        STAKE_POR_TRADE = stake
        set_stake_mode("FIJO")
        estado = cargar_estado()
        estado["stake"] = stake
        estado["stake_mode"] = "FIJO"
        guardar_estado(estado)
        return enviar(chat_id, f"*Stake FIJO: ${stake:.2f}*\n_Para volver al dinámico: /stake auto_")
    except:
        return enviar(chat_id, "❌ /stake auto · o /stake 7 (fijo $5-$50)")


# ============================================
# v12.8.3: SITUACIÓN REAL DEL MERCADO + PRECIO DE RESPALDO
# ============================================
def situacion_mercado(cid):
    """v12.8.3: estado REAL de un mercado del CLOB, en cristiano.
    → (clave, texto) con clave ∈ vivo|suspendido|sin_ganador|resuelto|sin_datos.
      · suspendido    = active=False y/o accepting_orders=False sin cerrar: NO
        hay libro ⇒ no se puede vender ni resolver (partido aplazado).
      · sin_ganador   = cerrado sin ganador declarado: normalmente ANULADO, los
        tokens se devuelven a ~$0.50 (explica cobros menores que las shares).
    Verificado el 11-sep: Seyboth Wild (atp-wild-ferrar-2026-09-08) →
    closed=False, active=False, accepting_orders=False, end 2026-09-15T00:00Z;
    Barranquilla (wta-pareja-stefani-2026-09-07) → closed=True, las DOS caras
    winner=False y price 0.5, y la wallet cobró $9.90 por 19.8 tokens."""
    m = mercado_clob(str(cid or ""))
    if not m:
        return "sin_datos", "❔ sin datos del mercado (CLOB/Gamma no responden)"
    toks = m.get("tokens") or []
    if any(tk.get("winner") for tk in toks):
        return "resuelto", "🏁 resuelto (ganador declarado)"
    if m.get("closed"):
        return "sin_ganador", ("↩️ cerrado SIN ganador declarado (anulado): los tokens "
                               "se devuelven a ~$0.50 · no paga $1")
    if (m.get("active") is False) or (m.get("accepting_orders") is False):
        t = "⏸ SUSPENDIDO: sin libro, no se puede vender ni resolver"
        if m.get("end_date_iso"):
            t += f" · resolución prevista {_madrid(m['end_date_iso'])}"
        return "suspendido", t
    return "vivo", "⏳ en juego"


_MAPA_SITUACION = {"vivo": "viva", "suspendido": "suspendida",
                   "sin_ganador": "anulada", "resuelto": "resuelta",
                   "sin_datos": "sin_datos"}


def situacion_op(op):
    """v12.8.3: situación de UNA posición (simple o combo) → (clave, texto).
    clave ∈ viva|suspendida|anulada|resuelta|muerta|sin_datos. En un combo manda
    la peor pata: si una leg ya perdió el parlay no paga; si alguna está
    suspendida no se puede vender el conjunto."""
    legs = op.get("legs") or []
    if not legs:
        cl, tx = situacion_mercado(op.get("condition_id"))
        return _MAPA_SITUACION.get(cl, cl), tx
    claves, isos = [], []
    n_gan = n_susp = n_juego = 0
    for lg in legs:
        cid = str(lg.get("condition_id") or "")
        m = mercado_clob(cid)
        cl, _tx = situacion_mercado(cid)
        est, _info = estado_leg(m, lg.get("outcome"))
        if est == "perdida":
            claves.append("perdida")
        elif est == "ganada":
            claves.append("ganada")
            n_gan += 1
        else:
            claves.append(cl)
            if cl == "suspendido":
                n_susp += 1
            elif cl == "vivo":
                n_juego += 1
        if m and m.get("end_date_iso"):
            isos.append(str(m["end_date_iso"]))
    if "perdida" in claves:
        return "muerta", "❌ una leg ya perdió: el combo NO paga (no se puede vender)"
    if claves and all(c == "ganada" for c in claves):
        return "resuelta", "🏁 todas las legs ganadas (pendiente de cobro)"
    txt = f"⏳ {n_gan} leg(s) ganadas · {n_juego} en juego"
    if n_susp:
        txt += f" · {n_susp} SUSPENDIDA(s) sin libro"
        if isos:
            txt += f" · resolución prevista {_madrid(max(isos))}"
        txt += " ⇒ no se puede vender ahora"
    return ("suspendida" if n_susp else "viva"), txt


def precio_vivo_op(op):
    """v12.8.3: (precio, fuente) de una posición abierta.
      fuente "mid" = libro vivo (midpoint del CLOB, lo de siempre).
      fuente "ult" = ÚLTIMO precio publicado por el mercado del CLOB: con el
        libro cerrado /midpoint da 404, pero el mercado trae `price` por cara,
        así que un mercado suspendido SÍ tiene valor en el panel (etiquetado).
      (None, None) si no hay nada de nada."""
    try:
        v = vivo_de(op)
    except Exception:
        v = None
    if v:
        return v, "mid"
    legs = op.get("legs") or []
    try:
        if legs:
            prod, ok = 1.0, True
            for lg in legs:
                cid = str(lg.get("condition_id") or "")
                m = mercado_clob(cid)
                tok = str(token_clob_de_leg(lg) or "")
                p = None
                for t in ((m or {}).get("tokens") or []):
                    if tok and str(t.get("token_id")) == tok:
                        try:
                            p = float(t.get("price") or 0) or None
                        except Exception:
                            p = None
                if p is None:
                    est, _ = estado_leg(m, lg.get("outcome"))
                    p = 1.0 if est == "ganada" else (0.0 if est == "perdida" else None)
                if p is None:
                    ok = False
                    break
                prod *= p
            return (prod, "ult") if ok else (None, None)
        tok = _token_de(op) or str(op.get("real_token") or "")
        m = mercado_clob(str(op.get("condition_id") or ""))
        for t in ((m or {}).get("tokens") or []):
            if tok and str(t.get("token_id")) == tok:
                try:
                    p = float(t.get("price") or 0)
                except Exception:
                    p = 0.0
                if 0 < p < 1:
                    return p, "ult"
    except Exception:
        pass
    return None, None


# ============================================
# v12.8.3: EVIDENCIA DE CADENA (fills reales) + CURACIÓN DE ABIERTAS
# ============================================
FILLS_PAGINAS = 3              # páginas de /activity?type=TRADE (500 c/u)
FILL_VENTANA_S = 3600          # un fill puede confirmarse minutos después
FILL_TOL_SHARES = 0.05         # tolerancia de shares entre registro y fill
_FILLS_CACHE = [0.0, []]       # [ts, fills BUY/SELL de la wallet]
_REPARTO_CACHE = [0.0, {}]     # [ts, {titulo_norm: {usdc, shares, por_share}}]


def fills_wallet(refrescar=False, limite=500):
    """v12.8.3: fills REALES de la wallet (data-api /activity?type=TRADE).
    → [{"ts","asset","size","usdc","side","tx","titulo"}]. Es la prueba de que
    una op del bot existió de verdad: el 11-sep se comprobó que Barranquilla
    tiene 4 registros del bot y sólo 2 fills en cadena (03:15:06 y 03:20:52).
    Cache 10 min; si la API falla devuelve lo último que tuvo (o []) ⇒ sin
    prueba NO se descarta nada."""
    ahora = time.time()
    if not refrescar and _FILLS_CACHE[1] and ahora - _FILLS_CACHE[0] < 600:
        return _FILLS_CACHE[1]
    out = []
    try:
        for pag in range(FILLS_PAGINAS):
            url = (f"{DATA_API}/activity?user={WALLET}&limit={limite}"
                   f"&offset={pag * limite}&type=TRADE")
            req = urllib.request.Request(url, headers={"User-Agent": "poly-combos-bot"})
            with urllib.request.urlopen(req, timeout=20) as r:
                parte = json.loads(r.read().decode())
            for a in (parte or []):
                if str(a.get("type", "")).upper() != "TRADE":
                    continue
                try:
                    out.append({"ts": int(a.get("timestamp") or 0),
                                "asset": str(a.get("asset") or ""),
                                "size": float(a.get("size") or 0),
                                "usdc": float(a.get("usdcSize") or 0),
                                "side": str(a.get("side") or ""),
                                "tx": str(a.get("transactionHash") or ""),
                                "titulo": a.get("title") or ""})
                except Exception:
                    continue
            if len(parte or []) < limite:
                break
        if out:
            _FILLS_CACHE[0], _FILLS_CACHE[1] = ahora, out
            log(f"  v12.8.3: {len(out)} fills reales de la wallet (evidencia de cadena)")
    except Exception as e:
        log(f"  fills_wallet: sin datos ({str(e)[:60]})")
    return _FILLS_CACHE[1]


def _tx_de_op(op):
    """v12.8.3: hash (o prefijo) de la tx que el bot guardó para esta op."""
    for k in ("tx_hash", "tx", "txHash"):
        v = str(op.get(k) or "").strip()
        if v.startswith("0x"):
            return v.lower()
    return ""


def casar_fills(ops):
    """v12.8.3: casa cada registro del bot con UN fill real de la cadena.
    Reglas: mismo token (asset), shares ±FILL_TOL_SHARES y hasta 1 h de
    diferencia; si la op guardó tx, manda la tx. Cada fill se usa UNA vez, así
    que los registros sobrantes se quedan sin fill ⇒ duplicados fantasma.
    → (casadas, fantasma, sin_evidencia). sin_evidencia = ops cuyo token no
    aparece NUNCA en /activity: no se juzgan (sin prueba no se borra nada)."""
    fills = fills_wallet()
    por_tok = {}
    for f in fills:
        if f.get("asset"):
            por_tok.setdefault(f["asset"], []).append(f)
    for v in por_tok.values():
        v.sort(key=lambda x: x["ts"])
    usados = set()
    casadas, fantasma, sin_ev = [], [], []
    for op in sorted(ops, key=lambda o: _op_ts(o) or 0):
        tok = _token_de(op) or str(op.get("real_token") or "")
        cands = por_tok.get(tok)
        if not cands:
            sin_ev.append(op)
            continue
        ts_op = _op_ts(op) or 0
        try:
            sh_op = float(op.get("size_shares") or 0)
        except Exception:
            sh_op = 0.0
        tx_op = _tx_de_op(op)
        hit = None
        if tx_op:
            for i, f in enumerate(cands):
                if (tok, i) in usados:
                    continue
                if f["tx"] and f["tx"].lower().startswith(tx_op[:18]):
                    hit = (tok, i)
                    break
        if hit is None:
            mejor, mejor_d = None, None
            for i, f in enumerate(cands):
                if (tok, i) in usados:
                    continue
                if sh_op > 0 and abs(f["size"] - sh_op) > FILL_TOL_SHARES:
                    continue
                d = abs(f["ts"] - ts_op) if (ts_op and f["ts"]) else 10 ** 9
                if d > FILL_VENTANA_S:
                    continue
                if mejor_d is None or d < mejor_d:
                    mejor, mejor_d = (tok, i), d
            hit = mejor
        if hit is None:
            fantasma.append(op)
            continue
        usados.add(hit)
        f = cands[hit[1]]
        op["fill_real"] = {"ts": f["ts"], "size": f["size"], "usdc": f["usdc"],
                           "tx": f["tx"], "side": f["side"]}
        casadas.append(op)
    return casadas, fantasma, sin_ev


def es_basura(op):
    """v12.8.3: registro vacío (sin pregunta, sin legs, sin stake, sin shares).
    No es una operación: es basura de un fallo de red. El panel ya la ocultaba,
    pero seguía contando como "abierta" y confundía el recuento."""
    if op.get("status") == "fallido":
        return False
    q = str(op.get("question") or "").strip()
    try:
        stake = float(op.get("stake_dolares") or 0)
        sh = float(op.get("size_shares") or 0)
    except Exception:
        return False
    return q in ("", "?") and not (op.get("legs") or []) and stake <= 0 and sh <= 0


def curar_abiertas(estado, aplicar=True):
    """🧹 v12.8.3: limpia `trades_copiados` ANTES de resolver nada.
      · registros vacíos (basura) → estado["descartadas"]
      · duplicados fantasma (más registros que fills reales en cadena) → idem
    Devuelve (ops_limpias, info). Con aplicar=False no guarda nada (modo seco).
    Nunca borra sin prueba: si data-api no responde o el token no tiene fills,
    la op se queda donde está."""
    ops = list(estado.get("trades_copiados") or [])
    limpias, basura = [], []
    for op in ops:
        if es_basura(op):
            basura.append(op)
        else:
            limpias.append(op)
    info = {"basura": len(basura), "fantasma": 0, "sin_evidencia": 0,
            "casadas": 0, "antes": len(ops)}
    fantasma = []
    if limpias:
        try:
            casadas, fantasma, sin_ev = casar_fills(limpias)
            info.update(fantasma=len(fantasma), sin_evidencia=len(sin_ev),
                        casadas=len(casadas))
            limpias = casadas + sin_ev
        except Exception as e:
            log(f"  curar_abiertas: dedup omitido ({str(e)[:70]})")
    estado["trades_copiados"] = limpias
    info["cura_info"] = info.copy()
    estado["_cura_info"] = info
    if (basura or fantasma) and aplicar:
        desc = list(estado.get("descartadas") or [])
        ahora = datetime.now(timezone.utc).isoformat()
        for o in basura:
            o["descartada"] = "registro vacío (basura): sin pregunta, stake ni legs"
            o["descartada_en"] = ahora
            desc.append(o)
        for o in fantasma:
            o["descartada"] = ("duplicado fantasma: hay más registros que fills "
                               "reales de ese token en la cadena")
            o["descartada_en"] = ahora
            desc.append(o)
        estado["descartadas"] = desc
        try:
            guardar_estado(estado)
        except Exception as e:
            log(f"  curar_abiertas: no se pudo guardar ({str(e)[:60]})")
        log(f"  🧹 v12.8.3 curación: {len(basura)} basura + {len(fantasma)} duplicados "
            f"fantasma fuera de ABIERTAS · quedan {len(limpias)} registros "
            f"({info['casadas']} casados con fill real, {info['sin_evidencia']} sin evidencia)")
    return limpias, info


def _reparto_mapa(estado=None, forzar=False):
    """💰 v12.8.3: reparte el usdcSize de cada REDEEM entre TODOS los fills del
    mismo mercado (por título normalizado) en proporción a sus shares.
    → {titulo_norm: {"usdc","shares","por_share"}}. Cache 5 min.
    Sin esto, cada fill de una posición se anotaba el cobro ENTERO: con los 4
    registros de Barranquilla (2 fantasma) eso habría inventado 4×$9.90."""
    ahora = time.time()
    if not forzar and _REPARTO_CACHE[1] and ahora - _REPARTO_CACHE[0] < 300:
        return _REPARTO_CACHE[1]
    try:
        cobros_wallet()
    except Exception:
        pass
    titulos = _COBROS_CACHE[2] or {}
    est = estado if estado is not None else cargar_estado()
    ops = [o for o in (list(est.get("trades_copiados") or [])
                       + list(est.get("historial") or []))
           if not o.get("descartada")]
    por_titulo = {}
    for o in ops:
        t = _norm_titulo(o.get("question"))
        if not t:
            continue
        try:
            por_titulo[t] = por_titulo.get(t, 0.0) + float(o.get("size_shares") or 0)
        except Exception:
            continue
    mapa = {}
    for t, g in titulos.items():
        try:
            usdc = float(g.get("usdc") or 0)
        except Exception:
            usdc = 0.0
        if usdc <= 0.000001:
            continue
        sh = por_titulo.get(t, 0.0)
        mapa[t] = {"usdc": round(usdc, 6), "shares": round(sh, 6),
                   "por_share": round(usdc / sh, 6) if sh > 0 else None}
    _REPARTO_CACHE[0], _REPARTO_CACHE[1] = ahora, mapa
    return mapa


def reparto_cobro(op):
    """v12.8.3: qué parte del cobro REAL le toca a esta op (o None)."""
    tit = _norm_titulo(op.get("question"))
    if not tit:
        return None
    return _reparto_mapa().get(tit)


# ============================================
# v12.8.3: 🔍 LEER AHORA (lectura inmediata, SÓLO MIRAR)
# ============================================
LECTURA_LOCK = threading.Lock()


def _eta_txt(ts):
    """v12.8.3: 'en 7 min 12 s' / 'ahora mismo' para la próxima pasada."""
    try:
        d = max(0, int(float(ts) - time.time()))
    except Exception:
        return "—"
    if d < 5:
        return "ahora mismo"
    m, s = divmod(d, 60)
    if m >= 60:
        return f"en {m // 60} h {m % 60} min"
    return f"en {m} min {s:02d} s" if m else f"en {s} s"


def cmd_leer_ahora(chat_id):
    """🔍 v12.8.3 — LECTURA INMEDIATA, SÓLO MIRAR (botón 🔍 Leer ahora / /leer).
    Fuerza una lectura AHORA sin esperar al intervalo ⏱ y cuenta qué ve:
    bankroll, catálogo RFQ, qué combo abriría (y por qué no), cada posición
    abierta con su situación REAL (viva / suspendida / anulada / resuelta) y lo
    que hay sin cobrar. NO abre operaciones, NO vende, NO archiva y NO toca el
    estado: la pasada AUTO sigue programada a su hora. Hilo propio con
    LECTURA_LOCK (no bloquea las pasadas ni se solapa consigo mismo)."""
    if not LECTURA_LOCK.acquire(blocking=False):
        return enviar(chat_id, "🔍 Ya hay una lectura en curso, espera unos segundos.")

    def _run():
        t0 = time.time()
        try:
            enviar(chat_id, "🔍 Leyendo ahora… _(sólo mirar: no abre ni vende nada)_")
            estado = {}
            try:
                estado = cargar_estado() or {}
            except Exception as e:
                log(f"  [LEER] estado: {e}")
            mins = intervalo_min_actual() or max(1, int(INTERVALO_AUTO_S // 60))
            eta = datetime.fromtimestamp(NEXT_PASADA_TS, tz=timezone.utc).strftime("%H:%M:%S")
            L = [f"🔍 *LECTURA AHORA* · {datetime.now(timezone.utc).strftime('%d-%m %H:%M:%S')} UTC",
                 (f"Modo *{MODO_OPERACION}* · pasada cada *{mins} min* ✅ · "
                  f"próxima lectura {_eta_txt(NEXT_PASADA_TS)} ({eta} UTC) · "
                  f"hoy {ops_pagadas_hoy(estado)}/{max_ops(estado)} ops · "
                  f"prob mín {prob_nivel_txt(prob_min_auto(estado))}")]
            try:
                _prune_propuestas()          # v12.8.4: propuestas SEMI vivas
                if PROPUESTAS:
                    _ul = max(v[0] for v in PROPUESTAS.values())
                    _q = max(0, int((PROPUESTA_VALIDA_S - (time.time() - _ul)) // 60))
                    L.append(f"🟡 Propuestas SEMI vivas: *{len(PROPUESTAS)}* "
                             f"(la última caduca en ~{_q} min)")
            except Exception:
                pass
            try:
                sal = saldo_disponible_clob()
                L.append(f"💵 Disponible en la wallet: *${float(sal):.2f}*"
                         if sal is not None else "💵 Disponible: sin dato (proxy/credenciales)")
            except Exception as e:
                L.append(f"💵 Disponible: sin dato ({str(e)[:50]})")
            # ---- catálogo RFQ: qué abriría (SIN abrirlo)
            try:
                legs = listar_combos() or []
                sel = seleccionar_combo(legs, estado) if legs else None
                if sel:
                    prod = 1.0
                    for c in sel:
                        prod *= float(c.get("yes_price") or 0)
                    cuota = round(1 / prod, 2) if prod > 0 else 0.0
                    blk = [f"🎯 *Qué abriría ahora*: combo de {len(sel)} legs · "
                           f"cuota ~{cuota:.2f} · prob ~{prod * 100:.0f}%"]
                    for c in sel:
                        blk.append(f"   • {str(c.get('question') or c.get('slug') or '?')[:74]}"
                                   f" @ {float(c.get('yes_price') or 0):.3f}")
                    try:
                        stk = stake_operacion(estado, cuota, prod)
                        blk.append(f"   Stake que usaría: ${float(stk):.2f}")
                    except Exception:
                        pass
                    blk.append("   _NO se ha abierto: esto sólo lee_")
                    L.append("\n".join(blk))
                else:
                    L.append(f"🎯 *Qué abriría ahora*: NADA — {len(legs)} legs en el catálogo, "
                             f"ninguna combinación pasa el filtro (cuota {CUOTA_MIN}-{CUOTA_MAX}, "
                             f"prob ≥{prob_nivel_txt(prob_min_auto(estado))}, eventos distintos, "
                             f"cooldown de legs, tope {ops_pagadas_hoy(estado)}/{max_ops(estado)} hoy)")
            except Exception as e:
                L.append(f"🎯 Catálogo RFQ: sin lectura ({str(e)[:70]})")
            # ---- posiciones abiertas con su situación REAL
            try:
                ops = [o for o in (estado.get("trades_copiados") or [])
                       if o.get("status") != "fallido"
                       and str(o.get("question", "")).strip() not in ("", "?")
                       and (float(o.get("stake_dolares") or 0) > 0 or o.get("legs"))]
                grupos = agrupar_abiertas(ops)
                if not grupos:
                    L.append("📂 *Posiciones abiertas*: ninguna")
                else:
                    extra = f" ({len(ops)} fills)" if len(ops) != len(grupos) else ""
                    blk = [f"📂 *Posiciones abiertas*: {len(grupos)}{extra}"]
                    for i, g in enumerate(grupos[:12], 1):
                        op0 = g["ops"][0]
                        sh = sum(float(o.get("size_shares") or 0) for o in g["ops"])
                        st = sum(float(o.get("stake_dolares") or 0) for o in g["ops"])
                        _cl, sit = situacion_op(op0)
                        linea = f"\n*#{i}* {str(op0.get('question', '?'))[:78]}"
                        if len(g["ops"]) > 1:
                            linea += f"  ×{len(g['ops'])} fills"
                        linea += f"\n   ${st:.2f} · {sh:.2f} sh · {sit}"
                        p, fte = precio_vivo_op(op0)
                        if p and sh > 0:
                            tag = "precio ahora" if fte == "mid" else "últ. precio (libro cerrado)"
                            linea += (f"\n   📈 {tag} {p:.3f} (~{p * 100:.0f}%) · "
                                      f"valor ~${sh * p:.2f} vs pago ${sh:.2f}")
                        else:
                            linea += "\n   📈 precio: n/d"
                        if op0.get("fin_previsto"):
                            linea += f"\n   🏁 fin previsto {op0['fin_previsto']}"
                        blk.append(linea)
                    if len(grupos) > 12:
                        blk.append(f"\n_… y {len(grupos) - 12} posiciones más_")
                    L.append("\n".join(blk))
            except Exception as e:
                L.append(f"📂 Abiertas: sin lectura ({str(e)[:70]})")
            # ---- sin cobrar + última curación + stats
            try:
                rec = {k: v for k, v in (estado.get("reclamos_avisados") or {}).items()
                       if float(v.get("importe") or 0) > 0.000001}   # v12.8.4
                if rec:
                    imp = sum(float(v.get("importe") or 0) for v in rec.values())
                    L.append(f"💰 *Sin cobrar*: {len(rec)} posiciones · ${imp:.2f} — "
                             f"reclamación abierta con soporte (/reclamar)")
                else:
                    L.append("💰 *Sin cobrar*: nada pendiente según el último aviso")
            except Exception as e:
                L.append(f"💰 Sin cobrar: sin dato ({str(e)[:50]})")
            try:
                aud = estado.get("ultimo_auditoria_resumen") or {}
                if aud:
                    L.append(f"🩺 Última auto-curación: {_madrid(estado.get('ultima_auditoria'))} · "
                             f"⏳{aud.get('reabiertas', 0)} ✏️{aud.get('corregidas', 0)} "
                             f"🏁{aud.get('nuevas_cerradas', 0)} · "
                             f"PnL archivadas ${float(aud.get('pnl_despues') or 0):+.2f}")
                desc = estado.get("descartadas") or []
                if desc:
                    L.append(f"🧹 Registros descartados (basura/duplicados): {len(desc)}")
            except Exception:
                pass
            try:
                s = calcular_stats()
                L.append(f"📊 PnL total *${s['pnl']:+.2f}* · ✅{s['wins']} ❌{s['losses']}"
                         + (f" ↩️{s.get('anuladas', 0)} anuladas" if s.get("anuladas") else ""))
            except Exception:
                pass
            L.append(f"_Leído en {time.time() - t0:.1f} s · esto NO abre ni vende nada · "
                     f"la pasada AUTO sigue a su hora ({mins} min ✅)_")
            enviar_largo(chat_id, "\n\n".join(L))
            log(f"  [LEER] lectura inmediata completada en {time.time() - t0:.1f} s (sólo mirar)")
        except Exception as e:
            log(f"  [LEER] error: {e}")
            try:
                enviar(chat_id, f"🔍 La lectura ha fallado: {str(e)[:150]}")
            except Exception:
                pass
        finally:
            try:
                LECTURA_LOCK.release()
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()
    return None



# ============================================
# v12.8.4: 🟡 SEMI DE VERDAD (propuesta + ✅/❌, caduca a los 10 min)
# ============================================
PROPUESTAS = {}          # h8 -> (ts, sel, chat_id, texto)


def _prune_propuestas():
    """v12.8.4: tira las propuestas caducadas (las vivas se quedan)."""
    global PROPUESTAS
    ahora = time.time()
    PROPUESTAS = {k: v for k, v in PROPUESTAS.items()
                  if ahora - v[0] < PROPUESTA_VALIDA_S}


def _sin_tick(t):
    """✅ v12.8.4: quita el tick de un texto de botón para casar con el handler
    (el botón activo llega como "🟡 SEMI ✅" y el handler compara "🟡 SEMI")."""
    return str(t or "").replace(TICK_ACTIVO, "").strip()


def proponer_combo_semi(chat_id, sel, estado=None):
    """🟡 v12.8.4: en SEMI el bot NO compra: PROPONE el combo con botones
    ✅ Aceptar / ❌ Descartar y espera. Caduca a los PROPUESTA_VALIDA_S (10 min).
    No reserva la huella (si no, el anti-duplicados bloquearía tu propio ✅);
    la reserva la hace ejecutar_combo_rfq al aceptar, como en AUTO."""
    _prune_propuestas()
    estado = estado if estado is not None else cargar_estado()
    pids = [str(c.get("yes_token")) for c in sel]
    if huella_combo(pids) in (estado.get("combos_rfq", {}) or {}).get("huellas", {}):
        log("  [SEMI] combo ya operado: no se propone")
        return None
    h8 = hash8_sel(sel)
    if any(hash8_sel(v[1]) == h8 for v in PROPUESTAS.values()):
        log(f"  [SEMI] ya hay una propuesta viva para este combo ({h8})")
        return None
    prod = 1.0
    for c in sel:
        prod *= float(c.get("yes_price") or 0)
    cuota_est = round(1 / prod, 2) if prod > 0 else 0.0
    try:
        stake = float(stake_operacion(estado, cuota_est, cuota_est) or 0)
    except Exception:
        stake = 0.0
    if stake < STAKE_MIN_AUTO:
        stake = STAKE_MIN_AUTO
    gana = round(stake * max(0.0, cuota_est - 1), 2)
    cuota_min_real = round(cuota_est * (1 + VENTAJA_MIN_EV), 2)
    caduca = datetime.fromtimestamp(time.time() + PROPUESTA_VALIDA_S,
                                    tz=timezone.utc).strftime("%H:%M:%S")
    txt = (f"🟡 *SEMI — PROPUESTA* (caduca en {int(PROPUESTA_VALIDA_S // 60)} min)\n\n"
           f"🎫 Combo de {len(sel)} legs · cuota est. *{cuota_est:.2f}* · "
           f"prob *{prod * 100:.0f}%*\n")
    for c in sel:
        txt += (f"   · {str(c.get('question') or '?')[:64]} "
                f"(p={float(c.get('yes_price') or 0):.2f})\n")
    txt += (f"💵 Stake previsto *${stake:.2f}* · ganancia si acierta *+${gana:.2f}*\n"
            f"⚖️ Al aceptar pediré cotización NUEVA (las del RFQ viven segundos) y sólo "
            f"compro si mejora el mercado ≥{int(VENTAJA_MIN_EV * 100)}% "
            f"(cuota real ≥{cuota_min_real:.2f}). Si no, te lo digo y no gasto nada.\n"
            f"🔢 hoy {ops_pagadas_hoy(estado)}/{max_ops(estado)} ops · ⏱ caduca {caduca} UTC")
    kb = {"inline_keyboard": [
        [{"text": "✅ Aceptar y comprar", "callback_data": f"sm:{h8}"},
         {"text": "❌ Descartar", "callback_data": f"smx:{h8}"}]]}
    PROPUESTAS[h8] = (time.time(), sel, chat_id, txt)
    log(f"  [SEMI] propuesta {h8}: {len(sel)} legs · cuota est {cuota_est} · "
        f"prob {prod:.2f} · stake ${stake} · caduca en {int(PROPUESTA_VALIDA_S // 60)} min")
    return enviar(chat_id, txt, kb)


def ejecutar_semi_aprobado(chat_id, sel, h8=None):
    """✅ v12.8.4: aprobaste la propuesta → se ejecuta por la MISMA ruta que
    AUTO (stake dinámico con la cuota real, filtro de ventaja, tope diario y
    anti-duplicados). Hilo propio serializado con PASADA_LOCK."""
    PROPUESTAS.pop(h8, None)
    titulo = " + ".join(str(c.get("question", "?"))[:38] for c in sel)

    def _run():
        try:
            with PASADA_LOCK:
                estado = cargar_estado()
                _mx, _hoy = max_ops(estado), ops_pagadas_hoy(estado)
                if _hoy >= _mx:
                    return enviar(chat_id, f"⛔ *Tope diario alcanzado* ({_hoy}/{_mx} ops pagadas hoy)")
                pids = [str(c.get("yes_token")) for c in sel]
                if huella_combo(pids) in (estado.get("combos_rfq", {}) or {}).get("huellas", {}):
                    return enviar(chat_id, f"⛔ *Combo ya operado* (anti-duplicados):\n{titulo[:80]}")
                log(f"[SEMI] aprobado con ✅: {titulo[:70]}")
                enviar(chat_id, f"✅ *SEMI aprobado* — pidiendo cotización nueva…\n📌 {titulo[:80]}")
                ok, res = ejecutar_combo_rfq(sel, chat_id=chat_id, franja="base")
                if not ok:
                    enviar(chat_id, f"❌ *No comprado* (tu ✅ no ha gastado nada)\n"
                                    f"📌 {titulo[:70]}\nMotivo: `{str(res)[:70]}`")
        except Exception as e:
            log(f"[SEMI] error: {e}")
            try:
                enviar(chat_id, f"❌ Error ejecutando la propuesta: {str(e)[:100]}")
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


def _marcar_propuesta(chat_id, message_id, etiqueta):
    """v12.8.4: sustituye los botones de la propuesta por su resultado, para que
    nadie pueda pulsar ✅ dos veces ni aceptar una propuesta caducada."""
    if not chat_id or not message_id:
        return
    try:
        telegram_api("editMessageReplyMarkup", {
            "chat_id": chat_id, "message_id": message_id,
            "reply_markup": json.dumps({"inline_keyboard": [
                [{"text": etiqueta, "callback_data": "noop"}]]})})
    except Exception as e:
        log(f"  [SEMI] sin editar botones: {str(e)[:60]}")


def respuesta_propuesta(cbq, h8, aceptar):
    """v12.8.4: atiende ✅/❌ de una propuesta SEMI, con caducidad de 10 min."""
    cbid = cbq.get("id")
    msg = cbq.get("message") or {}
    cid = (msg.get("chat") or {}).get("id") or (cbq.get("from") or {}).get("id")
    mid = msg.get("message_id")
    hit = PROPUESTAS.get(h8)
    if not hit or time.time() - hit[0] > PROPUESTA_VALIDA_S:
        PROPUESTAS.pop(h8, None)
        telegram_api("answerCallbackQuery", {
            "callback_query_id": cbid, "show_alert": True,
            "text": (f"⌛ Propuesta caducada o ya atendida (valía "
                     f"{int(PROPUESTA_VALIDA_S // 60)} min). No se compra dos veces: "
                     "la pasada SEMI siguiente te propondrá otro combo.")})
        _marcar_propuesta(cid, mid, "⌛ caducada")
        log(f"  [SEMI] propuesta {h8} caducada (pulsada fuera de tiempo)")
        return
    if not aceptar:
        PROPUESTAS.pop(h8, None)
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid, "text": "❌ Descartada"})
        _marcar_propuesta(cid, mid, "❌ descartada")
        log(f"  [SEMI] propuesta {h8} descartada por el usuario")
        return enviar(cid, "❌ *Propuesta descartada* — no se ha comprado nada ($0).\n"
                           "_La pasada SEMI siguiente te propondrá otro combo._")
    telegram_api("answerCallbackQuery", {"callback_query_id": cbid,
                                         "text": "✅ Aceptada, pidiendo cotización…"})
    _marcar_propuesta(cid, mid, "✅ aceptada")
    return ejecutar_semi_aprobado(cid, hit[1], h8)


def cmd_status(chat_id):
    global CHAT_ID
    CHAT_ID = chat_id
    s = calcular_stats()
    _est = cargar_estado()
    _mx = max_ops(_est)
    _hoy = ops_pagadas_hoy(_est)
    _aud = _est.get("ultimo_auditoria_resumen") or {}
    _aud_txt = (f"🩺 Auto-curación: {_madrid(_est.get('ultima_auditoria')) if _est.get('ultima_auditoria') else '—'}"
                + (f" · ⏳{_aud.get('reabiertas', 0)} ✏️{_aud.get('corregidas', 0)} "
                   f"🏁{_aud.get('nuevas_cerradas', 0)}\n" if _aud else " (sin ejecutar aún)\n"))
    # v12.8.4: sólo los avisos con dinero DE VERDAD (importe 0 = "ya revisado:
    # saldo 0 on-chain", que no es un reclamo pendiente)
    _rec = {k: v for k, v in (_est.get("reclamos_avisados") or {}).items()
            if float(v.get("importe") or 0) > 0.000001}
    _rec_txt = (f"💰 Sin cobrar (último aviso): *{len(_rec)}* "
                f"(${sum(float(v.get('importe') or 0) for v in _rec.values()):.2f}) "
                f"· /reclamar\n" if _rec else "")
    texto = (f"📊 *ESTADO v12.9.0 (Combos)*\n\n"
             f"Modo: *{MODO_OPERACION}*\n"
             f"Stake: *{stake_txt(_est)}*\n"
             f"Cuota: *{CUOTA_MIN}-{CUOTA_MAX}*\n"
             f"🔢 Máx ops/día: *{_mx}* (hoy {_hoy})\n"
             f"🎯 Prob AUTO: *{prob_nivel_txt(prob_min_auto(_est))}*\n"
             f"Trades: *{s['total']}*\n"
             f"PnL: *${s['pnl']:+.2f}*\n"
             f"{_aud_txt}"
             f"{_rec_txt}"
             f"Proxy: `{PROXY_URL}`\n"
             f"Hora: {datetime.now().strftime('%H:%M:%S')}")
    return enviar(chat_id, texto)


# ============================================
# AUTO LOOP
# ============================================
def auto_pasada(chat_id):
    """v11: lee el CATALOGO DE LEGS, construye un combo real (2-3 piernas,
    eventos distintos, cuota en rango, sin repetir legs recientes) y lo
    ejecuta via RFQ (quote → firma Exchange v3 → accept → FILLED).
    Max 1 combo por pasada + tope diario. La via CLOB de legs sueltos
    (ejecutar_trade) queda DESACTIVADA en AUTO: no eran combos reales."""
    if MODO_OPERACION not in ("AUTO", "SEMI"):
        return                      # v12.8.4: en SEMI también hay pasada (propone)
    log(f"[{MODO_OPERACION}] pasada (combos RFQ v11)")
    try:
        legs = listar_combos()
    except Exception as e:
        log(f"  listar error: {e}")
        return
    if not legs:
        log("  sin legs disponibles")
        return
    estado = cargar_estado()
    sel = seleccionar_combo(legs, estado)
    if not sel:
        log("  sin combos viables esta pasada (eventos distintos, cuota, cooldown, tope)")
        return
    if MODO_OPERACION == "SEMI":
        # 🟡 v12.8.4: SEMI de verdad — PROPONE y espera tu ✅ (caduca a los 10 min)
        proponer_combo_semi(chat_id, sel, estado)
        return
    ok, res = ejecutar_combo_rfq(sel, chat_id)
    if ok:
        log(f"  ✅ combo OK: {str(res)[:110]}")
    else:
        log(f"  ❌ combo: {str(res)[:130]}")

def auto_loop():
    """v11.1: tick de 5s + próxima pasada programada, para que cambiar el
    intervalo con los botones ⏱ surta efecto inmediato (antes el sleep de
    300s bloqueaba hasta terminar).
    v12.7: también dispara la AUTO-CURACIÓN (re-auditoría) sola: al arrancar y
    cada AUDITORIA_CADA_H horas, serializada con las pasadas (PASADA_LOCK).
    v12.8.4: en SEMI también hay pasada, pero PROPONE (✅/❌) en vez de comprar.
    v12.9.0: además lanza la ronda 📡 de copy-trading EN PAPEL cada COPY_SONDEO_S
    (lectura pública, sin proxy y sin firmar nada)."""
    global NEXT_PASADA_TS, NEXT_AUDITORIA_TS, NEXT_COPY_TS
    while True:
        try:
            ahora = time.time()
            if MODO_OPERACION in ("AUTO", "SEMI") and CHAT_ID and ahora >= NEXT_PASADA_TS:
                programar_paso(ahora + INTERVALO_AUTO_S)
                with PASADA_LOCK:
                    auto_pasada(CHAT_ID)
        except Exception as e:
            log(f"auto_loop error: {e}")
        # 📡 v12.9.0: seguimiento en papel de los top (no depende del modo y NO
        # gasta dinero: sólo lee ranking/fills/mids y anota señales)
        try:
            if COPY_ACTIVO and CHAT_ID and time.time() >= NEXT_COPY_TS:
                NEXT_COPY_TS = time.time() + COPY_SONDEO_S
                with PASADA_LOCK:
                    copy_pasada(CHAT_ID)
        except Exception as e:
            log(f"copy_loop error: {e}")
        # v12.7: auto-curación (no depende del modo: corrige el histórico igual)
        try:
            if time.time() >= NEXT_AUDITORIA_TS and AUDITORIA_LOCK.acquire(blocking=False):
                try:
                    NEXT_AUDITORIA_TS = time.time() + AUDITORIA_CADA_S
                    with PASADA_LOCK:
                        reauditar_estado(chat_id=CHAT_ID, aplicar=True, con_saldo=False,
                                         origen="auto", silencioso=True)
                        reclamar_check()      # v12.8: avisa de ganadas sin cobrar
                finally:
                    AUDITORIA_LOCK.release()
        except Exception as e:
            log(f"auto_auditoria error: {e}")
        time.sleep(5)


# ============================================
# LOOP TELEGRAM
# ============================================
def lanzar_combo_manual(chat_id, sel, franja="base"):
    """v12.0: ejecuta un combo elegido por botón (franja base/extendida/super).
    Hilo propio SERIALIZADO con el auto_loop (PASADA_LOCK); anti-duplicados y
    cupo diario por franja dentro del lock."""
    pids = [str(c.get("yes_token")) for c in sel]
    titulo = " + ".join(str(c.get("question", "?"))[:38] for c in sel)
    mk = FRANJA_ICO.get(franja, "").strip()

    def _run():
        try:
            with PASADA_LOCK:
                estado = cargar_estado()
                _mx = max_ops(estado)
                _hoy = ops_pagadas_hoy(estado)
                if _hoy >= _mx:
                    return enviar(chat_id, f"⛔ *Tope diario alcanzado* ({_hoy}/{_mx} ops pagadas hoy)\nCámbialo en 🔢 Máx ops/día (desde {OPS_PIN_DESDE} pide código 🔐).")
                if franja == "extendida" and extendidas_hoy_count(estado) >= MAX_EXT_DIA:
                    return enviar(chat_id, f"⛔ *Cupo de extendidas agotado hoy* ({MAX_EXT_DIA}/{MAX_EXT_DIA}) 🚀\nMañana más.")
                if franja == "super" and supers_hoy_count(estado) >= MAX_SUPER_DIA:
                    return enviar(chat_id, f"⛔ *Cupo de súper combos agotado hoy* ({MAX_SUPER_DIA}/{MAX_SUPER_DIA}) 💥\nMañana más.")
                if huella_combo(pids) in estado.get("combos_rfq", {}).get("huellas", {}):
                    return enviar(chat_id, f"⛔ *Combo ya operado* (anti-duplicados):\n{titulo[:80]}")
                _prod = 1.0
                for _c in sel:
                    _prod *= float(_c.get("yes_price") or 0)
                _cest = round(1 / _prod, 2) if _prod > 0 else 0
                _stake = stake_operacion(estado, _cest, _cest, manual=True)
                log(f"[MANUAL{' ' + mk if mk else ''}] botón ▶️: {titulo[:70]} · stake ${_stake}")
                _stxt = (f"AUTO ${_stake} (cuota ~{_cest})"
                         if str(estado.get("stake_mode", "AUTO")).upper() == "AUTO"
                         else f"FIJO ${_stake}")
                enviar(chat_id, f"▶️ *EJECUTANDO COMBO MANUAL*{' ' + mk if mk else ''}\n📌 {titulo[:80]}\n"
                                f"💵 {_stxt} · pidiendo quote RFQ…")
                ok, res = ejecutar_combo_rfq(sel, chat_id=chat_id, franja=franja, stake=_stake)
                if not ok:
                    enviar(chat_id, f"❌ *Combo manual no ejecutado*\n📌 {titulo[:70]}\nMotivo: `{str(res)[:60]}`")
        except Exception as e:
            log(f"[MANUAL] error: {e}")
            try:
                enviar(chat_id, f"❌ Error lanzando combo manual: {str(e)[:80]}")
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()


def procesar_callback(cbq):
    """v11.8: botones inline ▶️ del catálogo (callback_query)."""
    msg = cbq.get("message") or {}
    cid = (msg.get("chat") or {}).get("id") or (cbq.get("from") or {}).get("id")
    cbid = cbq.get("id")
    data = str(cbq.get("data") or "")
    if cid:
        global CHAT_ID
        if cid != CHAT_ID:
            CHAT_ID = cid
            try:
                _est = cargar_estado()
                _est["chat_id"] = cid
                guardar_estado(_est)
            except Exception:
                pass
    if (data.startswith("ej:") or data.startswith("sp:")) and cid:
        h8 = data.split(":")[-1]
        hit = CATALOGO_CACHE.get(h8)
        if not hit or time.time() - hit[0] > 3600:
            telegram_api("answerCallbackQuery", {"callback_query_id": cbid,
                         "text": "Catálogo caducado: pulsa 📋 Trades o 💥 SúperCombos otra vez", "show_alert": True})
            return
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid, "text": "Lanzando combo…"})
        lanzar_combo_manual(cid, hit[1], hit[2] if len(hit) > 2 else "base")
        return
    if data.startswith("lb:") and cid:       # v12.9.0: 🏆 ventana del ranking
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid})
        return cmd_top(cid, data.split(":", 1)[1])
    if data.startswith("sm:") and cid:       # v12.8.4: 🟡 SEMI ✅ aceptar
        return respuesta_propuesta(cbq, data.split(":", 1)[1], True)
    if data.startswith("smx:") and cid:      # v12.8.4: 🟡 SEMI ❌ descartar
        return respuesta_propuesta(cbq, data.split(":", 1)[1], False)
    if data.startswith("mx:") and cid:
        acc = data.split(":", 1)[1]
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid})
        if acc == "menu":
            return max_combos_menu(cid)
        try:
            v = int(acc)
        except Exception:
            return
        if v not in OPS_MAX_VALORES:
            return enviar(cid, "❌ Topes disponibles: 5, 10, 20, 30 o 50")
        if v >= OPS_PIN_DESDE:
            return set_max_ops_dia(cid, v, pendiente=True) or pin_menu(cid)
        return set_max_ops_dia(cid, v)
    if data == "mxp:v" and cid:
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid})
        return enviar(cid, f"👁 Tu código de 4 cifras: `{codigo_pin()}`\n_Se pide al fijar un máximo de {OPS_PIN_DESDE} o más operaciones/día_")
    if data == "mxp:x" and cid:
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid})
        return
    if data.startswith("pn:") and cid:
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid})
        return pin_tecla(cid, data.split(":", 1)[1])
    if data.startswith("st:") and cid:
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid})
        acc = data.split(":", 1)[1]
        if acc == "menu":
            return stake_menu(cid)
        if acc == "auto":
            set_stake_mode("AUTO")
            est = cargar_estado()
            est["stake_mode"] = "AUTO"
            guardar_estado(est)
            log("stake -> AUTO 5-10")
            return enviar(cid, f"💵 *Stake AUTO ${STAKE_MIN_AUTO:.0f}-${STAKE_MAX_AUTO:.0f}*\n_Decide el bot según la cuota y cómo va la combinada: cuota 1.2 ⇒ ${STAKE_MAX_AUTO:.0f} · 2.0 ⇒ $8 · 2.5 ⇒ $7.4 · 5 ⇒ $6.2; la ventaja real del RFQ lo ajusta y si no mejora el mercado, no apuesta_")
        if acc == "fijo":
            set_stake_mode("FIJO")
            est = cargar_estado()
            est["stake_mode"] = "FIJO"
            try:
                _sf = float(est.get("stake", STAKE_POR_TRADE) or STAKE_POR_TRADE)
            except Exception:
                _sf = float(STAKE_POR_TRADE)
            est["stake"] = _sf
            guardar_estado(est)
            log(f"stake -> FIJO {_sf}")
            return enviar(cid, f"💵 *Stake FIJO ${_sf:.2f}*\n_Cámbialo con /stake 7 · vuelve al dinámico con /stake auto_")
        return
    if data.startswith("pb:") and cid:
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid})
        acc = data.split(":", 1)[1]
        if acc == "x":
            return
        if acc == "menu":
            return prob_menu(cid)
        return set_prob_min_auto(cid, acc)
    if data.startswith("cc:") and cid:
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid, "text": "Cerrando posición…"})
        return cerrar_desde_boton(data.split(":", 1)[1], cid)
    telegram_api("answerCallbackQuery", {"callback_query_id": cbid})


def procesar_update(update):
    global CHAT_ID
    if "callback_query" in update:
        try:
            return procesar_callback(update["callback_query"])
        except Exception as e:
            log(f"callback error: {e}")
            return
    if "message" not in update:
        return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    if chat_id != CHAT_ID:
        CHAT_ID = chat_id
        try:   # v11.4: persistir chat para que AUTO continúe tras reinicios
            _est = cargar_estado()
            _est["chat_id"] = chat_id
            guardar_estado(_est)
        except Exception:
            pass
    if isinstance(PIN_ESPERA, dict) and _re.match(r"^\d{1,4}$", text):
        for ch in text:
            pin_tecla(chat_id, ch)
            if not isinstance(PIN_ESPERA, dict):
                break
        return
    if text == "📋 Trades":
        return cmd_trades(chat_id)
    elif text == "💥 SúperCombos":
        return cmd_super(chat_id)
    elif text == "💰 Saldo":
        return cmd_saldo(chat_id)
    elif text == "📂 Abiertas":
        return cmd_abiertas(chat_id)
    elif text == "✅ Cerradas":
        return cmd_cerradas(chat_id)
    elif text == "📊 Stats":
        return cmd_stats(chat_id)
    elif text == "📡 Copy":                  # v12.9.0: seguimiento en papel
        return cmd_copy(chat_id)
    elif text == "🏆 Top":
        return cmd_top(chat_id)
    elif _sin_tick(text) == "🟢 AUTO":     # v12.8.4: el activo llega con ✅
        return cmd_modo(chat_id, "AUTO")
    elif _sin_tick(text) == "🟡 SEMI":
        return cmd_modo(chat_id, "SEMI")
    elif _sin_tick(text) == "🔴 OFF":
        return cmd_modo(chat_id, "OFF")
    elif text == "💵 Stake AUTO":
        return cmd_stake(chat_id, "auto")
    elif text.startswith("💵 Stake $"):
        try:
            v = float(text.replace("💵 Stake $", "").strip())
            return cmd_stake(chat_id, str(v))
        except:
            return enviar(chat_id, "❌")
    elif text == "🔢 Máx ops/día":
        return max_combos_menu(chat_id)
    elif text == "🎯 Prob AUTO":
        return prob_menu(chat_id)
    elif text == "💰 Reclamar":          # v12.8
        return cmd_reclamar(chat_id)
    elif text.startswith("🔍 Leer") or text in ("/leer", "/leerahora"):
        return cmd_leer_ahora(chat_id)   # v12.8.3: sólo mirar, no abre nada
    if text.startswith("⏱"):
        return cmd_intervalo(chat_id, text)
    if _re.match(r"^\d{1,2}\s*(min|minutos|m|minutes?)\b$", text, _re.IGNORECASE):
        return cmd_intervalo(chat_id, text)   # v11.4: texto manual "30 minutos"
    if text == "/prob":
        return prob_menu(chat_id)
    if text.startswith("/testcerrar"):
        return cmd_testcerrar(chat_id, text)
    if text.startswith("/reauditar"):
        return cmd_reauditar(chat_id, text.replace("/reauditar", "", 1))
    if text.startswith("/reclamar"):     # v12.8
        return cmd_reclamar(chat_id, text.replace("/reclamar", "", 1))
    if text.startswith("/cerrar"):
        return cmd_cerrar(chat_id, text.replace("/cerrar", "", 1))
    if text == "/testcombo":
        return cmd_testcombo(chat_id)
    elif text == "/fills":
        return cmd_fills(chat_id)
    if text == "/start":
        cmd_start(chat_id)
        if MODO_OPERACION == "AUTO":
            programar_pasada_ahora()   # v11.3: sin hilo paralelo
        return
    elif text == "/trades":
        return cmd_trades(chat_id)
    elif text == "/stats":
        return cmd_stats(chat_id)
    elif text == "/abiertas":
        return cmd_abiertas(chat_id)
    elif text == "/cerradas":
        return cmd_cerradas(chat_id)
    elif text == "/saldo":
        return cmd_saldo(chat_id)
    elif text in ("/copy", "/copytrading", "/señales", "/senales"):
        return cmd_copy(chat_id)          # v12.9.0
    elif text == "/top":
        return cmd_top(chat_id)
    elif text.startswith("/auto"):
        parts = text.split()
        return cmd_modo(chat_id, parts[1] if len(parts) > 1 else "AUTO")
    elif text.startswith("/stake"):
        parts = text.split()
        return cmd_stake(chat_id, parts[1] if len(parts) > 1 else "2.0")
    elif text in ("/status", "/estado"):
        return cmd_status(chat_id)

def bot_loop():
    log("v12.9.0 iniciado")
    offset = 0
    while True:
        try:
            params = {"timeout": 30, "offset": offset}
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                data=data)
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read())
            if result.get("ok"):
                for update in result.get("result", []):
                    offset = update["update_id"] + 1
                    try: procesar_update(update)
                    except Exception as e: log(f"update err: {e}")
        except Exception as e:
            log(f"loop err: {e}")
            time.sleep(5)

def main():
    if not cargar_token():
        log("ERROR: no se encontró el token")
        return
    global INTERVALO_AUTO_S, CHAT_ID, NEXT_PASADA_TS, STAKE_MODE, MAX_OPS_DIA, PROB_MIN_AUTO
    _est0 = cargar_estado()
    _im = _est0.get("intervalo_min")
    if _im in INTERVALOS_MIN:
        INTERVALO_AUTO_S = _im * 60
        log(f"intervalo AUTO restaurado: {_im} min")
    restaurar_modo(_est0)   # 🟡 v12.8.4: SEMI/OFF sobreviven al reinicio
    programar_copy_inicio()  # 📡 v12.9.0: 1ª ronda de seguimiento en ~90 s
    # v12.2: stake dinámico y tope diario persistidos
    set_stake_mode(_est0.get("stake_mode", "AUTO"))
    MAX_OPS_DIA = max_ops(_est0)
    PROB_MIN_AUTO = prob_min_auto(_est0)
    log(f"stake={STAKE_MODE} · max ops/día={MAX_OPS_DIA} · prob AUTO ≥{int(PROB_MIN_AUTO * 100)}% · PIN ops fijo (4 cifras)")
    restaurar_horario()
    programar_auditoria_inicial()   # v12.7: auto-curación al arrancar
    try:
        _ab, _nu, _es = sincronizar_operaciones()   # v11.5: cierra resueltas al arrancar
        if _nu:
            log(f"  sync inicial: {len(_nu)} op(s) cerradas ({sum(1 for o in _nu if o.get('resultado') == 'ganada')} ganadas)")
    except Exception as e:
        log(f"  sync inicial error: {e}")
    log(f"v12.9.0 cargado · modo={MODO_OPERACION} · stake={stake_txt()} · max {MAX_OPS_DIA}/día · prob ≥{int(PROB_MIN_AUTO * 100)}%")
    log(f"Proxy: {PROXY_URL}")
    status, body = http_get("https://api.telegram.org", timeout=10)
    log(f"Test proxy: {status if status else 'FALLO'}")
    t = threading.Thread(target=auto_loop, daemon=True)
    t.start()
    bot_loop()

if __name__ == "__main__":
    main()
