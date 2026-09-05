#!/bin/bash
# Instala poly_combos_bot como servicio systemd
set -e
echo "== Bajando bot =="
curl -sL https://raw.githubusercontent.com/lamegawi/bots-backup/main/scripts_despliegue/poly_combos_bot.py -o /opt/polymarket/poly_combos_bot.py
chmod +x /opt/polymarket/poly_combos_bot.py

echo "== Verificando py-clob-client-v2 =="
pip install --quiet py-clob-client-v2 2>&1 | tail -3

echo "== Creando servicio systemd =="
cat > /etc/systemd/system/poly-combos-bot.service << 'SVC'
[Unit]
Description=Poly Combos Bot (Telegram copy-trading)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -u /opt/polymarket/poly_combos_bot.py
Restart=always
RestartSec=10
WorkingDirectory=/opt/polymarket
StandardOutput=append:/var/log/poly-combos-bot.log
StandardError=append:/var/log/poly-combos-bot.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVC
systemctl daemon-reload
systemctl enable poly-combos-bot
systemctl restart poly-combos-bot
sleep 3
systemctl status poly-combos-bot --no-pager
echo "== Listo =="
