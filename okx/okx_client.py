#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conector OKX (API v5) para el bot de trading — Europa (my.okx.com).

Particularidades de OKX Europa (verificadas):
  - Dominio: https://my.okx.com  (las claves EEE NO valen en www.okx.com)
  - Cabecera "User-Agent" OBLIGATORIA (sin ella Cloudflare bloquea con 1010).
  - Demo: cabecera "x-simulated-trading: 1" + clave creada en el entorno demo.
  - X-Perps: instType=FUTURES, instId "XXX-USD_UM_XPERP-YYMMDD", liquidan en USD
    (USDC/USDG). El tamaño se da en CONTRATOS (sz entero), cada contrato vale
    ctVal unidades de la moneda base (p.ej. BTC: 0.0001 BTC/contrato).

Uso:
    import okx_client as OKX
    c = OKX.Cliente(demo=True)          # o demo=False
    c.saldo()  c.posiciones()  c.orden_mercado(...)  c.cerrar(...)
"""
import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE = "https://my.okx.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


class Cliente:
    def __init__(self, api_key, secret, passphrase, demo=False):
        self.key = api_key.strip()
        self.secret = secret.strip()
        self.passphrase = passphrase.strip()
        self.demo = demo
        self._instr_cache = {"ts": 0.0, "map": {}}   # base -> instId XPERP

    # ------------------------------------------------------------- firma
    def _ts(self):
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(time.time()*1000)%1000:03d}Z"

    def _sign(self, ts, method, path, body):
        pre = ts + method + path + (body or "")
        mac = hmac.new(self.secret.encode(), pre.encode(), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()

    def _req(self, method, path, body_dict=None):
        body = json.dumps(body_dict, separators=(",", ":")) if body_dict else ""
        ts = self._ts()
        sign = self._sign(ts, method, path, body)
        headers = {
            "OK-ACCESS-KEY": self.key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "User-Agent": UA,
        }
        if self.demo:
            headers["x-simulated-trading"] = "1"
        data = body.encode() if body else None
        req = urllib.request.Request(BASE + path, data=data, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raw = e.read().decode()[:300]
            raise RuntimeError(f"OKX HTTP {e.code}: {raw}")

    def _get(self, path):
        return self._req("GET", path)

    def _post(self, path, body):
        return self._req("POST", path, body)

    def _check(self, resp, where):
        code = str(resp.get("code", ""))
        if code != "0":
            raise RuntimeError(f"{where}: code={code} msg={resp.get('msg')}")
        return resp

    # -------------------------------------------------------- instrumentos
    def instrumentos_xperp(self, refrescar=False):
        """Devuelve {base: instId} de los X-Perps disponibles (FUTURES)."""
        if self._instr_cache["map"] and not refrescar \
                and time.time() - self._instr_cache["ts"] < 3600:
            return self._instr_cache["map"]
        r = self._get("/api/v5/public/instruments?instType=FUTURES")
        mapa = {}
        for x in (r.get("data") or []):
            iid = x.get("instId", "")
            if "XPERP" in iid.upper() and x.get("state") == "live":
                base = iid.split("-")[0]
                if base not in mapa:
                    mapa[base] = iid
        self._instr_cache = {"ts": time.time(), "map": mapa}
        return mapa

    def inst_id(self, base):
        """instId del X-Perp de una moneda base (p.ej. 'BTC' -> 'BTC-USD_UM_XPERP-310404')."""
        base = base.upper().replace("USDT", "").replace("USDC", "").replace("-", "")
        return self.instrumentos_xperp().get(base)

    def info_instr(self, inst_id):
        r = self._get(f"/api/v5/public/instruments?instType=FUTURES&instId={inst_id}")
        data = (r.get("data") or [])
        return data[0] if data else {}

    # ------------------------------------------------------------- saldo
    def saldo(self):
        """Devuelve {'ccy', 'available', 'equity', 'unrealized'}.

        - equity: totalEq de la cuenta (multi-divisa, en USD).
        - available: saldo disponible en USDC (la divisa de margen del bot).
        - unrealized: suma del upl de las posiciones abiertas.
        """
        r = self._check(self._get("/api/v5/account/balance"), "balance")
        d = (r.get("data") or [{}])[0]
        equity = float(d.get("totalEq", 0) or 0)
        usdc_avail = 0.0
        for det in (d.get("details") or []):
            if det.get("ccy") == "USDC":
                usdc_avail = float(det.get("availBal", 0) or 0)
                break
        unreal = 0.0
        try:
            for p in self.posiciones():
                unreal += float(p.get("upl", 0) or 0)
        except Exception:
            pass
        return {"ccy": "USD", "available": usdc_avail, "equity": equity,
                "unrealized": unreal}

    def posiciones(self):
        """Posiciones abiertas (FUTURES) con pos != 0."""
        r = self._check(self._get("/api/v5/account/positions?instType=FUTURES"),
                        "positions")
        out = []
        for p in (r.get("data") or []):
            pos = float(p.get("pos", 0) or 0)
            if pos == 0:
                continue
            out.append(p)
        return out

    def posiciones_cerradas(self, inst_id=None, limit=5):
        """Últimas posiciones CERRADAS (histórico) con su P&L realizado.

        Devuelve lista (más reciente primero) con {instId, type, openAvgPx,
        closeAvgPx, closeTotalPos, pnl, realizedPnl, fee, uTime, posId}."""
        path = "/api/v5/account/positions-history?instType=FUTURES"
        if inst_id:
            path += "&instId=" + urllib.parse.quote(inst_id)
        path += "&limit=%d" % int(limit)
        r = self._check(self._get(path), "positions-history")
        return r.get("data") or []

    # ------------------------------------------------------------- mercado
    def ticker(self, inst_id):
        r = self._check(self._get(f"/api/v5/market/ticker?instId={inst_id}"),
                        "ticker")
        return (r.get("data") or [{}])[0]

    def velas(self, inst_id, bar="1H", limit=200):
        """Velas ascendentemente: [{time, open, high, low, close, vol}]."""
        r = self._get(f"/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}")
        data = r.get("data") or []
        out = []
        for row in data:   # [ts, o, h, l, c, vol, ...] (nuevas primero)
            try:
                out.append({"time": int(row[0]), "open": float(row[1]),
                            "high": float(row[2]), "low": float(row[3]),
                            "close": float(row[4]), "vol": float(row[5] or 0)})
            except Exception:
                continue
        out.sort(key=lambda k: k["time"])
        return out

    # ----------------------------------------------------------- operativa
    def set_apalancamiento(self, inst_id, lever):
        self._check(self._post("/api/v5/account/set-leverage",
                               {"instId": inst_id, "lever": str(int(lever)),
                                "mgnMode": "cross", "posSide": "net"}),
                    "set-leverage")

    def orden_mercado(self, inst_id, side, sz_contratos, tp_px=None, sl_px=None):
        """Orden a mercado (side: buy/sell). sz en CONTRATOS (entero).

        tp_px/sl_px: precios de TP/SL adjuntos (market cuando se disparan)."""
        body = {"instId": inst_id, "tdMode": "cross", "side": side,
                "posSide": "net", "ordType": "market", "sz": str(int(sz_contratos))}
        if tp_px is not None:
            body["tpTriggerPx"] = str(tp_px)
            body["tpOrdPx"] = "-1"
            body["tpTriggerPxType"] = "last"
        if sl_px is not None:
            body["slTriggerPx"] = str(sl_px)
            body["slOrdPx"] = "-1"
            body["slTriggerPxType"] = "last"
        return self._check(self._post("/api/v5/trade/order", body), "order")

    # ------------------------------------------------ órdenes algo (SL / TP)
    def orden_algo_sl(self, inst_id, side_cierre, sl_px, sz_contratos):
        """SL: orden condicional que cierra a mercado al tocar sl_px."""
        body = {"instId": inst_id, "tdMode": "cross", "posSide": "net",
                "side": side_cierre, "ordType": "conditional",
                "sz": str(int(sz_contratos)),
                "slTriggerPx": str(sl_px), "slTriggerPxType": "last",
                "slOrdPx": "-1", "reduceOnly": "true"}
        r = self._check(self._post("/api/v5/trade/order-algo", body), "order-algo-sl")
        return (r.get("data") or [{}])[0].get("algoId")

    def orden_algo_tp(self, inst_id, side_cierre, tp_px, sz_contratos):
        """TP (parcial o total): orden condicional que cierra a mercado."""
        body = {"instId": inst_id, "tdMode": "cross", "posSide": "net",
                "side": side_cierre, "ordType": "conditional",
                "sz": str(int(sz_contratos)),
                "tpTriggerPx": str(tp_px), "tpTriggerPxType": "last",
                "tpOrdPx": "-1", "reduceOnly": "true"}
        r = self._check(self._post("/api/v5/trade/order-algo", body), "order-algo-tp")
        return (r.get("data") or [{}])[0].get("algoId")

    def algo_pendientes(self, inst_id=None):
        """Órdenes algo (conditional) pendientes. [{algoId, side, sz, tpTriggerPx,
        slTriggerPx, state}]."""
        path = "/api/v5/trade/orders-algo-pending?ordType=conditional"
        if inst_id:
            path += f"&instId={inst_id}"
        r = self._check(self._get(path), "algo-pending")
        return r.get("data") or []

    def cancelar_algo(self, inst_id, algo_id):
        # cancel-algos espera un ARRAY de objetos en el body
        body = [{"instId": inst_id, "algoId": str(algo_id)}]
        return self._check(self._post("/api/v5/trade/cancel-algos", body),
                           "cancel-algo")

    def cancelar_todas_algo(self, inst_id):
        """Cancela todas las órdenes algo de un instrumento."""
        pend = self.algo_pendientes(inst_id)
        for o in pend:
            try:
                self.cancelar_algo(inst_id, o.get("algoId"))
            except Exception:
                pass
        return len(pend)

    def mover_sl_algo(self, inst_id, algo_id, nuevo_sl_px):
        """Modifica el precio de disparo de una orden algo (SL a break-even)."""
        body = {"instId": inst_id, "algoId": str(algo_id),
                "newSlTriggerPx": str(nuevo_sl_px)}
        return self._check(self._post("/api/v5/trade/amend-algos", body),
                           "amend-algos")

    def cerrar(self, inst_id, side, sz_contratos=None):
        """Cierra la posición a mercado (reduceOnly). side = lado de la POSICIÓN
        (long->sell, short->buy). Si sz None, cierra todo con la orden closePosition."""
        if sz_contratos is None:
            # cierra la posición completa
            body = {"instId": inst_id, "tdMode": "cross", "posSide": "net",
                    "mgnMode": "cross", "autoCxl": "false"}
            if side == "long":
                body["side"] = "sell"
            else:
                body["side"] = "buy"
            return self._post("/api/v5/trade/close-position", body)
        cierre = "sell" if side == "long" else "buy"
        body = {"instId": inst_id, "tdMode": "cross", "side": cierre,
                "posSide": "net", "ordType": "market",
                "sz": str(int(sz_contratos)), "reduceOnly": "true"}
        return self._check(self._post("/api/v5/trade/order", body), "close")

    def contratos(self, inst_id, notional_usd):
        """Nº de contratos (entero) para un nocional en USD dado."""
        info = self.info_instr(inst_id)
        ct_val = float(info.get("ctVal", 0) or 0)
        if ct_val <= 0:
            return 1
        precio = float(self.ticker(inst_id).get("last", 0) or 0)
        if precio <= 0:
            return 1
        n = notional_usd / (ct_val * precio)
        return max(1, int(round(n)))
# === FIX4_ARENA: historial de posiciones cerradas (P&L) ===
def _pos_hist_arena(self, limit=100):
    r = self._check(self._get("/api/v5/account/positions-history?instType=FUTURES&limit=" + str(int(limit))), "positions-history")
    return r.get("data") or []
Cliente.posiciones_historicas = _pos_hist_arena

# === FIX1_ARENA: _check muestra el detalle real de OKX (sCode/sMsg) ===
def _arena_check(self, resp, where):
    code = str(resp.get("code", ""))
    if code != "0":
        _data = resp.get("data")
        _d = _data[0] if isinstance(_data, list) and _data else {}
        raise RuntimeError(where + ": code=" + code + " msg=" + str(resp.get("msg")) + " | detail=" + str(_d.get("sCode")) + ":" + str(_d.get("sMsg")))
    return resp
Cliente._check = _arena_check

# === FIXR_ARENA: SL/TP con reduceOnly (una orden huerfana nunca podra abrir posicion) ===
