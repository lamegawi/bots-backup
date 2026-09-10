#!/usr/bin/env bash
# test_proxy.sh — Diagnostica conectividad Hetzner -> PC proxy Tailscale
set -u
TS_IP=${TS_IP:-100.83.57.99}
echo "== Test Tailscale =="
tailscale status 2>&1 | head -10
echo
echo "== Mi IP Tailscale =="
tailscale ip -4 2>&1
echo
echo "== Ping $TS_IP =="
ping -c 2 "$TS_IP" 2>&1 | tail -4
echo
echo "== Puerto $TS_IP:8888 =="
nc -zv -w 5 "$TS_IP" 8888 2>&1
echo
echo "== Curl verbose con proxy =="
curl -v --max-time 8 -x "http://${TS_IP}:8888" https://api.ipify.org 2>&1 | head -25
echo
echo "== Curl con proxy vía env =="
http_proxy="http://${TS_IP}:8888" https_proxy="http://${TS_IP}:8888" \
  curl -v --max-time 8 https://api.ipify.org 2>&1 | head -25
echo
echo "== Desde la IP de Tailscale del Hetzner (sin proxy) =="
curl -s --max-time 5 https://api.ipify.org
echo
echo "== Test HTTPS CONNECT directo al proxy =="
echo -e "CONNECT api.ipify.org:443 HTTP/1.1\r\nHost: api.ipify.org:443\r\n\r\n" | \
  timeout 5 nc "$TS_IP" 8888 2>&1 | head -5
