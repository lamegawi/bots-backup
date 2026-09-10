#!/usr/bin/env python3
"""parse_jina.py — extrae info de un MD scrapeado por jina de polymarket.com
IMPORTANTE: SOLO devuelve CONTAJE, CONDITION_ID, y porcentajes como 'PCT_X'.
Los precios vienen del CLOB (no del scraper, que solo da porcentajes).
"""
import re, sys

def parse(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        md = f.read()

    # Tweet count
    m_tc = re.search(r"TWEET\s*COUNT\s*\n?\s*(\d+)", md, re.IGNORECASE)
    print("CONTAJE", m_tc.group(1) if m_tc else 0)

    # Tiempo restante
    m_t = re.search(r"(\d+)\s*DAYS?\s*(\d+)\s*HOURS?\s*(\d+)\s*MIN", md, re.IGNORECASE)
    if m_t:
        print("DIAS", m_t.group(1))
        print("HORAS", m_t.group(2))
        print("MIN", m_t.group(3))

    # Porcentajes de cada bin (SOLO para info, NO se usan como precio)
    bins = ["120-139", "140-159", "160-179", "180-199", "200-219"]
    for b in bins:
        m = re.search(re.escape(b) + r"[\s\S]{0,40}?(\d+(?:\.\d+)?)\s*%", md)
        if m:
            print(f"PCT_{b}", m.group(1))

    # conditionId para consultar CLOB
    m_c = re.search(r'conditionId["\'\s:=]+(0x[0-9a-fA-F]{40,64})', md)
    if m_c:
        print("COND", m_c.group(1))

if __name__ == "__main__":
    parse(sys.argv[1] if len(sys.argv) > 1 else "/tmp/auto_exit_elon/_last_jina.md")
