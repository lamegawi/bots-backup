#!/usr/bin/env python3
import os
import hashlib

print("=== Verificación del PAT en disco ===\n")

# 1) Buscar todos los archivos posibles
candidatos = [
    "/root/diag_token.txt",
    "/opt/polymarket/diag_token.txt",
    os.path.expanduser("~/diag_token.txt"),
    "/tmp/diag_token.txt",
    "/root/.github_token",
    "/root/.config/gh/hosts.yml",
]
print("Archivos encontrados:")
for r in candidatos:
    if os.path.exists(r):
        sz = os.path.getsize(r)
        with open(r, "rb") as f:
            contenido = f.read()
        # Hash para comparar sin mostrar el contenido
        h = hashlib.sha256(contenido).hexdigest()[:16]
        print(f"  {r}: {sz} bytes, sha256={h}")
        # Mostrar primeros y últimos bytes (sin el secreto)
        try:
            texto = contenido.decode("utf-8", errors="replace")
            primera_linea = texto.split("\n")[0]
            if "ghp_" in primera_linea or "github_pat_" in primera_linea:
                # Sí es un PAT
                print(f"    Parece PAT: empieza por '{primera_linea[:8]}', longitud {len(primera_linea)}")
            else:
                print(f"    Contenido: {repr(primera_linea[:50])}")
        except Exception as e:
            print(f"    Error leyendo: {e}")
    else:
        print(f"  {r}: no existe")

print("\n=== Probar el PAT de /root/diag_token.txt con API real ===")
pat_file = "/root/diag_token.txt"
if os.path.exists(pat_file):
    with open(pat_file) as f:
        pat = f.read().strip()
    print(f"Longitud PAT: {len(pat)}")
    print(f"Empieza por: '{pat[:8]}'")
    print(f"Termina en: '{pat[-4:]}'")
    print(f"Hash: {hashlib.sha256(pat.encode()).hexdigest()[:16]}")
    
    # Probar GET con rate_limit (no requiere user scope)
    import urllib.request
    import urllib.error
    import json
    try:
        req = urllib.request.Request(
            "https://api.github.com/rate_limit",
            headers={"Authorization": f"token {pat}", "User-Agent": "test", "Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            print(f"\n✓ GET rate_limit OK: {data['rate']['remaining']} restantes")
    except urllib.error.HTTPError as e:
        print(f"\n✗ GET rate_limit: HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
    
    # Probar PUT
    try:
        import base64
        ts_str = os.popen("date +%Y%m%d_%H%M%S").read().strip()
        body = f"test from hetzner {ts_str}"
        b64 = base64.b64encode(body.encode()).decode()
        ruta = f"diag_hetzner/test_pat_{ts_str}.txt"
        payload = {"message": f"test {ts_str}", "content": b64, "branch": "diag-public"}
        req = urllib.request.Request(
            f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}",
            data=json.dumps(payload).encode(), method="PUT",
            headers={"Authorization": f"token {pat}", "Content-Type": "application/json",
                     "Accept": "application/vnd.github+json", "User-Agent": "test"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"✓ PUT OK: HTTP {r.status}")
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        print(f"✗ PUT HTTP {e.code}: {body_err[:500]}")
    except Exception as e:
        print(f"✗ PUT error: {type(e).__name__}: {e}")
else:
    print(f"No existe {pat_file}")
