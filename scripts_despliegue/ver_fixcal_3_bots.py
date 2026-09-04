#!/usr/bin/env python3
"""
VER FIXCAL DE LOS 3 BOTS
=========================
Lee el código fuente de cada bot y extrae la lógica de FIXCAL:
- Win rate mínimo
- Cuota máxima
- Stake base
- Factor de escalamiento
- EV mínimo
- Kelly
- Etc.
"""
import os
import re
import json
import base64
import urllib.request
import urllib.error
from datetime import datetime

LOG = []
def log(s):
    s = str(s)
    print(s, flush=True)
    LOG.append(s)

def cargar_pat():
    for r in ["/root/diag_token.txt", "/opt/polymarket/diag_token.txt",
              os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            try:
                t = open(r).read().strip()
                if t.startswith("ghp_") or t.startswith("github_pat_"):
                    return t
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
    payload = {"message": f"fixcal {datetime.now().strftime('%H%M%S')}",
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

def leer_config(bot_dir):
    """Lee config.json y config_real.json si existen."""
    configs = {}
    for nombre in ["config.json", "config_real.json"]:
        fp = os.path.join(bot_dir, nombre)
        if os.path.exists(fp):
            try:
                with open(fp) as f:
                    configs[nombre] = json.load(f)
            except: pass
    return configs

def buscar_fixcal(archivos):
    """Busca patrones FIXCAL en los archivos de un bot.
    Devuelve todas las líneas que mencionan FIXCAL, kelly, stake, cuota, etc."""
    out = []
    for fp in archivos:
        if not os.path.exists(fp):
            continue
        try:
            with open(fp) as f:
                contenido = f.read()
            for num, linea in enumerate(contenido.split('\n'), 1):
                L = linea.strip()
                # Patrones de interés
                if re.search(r'\b(FIXCAL|fixcal|kelly|stake|cuota|min_win|win_rate|ev_min|escalon|step|factor|p_modelo|cuota_med|apuesta|bankroll)\b', L, re.IGNORECASE):
                    if L and not L.startswith('#') and not L.startswith('//'):
                        out.append((fp, num, L))
        except Exception as e:
            out.append((fp, 0, f"ERROR: {e}"))
    return out

log("=" * 70)
log(f"FIXCAL 3 BOTS · {datetime.now().isoformat()}")
log("=" * 70)
log("")

bots = [
    ("Elon 48h", "/opt/polymarket/bot-polymarket-elon", [
        "bot.py", "papel.py", "operar_real.py", "senal.py", "senal_vivo.py",
    ]),
    ("Zelenskyy", "/opt/polymarket/bot-polymarket-zelenskyy", [
        "bot_semanal.py", "papel_semanal.py", "operar_real_semanal.py",
        "senal.py", "senal_vivo.py",
    ]),
    ("Trump", "/opt/polymarket/bot-polymarket-trump", [
        "bot_semanal.py", "papel_semanal.py", "operar_real_semanal.py",
        "senal.py", "senal_vivo.py",
    ]),
]

# 1) Configs
log("[1] CONFIGS DE CADA BOT:")
for nombre, d, _ in bots:
    log(f"\n--- {nombre} ---")
    configs = leer_config(d)
    for fname, cfg in configs.items():
        log(f"  {fname}:")
        for k, v in sorted(cfg.items()):
            if isinstance(v, (str, int, float, bool, type(None))):
                if "key" in k.lower() or "secret" in k.lower() or "token" in k.lower() or "pass" in k.lower():
                    log(f"    {k}: ***")
                else:
                    log(f"    {k}: {v}")
            elif isinstance(v, dict):
                log(f"    {k}: {json.dumps(v, indent=6)[:200]}")

log("")
log("=" * 70)
log("[2] LÓGICA FIXCAL (líneas relevantes):")
log("=" * 70)

for nombre, d, archivos in bots:
    log(f"\n=== {nombre} ===")
    paths = [os.path.join(d, a) for a in archivos]
    matches = buscar_fixcal(paths)
    # Filtrar para no mostrar líneas demasiado largas o deprecadas
    relevantes = []
    for fp, num, L in matches:
        if len(L) > 200:
            continue
        # Filtrar solo las que parecen tener valores numéricos o de config
        if re.search(r'[=<>]|if|return|kelly|stake|cuota|min_', L, re.IGNORECASE):
            relevantes.append((fp, num, L))
    for fp, num, L in relevantes[:50]:
        nombre_fp = os.path.basename(fp)
        log(f"  {nombre_fp}:{num}  {L[:160]}")

log("")
log("=" * 70)
log("[3] TABLAS DE STAKE (si existen):")
log("=" * 70)
for nombre, d, _ in bots:
    for fname in ["papel.py", "papel_semanal.py", "bot.py", "bot_semanal.py"]:
        fp = os.path.join(d, fname)
        if not os.path.exists(fp):
            continue
        with open(fp) as f:
            contenido = f.read()
        # Buscar tablas tipo "stake = [3.3, 5, 7.5, 11.25, ...]"
        m = re.search(r'stake\s*=\s*\[([\d.,\s]+)\]', contenido)
        if m:
            log(f"  {nombre} ({fname}): stake = [{m.group(1)}]")
        m = re.search(r'tabla\s*=\s*\[([\d.,\s]+)\]', contenido)
        if m:
            log(f"  {nombre} ({fname}): tabla = [{m.group(1)}]")

# Publicar
inf = ["=" * 78,
       f"FIXCAL 3 BOTS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
       "=" * 78, ""]
inf.extend(LOG)
inf.append("=" * 78)
texto = "\n".join(inf)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ok, info = publicar(texto, f"diag_hetzner/fixcal_{ts}.txt")
if ok:
    log(f"\n✓ Publicado: https://github.com/lamegawi/bots-backup/blob/diag-public/diag_hetzner/fixcal_{ts}.txt")
else:
    log(f"\n✗ Error: {info}")
