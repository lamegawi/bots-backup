#!/bin/bash
# Inspeccionar SignedOrderV2 para saber como serializarlo
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/inspect_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== INSPECCIONAR SignedOrderV2 - $(date) ==="
python3 << 'PYEOF'
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
sys.path.insert(0, "/usr/local/lib/python3.11/dist-packages")
try:
    from py_clob_client_v2.clob_types import SignedOrderV2
    print(f"SignedOrderV2 importado: {SignedOrderV2}")
    print(f"Tipo: {type(SignedOrderV2)}")
    # Ver si es dataclass
    import dataclasses
    if dataclasses.is_dataclass(SignedOrderV2):
        print("Es dataclass")
        print(f"Campos: {[f.name for f in dataclasses.fields(SignedOrderV2)]}")
    # Ver campos
    print(f"dir: {[x for x in dir(SignedOrderV2) if not x.startswith('_')]}")
    # Crear uno fake
    try:
        from py_clob_client_v2.clob_types import OrderArgs
        o = SignedOrderV2(
            salt="123",
            maker="0x1234",
            signer="0x1234",
            tokenId="0x1234",
            makerAmount="1000",
            takerAmount="2000",
            expiration="0",
            nonce="0",
            feeRateBps="0",
            side="BUY",
            signatureType=1,
            signature="0xabc"
        )
        print(f"\nObjeto creado: {o}")
        print(f"vars: {vars(o)}")
        print(f"__dict__: {o.__dict__}")
        # Probar serializar
        import json
        try:
            j = json.dumps(o)
            print(f"json.dumps OK: {j[:100]}")
        except Exception as e:
            print(f"json.dumps ERROR: {e}")
        # Probar asdict
        try:
            d = dataclasses.asdict(o)
            j = json.dumps(d)
            print(f"dataclasses.asdict + json.dumps OK: {j[:100]}")
        except Exception as e:
            print(f"dataclasses.asdict ERROR: {e}")
    except Exception as e:
        print(f"Error creando objeto: {e}")
except Exception as e:
    print(f"Error importando: {e}")
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
