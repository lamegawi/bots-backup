#!/usr/bin/env python3
"""Ver la estructura del JSON de mercados de Trump para arreglar el bot."""
import json
import base64
import urllib.request
import os
from datetime import datetime

PAT = None
for r in ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt")]:
    if os.path.exists(r):
        try:
            PAT = open(r).read().strip()
            if PAT.startswith("ghp_"):
                break
        except: pass
if not PAT:
    PAT = os.environ.get("GH_PAT", "")

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
    payload = {"message": f"struct {datetime.now().strftime('%H%M%S')}",
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

log = []
def out(s):
    print(s, flush=True)
    log.append(s)

out("=" * 70)
out(f"ESTRUCTURA MERCADOS TRUMP · {datetime.now().isoformat()}")
out("=" * 70)

# 1) Cargar el mercado_activo.json de Trump
fp = "/opt/polymarket/bot-polymarket-trump/mercado_activo.json"
out(f"\n[1] {fp}:")
if not os.path.exists(fp):
    out("  NO EXISTE")
else:
    try:
        with open(fp) as f:
            data = json.load(f)
        out(f"  claves: {list(data.keys())}")
        mercados = data.get("mercados", [])
        out(f"  total mercados: {len(mercados)}")
        if mercados:
            m = mercados[0]
            out(f"\n  Estructura del primer mercado:")
            out(f"    claves: {list(m.keys())}")
            for k, v in m.items():
                if isinstance(v, (str, int, float)):
                    out(f"    {k}: {v}")
                elif isinstance(v, list):
                    out(f"    {k}: [lista de {len(v)} elementos]")
                    if v and isinstance(v[0], dict):
                        out(f"      claves del primer elemento: {list(v[0].keys())}")
                elif isinstance(v, dict):
                    out(f"    {k}: {json.dumps(v, indent=2)[:200]}")
    except Exception as e:
        out(f"  ERROR: {e}")

# 2) Cargar el datos_trump.csv
fp = "/opt/polymarket/bot-polymarket-trump/datos_trump.csv"
out(f"\n[2] {fp}:")
if not os.path.exists(fp):
    out("  NO EXISTE")
else:
    out("  primeras 5 líneas:")
    with open(fp) as f:
        for i, linea in enumerate(f):
            if i >= 5: break
            out(f"    {linea.rstrip()}")

# 3) Comparar con zelenskyy para ver la diferencia
out(f"\n[3] Comparar con zelenskyy:")
fp_z = "/opt/polymarket/bot-polymarket-zelenskyy/mercado_activo.json"
if os.path.exists(fp_z):
    try:
        with open(fp_z) as f:
            data_z = json.load(f)
        mercados_z = data_z.get("mercados", [])
        if mercados_z:
            m = mercados_z[0]
            out(f"  claves del primer mercado de Zelenskyy:")
            for k in m.keys():
                out(f"    {k}")
    except Exception as e:
        out(f"  ERROR: {e}")

# Publicar
inf = ["=" * 78,
       f"ESTRUCTURA MERCADOS TRUMP - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
       "=" * 78]
inf.extend(log)
inf.append("=" * 78)
texto = "\n".join(inf)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ok, info = publicar(texto, f"diag_hetzner/struct_trump_{ts}.txt")
if ok:
    out(f"\n✓ Publicado")
else:
    out(f"\n✗ Error: {info}")
