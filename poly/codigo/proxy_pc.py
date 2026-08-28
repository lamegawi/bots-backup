#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Proxy HTTP/HTTPS simple — salida por la IP de ESTE PC.

Sustituto de pproxy (que no funciona en Python 3.14). Solo usa la
librería estándar: funciona en cualquier Python 3.7+.

Uso:
    python proxy_pc.py [puerto]      # puerto por defecto: 8888

Soporta:
  - HTTPS: método CONNECT (túnel) — lo que usan las APIs de Polymarket
  - HTTP normal (GET/POST) — reenvío directo

Mantén esta ventana abierta (y el PC encendido).
"""
import socket
import sys
import threading

PUERTO = 8888
if len(sys.argv) > 1:
    PUERTO = int(sys.argv[1])

HOST = "0.0.0.0"          # escucha en todas las interfaces (incl. Tailscale)
BUFSIZE = 65536


def cerrar(s):
    try:
        s.close()
    except Exception:
        pass


def relay(a, b):
    """Copia bytes de a -> b hasta que alguno cierre."""
    try:
        while True:
            data = a.recv(BUFSIZE)
            if not data:
                break
            b.sendall(data)
    except Exception:
        pass
    finally:
        cerrar(a)
        cerrar(b)


def manejar_cliente(client):
    try:
        client.settimeout(60)
        buf = bytearray()
        # leer cabeceras hasta CRLFCRLF, conservando los bytes sobrantes
        while b"\r\n\r\n" not in buf:
            chunk = client.recv(BUFSIZE)
            if not chunk:
                return
            buf += chunk
            if len(buf) > 1_000_000:
                return
        idx = buf.index(b"\r\n\r\n") + 4
        cabeceras = bytes(buf[:idx])
        sobrante = bytes(buf[idx:])

        primera = cabeceras.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        partes = primera.split()
        if len(partes) < 3:
            return
        metodo, objetivo, version = partes[0], partes[1], partes[2]

        # ---------- HTTPS: CONNECT (túnel) ----------
        if metodo.upper() == "CONNECT":
            try:
                host, port = objetivo.rsplit(":", 1)
                port = int(port)
            except Exception:
                return
            try:
                upstream = socket.create_connection((host, port), timeout=20)
            except Exception:
                try:
                    client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                except Exception:
                    pass
                return
            try:
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            except Exception:
                cerrar(upstream)
                return
            if sobrante:
                try:
                    upstream.sendall(sobrante)
                except Exception:
                    pass
            t1 = threading.Thread(target=relay, args=(client, upstream), daemon=True)
            t2 = threading.Thread(target=relay, args=(upstream, client), daemon=True)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            return

        # ---------- HTTP normal ----------
        resto = cabeceras.split(b"\r\n", 1)[1]
        host = None
        port = 80
        for linea in resto.split(b"\r\n"):
            if linea.lower().startswith(b"host:"):
                hv = linea.split(b":", 1)[1].strip().decode("latin-1", "replace")
                if ":" in hv:
                    h, p = hv.rsplit(":", 1)
                    host, port = h, int(p)
                else:
                    host = hv
                break
        if not host:
            try:
                client.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            except Exception:
                pass
            return

        path = objetivo
        if objetivo.lower().startswith("http://"):
            path = objetivo.split("://", 1)[1]
            path = "/" + path.split("/", 1)[1] if "/" in path else "/"

        try:
            upstream = socket.create_connection((host, port), timeout=20)
        except Exception:
            try:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            except Exception:
                pass
            return

        nueva = (metodo + " " + path + " " + version + "\r\n").encode("latin-1") + resto
        try:
            upstream.sendall(nueva)
            if sobrante:
                upstream.sendall(sobrante)
        except Exception:
            cerrar(upstream)
            return
        relay(upstream, client)
    except Exception:
        pass
    finally:
        cerrar(client)


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((HOST, PUERTO))
    except OSError as e:
        print(f"ERROR: no se pudo abrir el puerto {PUERTO}: {e}")
        print("Puede que otro programa lo esté usando, o falte permiso.")
        return
    srv.listen(128)
    print(f"✅ Proxy escuchando en {HOST}:{PUERTO}")
    print("   Las conexiones saldrán con la IP de ESTE PC.")
    print("   Mantén esta ventana abierta. Ctrl+C para salir.")
    sys.stdout.flush()
    try:
        while True:
            client, addr = srv.accept()
            threading.Thread(target=manejar_cliente, args=(client,), daemon=True).start()
    except KeyboardInterrupt:
        print("\nProxy detenido.")
    finally:
        cerrar(srv)


if __name__ == "__main__":
    main()
