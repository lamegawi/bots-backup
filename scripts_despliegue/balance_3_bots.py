#!/usr/bin/env python3
"""
BALANCE DE LOS 3 BOTS CON TELEGRAM
==================================
Lee el estado real de cada bot y publica un balance completo
para estudiar motores o cambios.
"""
import os
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
    payload = {"message": f"balance {datetime.now().strftime('%H%M%S')}",
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

def leer_estado(ruta):
    """Lee el estado de un bot. Devuelve dict con la info clave."""
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta) as f:
            d = json.load(f)
        saldo = d.get("saldo", 0)
        paso = d.get("paso", 0)
        activa = d.get("activa")
        historial = d.get("historial", [])
        # Calcular stats
        n_ops = len(historial)
        g_count = sum(1 for op in historial if op.get("resultado") == "G")
        p_count = sum(1 for op in historial if op.get("resultado") == "P")
        otro = n_ops - g_count - p_count
        # Sumar beneficios
        total_beneficio = sum(float(op.get("beneficio", 0) or 0) for op in historial)
        # Beneficio real (campo "real" suele tener el dato verdadero)
        beneficio_real_total = 0
        for op in historial:
            real = op.get("real", "")
            # Si dice "vendido por el gestor en positivo (+X.XX...)", extraer X.XX
            if "+" in str(real):
                import re
                m = re.search(r'\(\+?([\d.]+)', str(real))
                if m:
                    beneficio_real_total += float(m.group(1))
        return {
            "saldo": saldo,
            "paso": paso,
            "activa": activa,
            "n_ops": n_ops,
            "ganadas": g_count,
            "perdidas": p_count,
            "otro": otro,
            "win_rate": (g_count / n_ops * 100) if n_ops > 0 else 0,
            "total_beneficio": total_beneficio,
            "beneficio_real_total": beneficio_real_total,
        }
    except Exception as e:
        return {"error": str(e)}

log("=" * 70)
log(f"BALANCE 3 BOTS · {datetime.now().isoformat()}")
log("=" * 70)
log("")

# 1) Bot de Elon
log("[1] Bot de Elon (48h):")
estado_elon = leer_estado("/opt/polymarket/bot-polymarket-elon/real.json")
if estado_elon:
    log(f"  saldo: ${estado_elon.get('saldo', '?')}")
    log(f"  paso: {estado_elon.get('paso', '?')}")
    log(f"  ops: {estado_elon.get('n_ops', 0)} (G:{estado_elon.get('ganadas', 0)} / P:{estado_elon.get('perdidas', 0)} / ?:{estado_elon.get('otro', 0)})")
    log(f"  win rate: {estado_elon.get('win_rate', 0):.1f}%")
    log(f"  beneficio (virtual): ${estado_elon.get('total_beneficio', 0):+.2f}")
    log(f"  beneficio (real): ${estado_elon.get('beneficio_real_total', 0):+.2f}")
    log(f"  activa: {bool(estado_elon.get('activa'))}")
else:
    log("  no encontrado")
    estado_elon = {}

log("")
log("[2] Bot de Zelenskyy (semanal):")
estado_zelen = leer_estado("/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json")
if estado_zelen:
    log(f"  saldo: ${estado_zelen.get('saldo', '?')}")
    log(f"  paso: {estado_zelen.get('paso', '?')}")
    log(f"  ops: {estado_zelen.get('n_ops', 0)} (G:{estado_zelen.get('ganadas', 0)} / P:{estado_zelen.get('perdidas', 0)} / ?:{estado_zelen.get('otro', 0)})")
    log(f"  win rate: {estado_zelen.get('win_rate', 0):.1f}%")
    log(f"  beneficio (virtual): ${estado_zelen.get('total_beneficio', 0):+.2f}")
    log(f"  beneficio (real): ${estado_zelen.get('beneficio_real_total', 0):+.2f}")
    log(f"  activa: {bool(estado_zelen.get('activa'))}")
else:
    log("  no encontrado")
    estado_zelen = {}

log("")
log("[3] Bot de Trump (semanal):")
estado_trump = leer_estado("/opt/polymarket/bot-polymarket-trump/real_trump.json")
if estado_trump:
    log(f"  saldo: ${estado_trump.get('saldo', '?')}")
    log(f"  paso: {estado_trump.get('paso', '?')}")
    log(f"  ops: {estado_trump.get('n_ops', 0)} (G:{estado_trump.get('ganadas', 0)} / P:{estado_trump.get('perdidas', 0)} / ?:{estado_trump.get('otro', 0)})")
    log(f"  win rate: {estado_trump.get('win_rate', 0):.1f}%")
    log(f"  beneficio (virtual): ${estado_trump.get('total_beneficio', 0):+.2f}")
    log(f"  beneficio (real): ${estado_trump.get('beneficio_real_total', 0):+.2f}")
    log(f"  activa: {bool(estado_trump.get('activa'))}")
else:
    log("  no encontrado (puede no haber operado todavía)")
    estado_trump = {}

log("")
log("[4] RESUMEN COMPARATIVO:")
log(f"  {'Bot':<20} {'Saldo':<10} {'Ops':<5} {'WinRate':<10} {'Virtual':<12} {'Real'}")
log(f"  {'-'*20} {'-'*10} {'-'*5} {'-'*10} {'-'*12} {'-'*10}")
for nombre, est in [("Elon 48h", estado_elon), ("Zelenskyy sem", estado_zelen), ("Trump sem", estado_trump)]:
    if est and "error" not in est:
        log(f"  {nombre:<20} ${est.get('saldo', 0):<9.2f} {est.get('n_ops', 0):<5} {est.get('win_rate', 0):<9.1f}% ${est.get('total_beneficio', 0):<+11.2f} ${est.get('beneficio_real_total', 0):+9.2f}")
    else:
        log(f"  {nombre:<20} {'(no data)':<10}")

# Publicar
inf = ["=" * 78,
       f"BALANCE 3 BOTS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
       "=" * 78, ""]
inf.extend(LOG)
inf.append("=" * 78)
texto = "\n".join(inf)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ok, info = publicar(texto, f"diag_hetzner/balance_{ts}.txt")
if ok:
    log(f"\n✓ Publicado")
else:
    log(f"\n✗ Error: {info}")
