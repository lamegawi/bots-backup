#!/usr/bin/env bash
# verificar_saldo_clob.sh — saca el saldo REAL del CLOB autenticado
# Usa POLY_PRIVATE_KEY del .env y firma con la EOA del bot
# Devuelve el balance en USDC.e con 6 decimales de precisión
set -euo pipefail
TS=$(date -u +%Y%m%d_%H%M%S)

# Cargar env
if [ -f /etc/polymarket.env ]; then
    export $(grep -E "^POLY_(PRIVATE_KEY|WALLET_ADDRESS|RELAYER_API_KEY|RELAYER_API_KEY_ADDRESS)=" /etc/polymarket.env | xargs)
fi

# Ejecutar Python con el SDK
/usr/bin/python3 << 'PYEOF'
import os, json, re
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

# Cargar PRIVATE_KEY
PRIVATE_KEY = os.environ.get('POLY_PRIVATE_KEY', '').strip()
if not PRIVATE_KEY:
    print("❌ POLY_PRIVATE_KEY no configurado")
    exit(1)

# EOA por defecto del bot
FUNDER = os.environ.get('POLY_WALLET_ADDRESS', '0xb0E1197098E6d427c01720F1631cAD24CE740FA0')

HOST = 'https://clob.polymarket.com'
CHAIN_ID = 137

# Cliente autenticado
client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=CHAIN_ID,
    signature_type=1,  # Magic.link signature
    funder=FUNDER
)

# API creds
api_creds = client.create_or_derive_api_creds()
client.set_api_creds(api_creds)

# Balance
params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
result = client.get_balance_allowance(params)
data = json.loads(result) if isinstance(result, str) else result
raw_balance = data.get('balance', 0) if isinstance(data, dict) else 0

# USDC.e tiene 6 decimales
balance_usd = int(raw_balance) / 1_000_000

# Salida JSON para fácil parsing
out = {
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "wallet": FUNDER,
    "balance_raw": raw_balance,
    "balance_usdc": balance_usd,
    "source": "CLOB API autenticado (get_balance_allowance COLLATERAL)"
}

print(json.dumps(out, indent=2))
PYEOF
