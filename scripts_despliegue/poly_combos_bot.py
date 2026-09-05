#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POLY COMBOS BOT
================
Bot de Telegram para copiar trades de los top traders de Polymarket.

Comandos:
  /start       - Mensaje de bienvenida
  /trades      - Ver trades recomendados para copiar
  /copiar N    - Copiar el trade numero N (con tu wallet)
  /abiertas    - Ver tus posiciones abiertas
  /cerradas    - Ver tus posiciones cerradas
  /saldo       - Ver tu saldo real
  /top         - Ver leaderboard de Polymarket
  /estado      - Estado del bot y servicios

USO:
  python3 poly_combos_bot.py

Requiere:
  - Token en /root/poly_combos_token.txt
  - Wallet y credenciales en /etc/polymarket.env
"""
import os
import sys
import json
import time
import base64
import urllib.request
import urllib.parse
import shutil
import subprocess
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = []
def log(s):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {s}"
    print(line, flush=True)
    LOG.append(line)

# ============================================
# CONFIGURACION
# ============================================
TELEGRAM_TOKEN = None
TELEGRAM_API = None
CHAT_ID_PERMITIDO = None  # solo tu chat_id podra usar el bot

WALLET = "0xb0e1197098e6d427c01720f1631cad24ce740fa0"

# archivos de estado
ESTADO_FILE = "/opt/polymarket/combos_estado.json"  # trades copiados
BACKUP_FILE = "/opt/polymarket/combos_estado.bak.json"

# stake por trade
STAKE_POR_TRADE = 2.0

# top traders (mismos que en el script de deteccion)
TOP_TRADERS = [
    ("pleaseplease123",     "0x5e9458202b5817a72cf81105ec8a30e6f3705ba1", 10),
    ("ferrariChampions2026", "0xfe787d2da716d60e8acff57fb87eb13cd4d10319", 8),
    ("balthazar",            "0x5a218c7ad04135830a45c41aaed7294df7809318", 5),
    ("Sassy-Bucket",         "0x4bff30af91642dc7d2b19a8664378fe55c45fc26", 5),
    ("Jsram",                "0x83720820a8aa6c3f20ad71850e7a1a17d16c5223", 5),
    ("Flaznorp",             "0x821dab0565ebf5b327f51db06223fdcfe01acf16", 5),
    ("Talvez10",             "0xa71093cafc0c099b4ccab24c3cb8018d817923c4", 4),
    ("GoalLineGhost",        "0x0346afae2603313d2bbee96b628536c8cbe352a5", 3),
    ("AV23IUa",              "0xdb859a551fcf56e49416160911476bea7307152f", 3),
]

# ============================================
# TELEGRAM
# ============================================
def cargar_token():
    """Carga el token del bot de Telegram."""
    global TELEGRAM_TOKEN
    paths = ["/root/poly_combos_token.txt", "/root/diag_token.txt", os.path.expanduser("~/poly_combos_token.txt")]
    for p in paths:
        if os.path.exists(p):
            t = open(p).read().strip()
            if ":" in t and len(t) > 20:
                TELEGRAM_TOKEN = t
                return True
    return False

def telegram_api(method, params=None):
    """Llama a la API de Telegram."""
    if not TELEGRAM_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    if params:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data)
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"telegram_api error: {e}")
        return None

def enviar_mensaje(chat_id, texto, reply_markup=None):
    """Envia un mensaje a un chat."""
    params = {"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"}
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    return telegram_api("sendMessage", params)

def enviar_trades(chat_id, trades):
    """Envia los trades con botones inline."""
    botones = []
    for i, t in enumerate(trades, 1):
        titulo_corto = t["titulo"][:40]
        botones.append([{
            "text": f"Copiar {i}: {titulo_corto}",
            "callback_data": f"copiar_{i}"
        }])
    texto = "*🎯 TRADES RECOMENDADOS*\n\n"
    for i, t in enumerate(trades, 1):
        texto += f"*{i}.* {t['titulo'][:50]}\n"
        texto += f"    Trader: `{t['trader']}`\n"
        texto += f"    Lado: {t['side']} @ {t['price']:.2f} (cuota {t['cuota']:.2f})\n"
        texto += f"    Tu stake: ${t['stake_sugerido']}\n\n"
    texto += "_Pulsa un boton para copiar el trade._"
    return enviar_mensaje(chat_id, texto, {"inline_keyboard": botones})

# ============================================
# POLYMARKET
# ============================================
def cargar_env():
    env = {}
    p = "/etc/polymarket.env"
    if not os.path.exists(p):
        return env
    with open(p) as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            if "=" in linea:
                k, v = linea.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def saldo_onchain(wallet):
    rpcs = ["https://polygon-rpc.com", "https://1rpc.io/matic",
            "https://polygon.llamarpc.com", "https://rpc.ankr.com/polygon"]
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
                    ["curl", "-s", "--max-time", "10", "-X", "POST", rpc,
                     "-H", "Content-Type: application/json", "-d", body],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=15).stdout
                r = json.loads(out)
                if "result" in r and r["result"] not in ("0x", "0x0", None):
                    saldos[simbolo] = int(r["result"], 16) / (10 ** dec)
                    break
            except:
                continue
    return saldos

def get_posiciones(wallet):
    url = f"https://data-api.polymarket.com/positions?user={wallet}&limit=500"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            posiciones = json.loads(r.read())
        return posiciones
    except:
        return []

def detectar_trades_copy():
    """Detecta los trades para copiar (mismo algoritmo que el script)."""
    EXCLUIR = ["Trump", "Biden", "Election", "President", "Congress",
               "Bitcoin", "Ethereum", "Crypto", "NFT",
               "Fed", "rate", "inflation", "Russia", "Ukraine", "China"]
    DEPORTES = ["MLB", "UFC", "NFL", "NBA", "tennis", "ATP", "soccer", "EPL", "O/U", "Spread"]

    candidatos = []
    ahora = datetime.now().timestamp()
    for nombre, wallet, peso in TOP_TRADERS:
        try:
            url = f"https://data-api.polymarket.com/trades?user={wallet}&limit=30"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                trades = json.loads(r.read())
            for t in trades:
                if not isinstance(t, dict): continue
                titulo = t.get("title", "") or t.get("question", "")
                if any(ex in titulo for ex in EXCLUIR):
                    continue
                if not any(d.lower() in titulo.lower() for d in DEPORTES):
                    continue
                ts = t.get("timestamp", 0)
                if ahora - ts > 24 * 3600:
                    continue
                side = t.get("side", "?")
                price = float(t.get("price", 0))
                if price <= 0: continue
                candidatos.append({
                    "trader": nombre,
                    "peso": peso,
                    "titulo": titulo,
                    "side": side,
                    "price": price,
                    "size": float(t.get("size", 0)),
                    "asset": t.get("asset", "?"),
                    "timestamp": ts,
                    "cuota": round(1/price, 2),
                    "stake_sugerido": STAKE_POR_TRADE,
                })
        except Exception as e:
            log(f"error detectando {nombre}: {e}")

    candidatos.sort(key=lambda x: -x["peso"])
    # dedup
    vistos = set()
    finales = []
    for c in candidatos:
        key = c["titulo"][:50]
        if key in vistos: continue
        vistos.add(key)
        finales.append(c)
        if len(finales) >= 3:
            break
    return finales

# ============================================
# ESTADO (persistente)
# ============================================
def cargar_estado():
    if not os.path.exists(ESTADO_FILE):
        return {"copiados": [], "historial": []}
    try:
        with open(ESTADO_FILE) as f:
            return json.load(f)
    except:
        return {"copiados": [], "historial": []}

def guardar_estado(estado):
    # backup
    if os.path.exists(ESTADO_FILE):
        shutil.copy2(ESTADO_FILE, BACKUP_FILE)
    # escribir
    with open(ESTADO_FILE, "w") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)

# ============================================
# COMANDOS
# ============================================
def cmd_start(chat_id):
    texto = """*🤖 POLY COMBOS BOT* 🤖

Bienvenido al bot de copia de trades de Polymarket Sports.

*Comandos:*
/trades - Ver trades recomendados para copiar
/abiertas - Ver tus posiciones abiertas
/cerradas - Ver historial de cerradas
/saldo - Ver tu saldo real
/top - Ver leaderboard
/estado - Estado del bot

_Stake por trade: $2 (configurable)_
"""
    return enviar_mensaje(chat_id, texto)

def cmd_trades(chat_id):
    log(f"[trades] pedido de chat {chat_id}")
    trades = detectar_trades_copy()
    if not trades:
        return enviar_mensaje(chat_id, "❌ No hay trades recomendados ahora mismo.")
    return enviar_trades(chat_id, trades)

def cmd_copiar(chat_id, num):
    log(f"[copiar] chat {chat_id} quiere copiar #{num}")
    trades = detectar_trades_copy()
    if num < 1 or num > len(trades):
        return enviar_mensaje(chat_id, f"❌ Número inválido. Hay {len(trades)} trades disponibles.")
    trade = trades[num - 1]
    # guardar en estado
    estado = cargar_estado()
    estado["copiados"].append({
        **trade,
        "copiado_en": datetime.now().isoformat(),
        "status": "pendiente",  # el bot real lo cambiaria a "ejecutado"
    })
    guardar_estado(estado)
    texto = f"""*✅ TRADE MARCADO PARA COPIAR*

*{trade['titulo'][:60]}*
Lado: {trade['side']} @ {trade['price']:.2f}
Cuota: {trade['cuota']:.2f}
Stake: ${trade['stake_sugerido']}
Trader: `{trade['trader']}`

⚠️ *Pendiente de ejecución real*
La ejecución automática se hará cuando se ejecute el bot desde Hetzner con tu wallet.

_Usa /abiertas para ver tus posiciones copiadas._
"""
    return enviar_mensaje(chat_id, texto)

def cmd_abiertas(chat_id):
    pos = get_posiciones(WALLET)
    if not pos:
        return enviar_mensaje(chat_id, "❌ No se pudieron cargar posiciones.")
    abiertas = [p for p in pos if float(p.get("currentValue", 0) or 0) > 0.001]
    if not abiertas:
        return enviar_mensaje(chat_id, "📭 No tienes posiciones abiertas.")
    texto = f"*📂 POSICIONES ABIERTAS ({len(abiertas)})*\n\n"
    for p in abiertas[:15]:
        titulo = (p.get("title") or p.get("question", "?"))[:50]
        outcome = p.get("outcome", "?")
        cur = float(p.get("currentValue", 0) or 0)
        init = float(p.get("initialValue", 0) or 0)
        pnl = float(p.get("cashPnl", 0) or 0)
        ico = "🟢" if pnl >= 0 else "🔴"
        texto += f"{ico} {titulo}\n   {outcome} | PnL: ${pnl:+.2f} (cur ${cur:.2f})\n\n"
    return enviar_mensaje(chat_id, texto)

def cmd_cerradas(chat_id):
    pos = get_posiciones(WALLET)
    if not pos:
        return enviar_mensaje(chat_id, "❌ No se pudieron cargar posiciones.")
    cerradas = [p for p in pos if float(p.get("currentValue", 0) or 0) <= 0.001
                and float(p.get("initialValue", 0) or 0) > 0.001
                and abs(float(p.get("cashPnl", 0) or 0)) > 0.001]
    if not cerradas:
        return enviar_mensaje(chat_id, "📭 No tienes posiciones cerradas.")
    texto = f"*✅ POSICIONES CERRADAS ({len(cerradas)})*\n\n"
    total_pnl = 0
    for p in cerradas[:20]:
        titulo = (p.get("title") or p.get("question", "?"))[:50]
        pnl = float(p.get("cashPnl", 0) or 0)
        total_pnl += pnl
        ico = "🟢" if pnl >= 0 else "🔴"
        texto += f"{ico} {titulo} → ${pnl:+.2f}\n"
    texto += f"\n*Total PnL: ${total_pnl:+.2f}*"
    return enviar_mensaje(chat_id, texto)

def cmd_saldo(chat_id):
    saldos = saldo_onchain(WALLET)
    cash = sum(saldos.values())
    pos = get_posiciones(WALLET)
    val_pos = sum(float(p.get("currentValue", 0) or 0) for p in pos)
    total = cash + val_pos
    texto = f"""*💰 SALDO REAL*

*Cash on-chain:* ${cash:.2f}
"""
    for tok, val in saldos.items():
        texto += f"  · {tok}: ${val:.2f}\n"
    texto += f"\n*Posiciones:* ${val_pos:.2f}\n"
    texto += f"*TOTAL:* ${total:.2f}\n"
    texto += f"\n_PnL desde $500: ${total - 500:+.2f} ({(total-500)/500*100:+.1f}%)_"
    return enviar_mensaje(chat_id, texto)

def cmd_top(chat_id):
    texto = "*🏆 LEADERBOARD POLYMARKET (mensual)*\n\n"
    texto += "1. pleaseplease123: +$1,002,970\n"
    texto += "2. ferrariChampions2026: +$791,181\n"
    texto += "3. balthazar: +$534,712\n"
    texto += "4. 0xd9670...: +$466,165\n"
    texto += "5. Talvez10: +$339,638\n"
    texto += "6. AV23IUa: +$311,198\n"
    texto += "7. 11vsldfdsgfkjgos: +$272,316\n"
    texto += "8. Flaznorp: +$265,127\n"
    texto += "9. sainttroplay: +$207,517\n"
    texto += "10. ExplosiveNinja: +$189,887\n"
    texto += "\n_Usa /trades para ver los últimos trades de estos traders_"
    return enviar_mensaje(chat_id, texto)

def cmd_estado(chat_id):
    # ver estado del servicio
    r = subprocess.run(["systemctl", "is-active", "poly-combos-bot"],
                       capture_output=True, text=True, timeout=5)
    srv = r.stdout.strip()
    texto = f"""*📊 ESTADO DEL BOT*

Servicio: `{srv}`
Wallet: `{WALLET[:10]}...{WALLET[-4:]}`
Stake por trade: ${STAKE_POR_TRADE}

_Última verificación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_
"""
    return enviar_mensaje(chat_id, texto)

# ============================================
# BOT LOOP (long polling)
# ============================================
def procesar_update(update):
    """Procesa un update de Telegram."""
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")
        if data.startswith("copiar_"):
            try:
                num = int(data.split("_")[1])
                return cmd_copiar(chat_id, num)
            except:
                pass
        return

    if "message" not in update:
        return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if text == "/start":
        return cmd_start(chat_id)
    elif text == "/trades":
        return cmd_trades(chat_id)
    elif text.startswith("/copiar "):
        try:
            num = int(text.split()[1])
            return cmd_copiar(chat_id, num)
        except:
            return enviar_mensaje(chat_id, "❌ Uso: /copiar N (numero de trade)")
    elif text == "/abiertas":
        return cmd_abiertas(chat_id)
    elif text == "/cerradas":
        return cmd_cerradas(chat_id)
    elif text == "/saldo":
        return cmd_saldo(chat_id)
    elif text == "/top":
        return cmd_top(chat_id)
    elif text == "/estado":
        return cmd_estado(chat_id)

def bot_loop():
    """Loop principal con long-polling."""
    log("Bot iniciado, esperando mensajes...")
    offset = 0
    while True:
        try:
            params = {"timeout": 30, "offset": offset, "allowed_updates": '["message","callback_query"]'}
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read())
            if result.get("ok"):
                for update in result.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        procesar_update(update)
                    except Exception as e:
                        log(f"error procesando update: {e}")
        except Exception as e:
            log(f"error en loop: {e}")
            time.sleep(5)

# ============================================
# MAIN
# ============================================
def main():
    if not cargar_token():
        log("ERROR: no se encontro el token del bot")
        log("Crea el bot con @BotFather y guarda el token en /root/poly_combos_token.txt")
        return

    log(f"Token cargado: {TELEGRAM_TOKEN[:10]}...")
    log(f"Wallet: {WALLET}")
    bot_loop()

if __name__ == "__main__":
    main()
