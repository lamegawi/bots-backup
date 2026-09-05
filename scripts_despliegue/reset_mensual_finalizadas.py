#!/usr/bin/env python3
"""
RESET MENSUAL · historico de finalizadas en el bot de Telegram
================================================================
Cambia el archivo /opt/polymarket/posiciones_reales.py para que la constante
FECHA_INICIO sea el primer dia del mes actual (en lugar de una fecha fija).

De esta forma, el bot de Telegram solo muestra las finalizadas del mes
en curso, y se reinicia automaticamente cada mes.

USO:
  python3 reset_mensual_finalizadas.py             # aplica (hace backup)
  python3 reset_mensual_finalizadas.py --dry       # muestra que haria
  python3 reset_mensual_finalizadas.py --revertir  # vuelve a la fecha fija

Se puede poner en cron el dia 1 de cada mes a las 00:01.
"""
import os
import sys
import shutil
import argparse
import base64
import urllib.request
import json
import re
from datetime import datetime

ARCHIVO = "/opt/polymarket/posiciones_reales.py"
LOG = []
def log(s):
    line = str(s)
    print(line, flush=True)
    LOG.append(line)

def find_pat():
    for r in ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            t = open(r).read().strip()
            if t.startswith("ghp_"): return t
    return os.environ.get("GH_PAT", "")

def publicar(texto, ruta, pat):
    if not pat: return False
    b64 = base64.b64encode(texto.encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}?ref=diag-public",
            headers={"Authorization": f"token {pat}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except: pass
    payload = {"message": f"reset {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": "diag-public"}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {pat}", "Content-Type": "application/json",
                 "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return True
    except: return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--revertir", action="store_true")
    args = ap.parse_args()

    log("=" * 70)
    log(f"RESET MENSUAL FINALIZADAS · {datetime.now().isoformat()}")
    log("=" * 70)

    if not os.path.exists(ARCHIVO):
        log(f"ERROR: no existe {ARCHIVO}")
        sys.exit(1)

    with open(ARCHIVO) as f:
        contenido = f.read()

    # calcular primer dia del mes actual
    hoy = datetime.now()
    primer_dia = hoy.replace(day=1).date()
    nueva_fecha = f"datetime({primer_dia.year}, {primer_dia.month}, {primer_dia.day}).date()"
    log(f"  Hoy: {hoy.date()}")
    log(f"  Primer dia del mes: {primer_dia}")
    log(f"  Nueva FECHA_INICIO: {nueva_fecha}")

    # patron actual
    patron = r"FECHA_INICIO\s*=\s*datetime\(\d{4},\s*\d{1,2},\s*\d{1,2}\)\.date\(\)"
    match = re.search(patron, contenido)
    if not match:
        log("  No encontre FECHA_INICIO en el archivo")
        sys.exit(1)
    log(f"  FECHA_INICIO actual: {match.group()}")

    if args.revertir:
        # volver a la fecha fija 2026-08-17
        nueva = "FECHA_INICIO = datetime(2026, 8, 17).date()  # fecha fija"
        log(f"  Revirtiendo a: {nueva}")
    else:
        nueva = f"FECHA_INICIO = {nueva_fecha}  # primer dia del mes actual"
        log(f"  Cambiando a: {nueva}")

    contenido_nuevo = re.sub(patron, nueva, contenido)

    # tambien cambiar el texto "(desde 17/08/2026)" si existe
    contenido_nuevo = re.sub(
        r"\(desde 17/08/2026\)",
        f"(desde {primer_dia.strftime('%d/%m/%Y')})",
        contenido_nuevo
    )
    contenido_nuevo = re.sub(
        r"desde el 17/08 todav[ií]a\.",
        f"desde el {primer_dia.strftime('%d/%m')}",
        contenido_nuevo
    )
    contenido_nuevo = re.sub(
        r"Cuenta desde el cierre positivo del 15-17/08\.",
        f"Cuenta desde el {primer_dia.strftime('%d/%m/%Y')} (reset mensual).",
        contenido_nuevo
    )

    if contenido == contenido_nuevo:
        log("  No hay cambios que aplicar")
        return

    log("")
    log("Cambios:")
    diffs = 0
    for i, (a, b) in enumerate(zip(contenido.split("\n"), contenido_nuevo.split("\n"))):
        if a != b:
            log(f"  - {a}")
            log(f"  + {b}")
            diffs += 1
    if diffs == 0:
        log("  (solo cambios en lineas nuevas o eliminadas)")

    if args.dry:
        log("")
        log("=" * 70)
        log("MODO DRY-RUN: no se ha tocado nada")
        log(f"Para aplicar: {sys.argv[0]}")
        # publicar el dry-run para que se pueda leer
        pat = find_pat()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        texto = f"Reset DRY-RUN - {ts}\n" + "\n".join(LOG)
        ok = publicar(texto, f"diag_hetzner/reset_dry_{ts}.txt", pat)
        log(f"  publicado dry-run: {ok}")
        return

    # backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{ARCHIVO}.bak.{ts}"
    shutil.copy2(ARCHIVO, backup)
    log(f"  Backup: {backup}")

    # escribir
    with open(ARCHIVO, "w") as f:
        f.write(contenido_nuevo)
    log(f"  Escrito: {ARCHIVO}")

    log("")
    log("=" * 70)
    log("OK: FECHA_INICIO actualizado. El bot mostrara solo finalizadas del mes.")
    log("IMPORTANTE: reiniciar el bot de Telegram para que recargue el modulo:")
    log("  systemctl restart poly-telegram-bot")
    log("=" * 70)

    # publicar
    pat = find_pat()
    texto = f"Reset mensual - {ts}\n" + "\n".join(LOG)
    publicar(texto, f"diag_hetzner/reset_{ts}.txt", pat)
    log("  publicado: True")

if __name__ == "__main__":
    main()
