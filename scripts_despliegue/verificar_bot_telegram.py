#!/usr/bin/env python3
"""
VERIFICAR BOT DE TELEGRAM DE TRUMP
==================================
Comprueba que el token del bot de Trump es válido y obtiene
información del bot (nombre, ID, etc.)
"""
import os
import json
import subprocess
import urllib.request
import urllib.parse
import base64
from datetime import datetime

LOG = []
def log(s):
    s = str(s)
    print(s, flush=True)
    LOG.append(s)

def cargar_pat():
    for r in ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt")]:
        if os.path.exists(r):
            try:
                PAT = open(r).read().strip()
                if PAT.startswith("ghp_"):
                    return PAT
            except: pass
    return os.environ.get("GH_PAT", "")

PAT = cargar_pat()

def publicar(texto, ruta):
    if not PAT: return False, "Sin PAT"
    b64 = base64.b64encode(texto.encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}?ref=diag-public",
            headers={"Authorization": f"token {PAT}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except: pass
    payload = {"message": f"telegram {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": "diag-public"}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {PAT}", "Content-Type": "application/json",
                 "Accept": "application/vnd.github+json", "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return True, r.read().decode()
    except Exception as e:
        return False, str(e)

log("=" * 70)
log(f"VERIFICAR BOT TELEGRAM TRUMP · {datetime.now().isoformat()}")
log("=" * 70)
log("")

# 1) Ver el archivo de env y extraer el token de Trump
log("[1] Token TRUMP_BOT_TOKEN en /etc/polymarket.env:")
try:
    with open("/etc/polymarket.env") as f:
        for linea in f:
            if "TRUMP_BOT_TOKEN" in linea or "TELEGRAM_BOT_TOKEN" in linea or "TELEGRAM_CHAT_ID" in linea:
                log(f"  {linea.rstrip()}")
except Exception as e:
    log(f"  ERROR: {e}")

# 2) Probar el token con getMe
log("")
log("[2] Probando token con getMe...")
try:
    # Cargar token
    token = None
    with open("/etc/polymarket.env") as f:
        for linea in f:
            if "TRUMP_BOT_TOKEN=" in linea:
                token = linea.split("=", 1)[1].strip()
                break
    if not token:
        # fallback
        with open("/etc/polymarket.env") as f:
            for linea in f:
                if "TELEGRAM_BOT_TOKEN=" in linea:
                    token = linea.split("=", 1)[1].strip()
                    break
    if not token:
        log("  ✗ No se encontró TRUMP_BOT_TOKEN ni TELEGRAM_BOT_TOKEN en env")
    else:
        log(f"  token: {token[:10]}...{token[-4:]} (longitud: {len(token)})")
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
                if data.get("ok"):
                    bot = data["result"]
                    log(f"  ✓ Token VÁLIDO")
                    log(f"    id: {bot.get('id')}")
                    log(f"    username: @{bot.get('username')}")
                    log(f"    first_name: {bot.get('first_name')}")
                    log(f"    can_join_groups: {bot.get('can_join_groups')}")
                else:
                    log(f"  ✗ Token INVÁLIDO: {data}")
        except Exception as e:
            log(f"  ✗ Error: {e}")
except Exception as e:
    log(f"  ERROR: {e}")

# 3) Comparar con el de Zelenskyy (que SÍ funciona)
log("")
log("[3] Comparación con token de Zelenskyy (debería ser DIFERENTE):")
try:
    with open("/etc/polymarket.env") as f:
        zelen_token = None
        trump_token = None
        for linea in f:
            if "ZELEN_BOT_TOKEN=" in linea:
                zelen_token = linea.split("=", 1)[1].strip()
            if "TRUMP_BOT_TOKEN=" in linea:
                trump_token = linea.split("=", 1)[1].strip()
    if zelen_token and trump_token:
        if zelen_token == trump_token:
            log("  ✗ IGUALES — problema: Trump y Zelenskyy están usando el MISMO token")
        else:
            log(f"  ✓ DIFERENTES (correcto)")
            log(f"    Zelenskyy: {zelen_token[:10]}...{zelen_token[-4:]}")
            log(f"    Trump:     {trump_token[:10]}...{trump_token[-4:]}")
    else:
        log(f"  zelen: {'encontrado' if zelen_token else 'NO'}, trump: {'encontrado' if trump_token else 'NO'}")
except Exception as e:
    log(f"  ERROR: {e}")

# 4) Probar getUpdates para ver si hay mensajes pendientes
log("")
log("[4] getUpdates del bot de Trump (mensajes pendientes):")
try:
    with open("/etc/polymarket.env") as f:
        token = None
        for linea in f:
            if "TRUMP_BOT_TOKEN=" in linea:
                token = linea.split("=", 1)[1].strip()
                break
    if token:
        url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=5"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
                if data.get("ok"):
                    updates = data["result"]
                    log(f"  Updates pendientes: {len(updates)}")
                    for u in updates[-3:]:
                        log(f"    update_id: {u.get('update_id')}")
                        if "message" in u:
                            msg = u["message"]
                            log(f"      text: {msg.get('text', '')[:50]}")
                            log(f"      from: {msg.get('from', {}).get('username', '?')}")
                            log(f"      chat_id: {msg.get('chat', {}).get('id')}")
                else:
                    log(f"  ✗ Error: {data}")
        except Exception as e:
            log(f"  ✗ Error: {e}")
except Exception as e:
    log(f"  ERROR: {e}")

# 5) Ver la configuración del servicio poly-telegram-trump
log("")
log("[5] Contenido del servicio poly-telegram-trump.service:")
r = subprocess.run(["systemctl", "cat", "poly-telegram-trump", "--no-pager"],
                   capture_output=True, text=True, timeout=10)
if r.returncode == 0:
    for linea in r.stdout.split('\n')[:30]:
        if linea.strip() and not linea.strip().startswith('#'):
            log(f"  {linea}")
else:
    log(f"  ERROR: {r.stderr}")

# 6) Ver el proceso en ejecución
log("")
log("[6] Proceso python en ejecución:")
r = subprocess.run(["ps", "auxf"], capture_output=True, text=True, timeout=10)
for linea in r.stdout.split('\n'):
    if 'poly_telegram_trump' in linea and 'grep' not in linea:
        log(f"  {linea.strip()}")

# 7) Ver últimas líneas del log
log("")
log("[7] Últimas 30 líneas del log:")
r = subprocess.run(["journalctl", "-u", "poly-telegram-trump", "-n", "30", "--no-pager"],
                   capture_output=True, text=True, timeout=10)
if r.returncode == 0:
    for linea in r.stdout.split('\n')[-30:]:
        if linea.strip():
            log(f"  {linea}")

# Publicar
inf = ["=" * 78,
       f"VERIFICAR BOT TELEGRAM TRUMP - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
       "=" * 78, ""]
inf.extend(LOG)
inf.append("=" * 78)
texto = "\n".join(inf)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ok, info = publicar(texto, f"diag_hetzner/telegram_{ts}.txt")
if ok:
    log(f"\n✓ Publicado")
else:
    log(f"\n✗ Error: {info}")
