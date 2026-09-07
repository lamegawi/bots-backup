#!/bin/bash
# Inspeccionar SignedOrderV2 - busca en todos los modulos del SDK
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/inspect_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== INSPECCIONAR SignedOrderV2 - $(date) ==="
python3 << 'PYEOF'
import sys
# Buscar en todos los paths posibles
for p in ["/usr/local/lib/python3.12/dist-packages", "/usr/local/lib/python3.11/dist-packages",
          "/usr/lib/python3/dist-packages"]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Intentar importar desde varios modulos
SignedOrderV2 = None
for mod in ["py_clob_client_v2.clob_types", "py_clob_client_v2.order",
            "py_clob_client_v2.signed_order", "py_clob_client_v2.model"]:
    try:
        m = __import__(mod, fromlist=["SignedOrderV2"])
        if hasattr(m, "SignedOrderV2"):
            SignedOrderV2 = m.SignedOrderV2
            print(f"Encontrado en: {mod}")
            break
    except Exception as e:
        print(f"No en {mod}: {e}")

# Si no, buscar por nombre en todo el modulo
if SignedOrderV2 is None:
    print("\nBuscando en py_clob_client_v2...")
    import py_clob_client_v2 as pclob
    for name in dir(pclob):
        if "SignedOrder" in name or "signed" in name.lower():
            print(f"  {name}")
    for sub in dir(pclob):
        try:
            obj = getattr(pclob, sub)
            if hasattr(obj, "__path__"):  # es un modulo
                for n in dir(obj):
                    if "Signed" in n:
                        print(f"  {sub}.{n}")
        except: pass
    # Buscar en clob_types
    try:
        from py_clob_client_v2 import clob_types
        print(f"\nclob_types tiene: {[x for x in dir(clob_types) if 'ign' in x]}")
    except Exception as e:
        print(f"Error: {e}")
    sys.exit(1)

# Si lo encontramos, inspeccionar
print(f"\n=== SignedOrderV2 ===")
print(f"Tipo: {type(SignedOrderV2)}")
import dataclasses
if dataclasses.is_dataclass(SignedOrderV2):
    print(f"Es dataclass")
    print(f"Campos: {[f.name for f in dataclasses.fields(SignedOrderV2)]}")

# Crear uno fake con todos los campos
import inspect
try:
    sig = inspect.signature(SignedOrderV2.__init__)
    print(f"\nInit signature: {sig}")
    kwargs = {p: "test" for p in sig.parameters if p != "self"}
    o = SignedOrderV2(**kwargs)
    print(f"\nObjeto: {o}")
    print(f"vars: {vars(o)}")

    # Probar serializar
    import json
    try:
        j = json.dumps(o.__dict__)
        print(f"\njson.dumps(__dict__) OK: {j}")
    except Exception as e:
        print(f"json.dumps(__dict__) ERROR: {e}")
    try:
        d = dataclasses.asdict(o)
        j = json.dumps(d)
        print(f"\ndataclasses.asdict OK: {j}")
    except Exception as e:
        print(f"\ndataclasses.asdict ERROR: {e}")
except Exception as e:
    print(f"Error: {e}")
PYEOF

# Publicar
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/inspect_${TS}.log"
  CONTenido=$(cat "$LOG")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'inspect ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'inspect ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
fi
