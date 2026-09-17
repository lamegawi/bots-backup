#!/usr/bin/env bash
# instalar_twitterapi.sh — instalar script de recogida de tweets vía twitterapi.io
# Cubre los 3 bots (Elon, Trump, Zelenskyy) con una sola API key
# Endpoint usado: /twitter/user/last_tweets (no /user/tweets — marca a @elonmusk como 'Suspended' falsamente)
set -euo pipefail
TS=$(date -u +%Y%m%d_%H%M%S)

echo "=== INSTALAR TWITTERAPI.IO · ${TS} UTC ==="

# 1. Comprobar que hay API key
if ! grep -q "^TWITTERAPI_KEY=" /etc/polymarket.env; then
    echo "❌ ERROR: añade TWITTERAPI_KEY=tu_clave a /etc/polymarket.env"
    exit 1
fi

# 2. Crear script
cat > /opt/polymarket/recoger_tweets_rapidapi.py << 'PYEOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recoger_tweets_rapidapi.py — tweets para 3 bots (Elon, Trump, Zelenskyy)
USA: twitterapi.io (endpoint /user/last_tweets)
"""
import os, sys, json, csv, argparse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from collections import defaultdict

API_HOST = "api.twitterapi.io"
API_KEY = os.environ.get("TWITTERAPI_KEY", "").strip()

if not API_KEY:
    sys.exit("❌ ERROR: configura TWITTERAPI_KEY")

BOTS = {
    "elon": ("elonmusk", "/opt/polymarket/bot-polymarket-elon", "datos_elon.csv"),
    "trump": ("realDonaldTrump", "/opt/polymarket/bot-polymarket-trump", "datos_trump.csv"),
    "zelenskyy": ("ZelenskyyUa", "/opt/polymarket/bot-polymarket-zelenskyy", "datos_zelen.csv"),
}

def fetch_user_last_tweets(username):
    url = f"https://{API_HOST}/twitter/user/last_tweets?userName={username}"
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("data", {})

def parse_count(data):
    counts = defaultdict(int)
    tweets = data.get("tweets", [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for t in tweets:
        created = t.get("createdAt") or t.get("created_at") or ""
        if not created: continue
        try:
            dt = datetime.strptime(created, "%a %b %d %H:%M:%S %z %Y")
            if dt < cutoff: continue
            counts[dt.strftime("%Y-%m-%d")] += 1
        except: continue
    return dict(sorted(counts.items()))

def update_csv(csv_path, counts):
    rows = {}
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try: rows[r["fecha"]] = int(r["tweets"])
                except: pass
    rows.update(counts)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "tweets"])
        for fecha in sorted(rows):
            w.writerow([fecha, rows[fecha]])
    return len(counts)

def process_bot(bot_name):
    user, bot_dir, csv_name = BOTS[bot_name]
    csv_path = os.path.join(bot_dir, csv_name)
    print(f"📡 @{user} → {csv_path}")
    try:
        data = fetch_user_last_tweets(user)
    except urllib.error.HTTPError as e:
        sys.exit(f"❌ HTTP {e.code}: {e.read().decode()[:200]}")
    tweets = data.get("tweets", [])
    print(f"  recibidos: {len(tweets)} tweets")
    counts = parse_count(data)
    n = update_csv(csv_path, counts)
    print(f"  ✅ {n} días actualizados")
    recent = dict(list(counts.items())[-7:])
    if recent: print(f"  📊 últimos 7 días: {recent}")
    if tweets:
        t = tweets[0]
        print(f"  💬 último: [{t.get('createdAt','?')}] {(t.get('text','') or '')[:80]}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", required=True, choices=list(BOTS.keys()) + ["all"])
    args = ap.parse_args()
    bots = list(BOTS.keys()) if args.bot == "all" else [args.bot]
    for b in bots:
        try:
            process_bot(b)
            if len(bots) > 1: print()
        except SystemExit as e:
            if len(bots) == 1: raise
            print(f"⚠️ Error en {b}: {e}")
            print()
PYEOF

chmod +x /opt/polymarket/recoger_tweets_rapidapi.py
echo "✅ Script creado: /opt/polymarket/recoger_tweets_rapidapi.py"

# 3. Instalar cron con offsets para evitar 429
(crontab -l 2>/dev/null | grep -v "recoger_tweets_rapidapi"; cat << 'CRON'
# twitterapi.io: tweets cada 2h con offset para evitar 429
5 */2 * * * cd /opt/polymarket && /usr/bin/python3 recoger_tweets_rapidapi.py --bot elon >> /var/log/poly/twitterapi_elon.log 2>&1
15 */2 * * * cd /opt/polymarket && /usr/bin/python3 recoger_tweets_rapidapi.py --bot trump >> /var/log/poly/twitterapi_trump.log 2>&1
25 */2 * * * cd /opt/polymarket && /usr/bin/python3 recoger_tweets_rapidapi.py --bot zelenskyy >> /var/log/poly/twitterapi_zelen.log 2>&1
CRON
) | crontab -

echo "✅ Cron instalado"
echo
echo "=== Listo. Los 3 bots se actualizarán cada 2h. ==="
