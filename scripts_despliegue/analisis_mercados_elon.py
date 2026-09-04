#!/usr/bin/env python3
"""
ANÁLISIS DE MERCADOS DE ELON
=============================
Revisa TODAS las operaciones de Elon (activas e históricas) y dice:
- En qué cuotas ha apostado
- Con qué p_modelo
- Qué mercados ha elegido
- Por qué falla
"""
import os
import json
import re
import base64
import urllib.request
import urllib.error
from datetime import datetime
from collections import Counter, defaultdict

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
    payload = {"message": f"merca {datetime.now().strftime('%H%M%S')}",
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
log(f"ANÁLISIS MERCADOS ELON · {datetime.now().isoformat()}")
log("=" * 70)
log("")

# 1) Leer real.json de Elon
fp = "/opt/polymarket/bot-polymarket-elon/real.json"
log(f"[1] Leyendo {fp}:")
if not os.path.exists(fp):
    log("  NO EXISTE")
else:
    with open(fp) as f:
        data = json.load(f)
    activa = data.get("activa")
    historial = data.get("historial", [])
    log(f"  activa: {bool(activa)}")
    if activa:
        log(f"    slug: {activa.get('slug', '?')}")
        log(f"    bin: {activa.get('bin_titulo', '?')}")
        log(f"    lado: {activa.get('lado', '?')}")
        log(f"    precio: {activa.get('precio', 0)}")
        log(f"    cuota: {activa.get('cuota', 0):.2f}")
        log(f"    p_modelo: {activa.get('p_modelo', 0):.0%}")
        log(f"    paso: {activa.get('paso', 0)}")
        log(f"    stake: ${activa.get('stake', 0):.2f}")
        log(f"    ev: {activa.get('ev', 0):.2f}")
        log(f"    motor: {activa.get('motor', '?')}")
    log(f"  historial: {len(historial)} ops")

log("")

# 2) Análisis del HISTORIAL de Elon
log("[2] ANÁLISIS DEL HISTORIAL:")
log("")
log("  Cuotas en las que ha apostado:")
cuotas = []
p_modelos = []
stakes = []
pasos = []
resultados = []
bins_por_op = []
for op in historial:
    try:
        c = float(op.get("cuota", 0) or 0)
        p = float(op.get("p_modelo", 0) or 0)
        s = float(op.get("stake", 0) or 0)
        paso = op.get("paso", 0)
        resultado = op.get("resultado", "?")
        bin_t = op.get("bin", "?")
        fecha = op.get("fecha", "?")
        cuotas.append(c)
        p_modelos.append(p)
        stakes.append(s)
        pasos.append(paso)
        resultados.append(resultado)
        bins_por_op.append((fecha, bin_t, c, p, s, paso, resultado))
    except: pass

if cuotas:
    log(f"    min: {min(cuotas):.2f}, max: {max(cuotas):.2f}, media: {sum(cuotas)/len(cuotas):.2f}")
    log(f"    Cuotas >10 (improbables): {sum(1 for c in cuotas if c > 10)} de {len(cuotas)}")
    log(f"    Cuotas >20: {sum(1 for c in cuotas if c > 20)}")
    log(f"    Cuotas >50: {sum(1 for c in cuotas if c > 50)}")
    log(f"    Cuotas >100: {sum(1 for c in cuotas if c > 100)}")
log("")
log("  p_modelo (probabilidad estimada):")
if p_modelos:
    log(f"    min: {min(p_modelos):.0%}, max: {max(p_modelos):.0%}, media: {sum(p_modelos)/len(p_modelos):.0%}")
log("")
log("  Stakes:")
if stakes:
    log(f"    min: ${min(stakes):.2f}, max: ${max(stakes):.2f}")
log("")
log("  Resultado por cuota:")
res_por_cuota = defaultdict(lambda: {"G": 0, "P": 0})
for c, r in zip(cuotas, resultados):
    if r in ("G", "P"):
        if c < 5: res_por_cuota["<5"][r] += 1
        elif c < 10: res_por_cuota["5-10"][r] += 1
        elif c < 20: res_por_cuota["10-20"][r] += 1
        elif c < 50: res_por_cuota["20-50"][r] += 1
        else: res_por_cuota[">50"][r] += 1
for rango, d in sorted(res_por_cuota.items()):
    total = d["G"] + d["P"]
    wr = (d["G"] / total * 100) if total else 0
    log(f"    cuota {rango:>5}: G={d['G']} P={d['P']} (win rate {wr:.0f}%)")

log("")
log("  HISTORIAL DETALLADO (todas las ops):")
for fecha, bin_t, c, p, s, paso, r in sorted(bins_por_op, key=lambda x: x[0]):
    icono = "✅" if r == "G" else "❌"
    log(f"    {icono} {fecha} | bin={bin_t:<10} | cuota={c:>6.2f} | p={p:>5.0%} | stake=${s:>5.2f} | paso={paso}")

# Publicar
inf = ["=" * 78,
       f"ANÁLISIS MERCADOS ELON - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
       "=" * 78, ""]
inf.extend(LOG)
inf.append("=" * 78)
texto = "\n".join(inf)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ok, info = publicar(texto, f"diag_hetzner/merca_elon_{ts}.txt")
if ok:
    log(f"\n✓ Publicado")
else:
    log(f"\n✗ Error: {info}")
