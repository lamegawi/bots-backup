#!/usr/bin/env bash
echo "== Test gamma-api =="
curl -sv --max-time 15 "https://gamma-api.polymarket.com/markets?slug=elon-musk-of-tweets-september-4-september-11-2026" 2>&1 | head -40
echo
echo "== Con user-agent =="
curl -s --max-time 15 -A "Mozilla/5.0" "https://gamma-api.polymarket.com/markets?slug=elon-musk-of-tweets-september-4-september-11-2026" 2>&1 | head -c 600
echo
echo
echo "== Sin query, mercado general =="
curl -s --max-time 15 -A "Mozilla/5.0" "https://gamma-api.polymarket.com/markets?slug=elon-musk-of-tweets-september-1-september-8-2026" 2>&1 | head -c 600
