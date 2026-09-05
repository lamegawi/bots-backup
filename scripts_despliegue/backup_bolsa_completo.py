#!/usr/bin/env python3
"""Backup completo del bot de bolsa.

Guarda una copia local y sube a GitHub el código y los datos de bolsa.
No contiene tokens: el PAT se lee únicamente desde el servidor.
"""
import base64
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = "lamegawi/bots-backup"
BRANCH = "arena/01a0587c-bots-backup"
REMOTE_ROOT = "backups_bolsa_completos"
LOCAL_ROOT = Path("/root/backup_bolsa_local")

FILES = [
    ("codigo", "/root/bolsa_bot.py"),
    ("config", "/root/bolsa_config.json"),
    ("cartera", "/root/bolsa_cartera.json"),
    ("alertas", "/root/bolsa_alertas.json"),
]


def find_pat():
    for filename in ("/root/diag_token.txt", "/tmp/diag_token.txt", "/root/.gist_token"):
        path = Path(filename)
        if path.exists():
            value = path.read_text().strip()
            if value:
                return value
    return os.environ.get("GH_PAT", "").strip()


PAT = find_pat()


def api_request(url, data=None, method="GET"):
    headers = {
        "Authorization": f"token {PAT}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "bolsa-backup",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def github_put(path, content, message):
    """Crea o actualiza un archivo en la rama de backup mediante Contents API."""
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    sha = None
    try:
        existing = api_request(f"{url}?ref={BRANCH}")
        sha = existing.get("sha")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    payload = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
    api_request(url, json.dumps(payload).encode(), method="PUT")


def command_text(command):
    try:
        return subprocess.check_output(command, shell=True, text=True,
                                       stderr=subprocess.STDOUT, timeout=20).strip()
    except Exception as exc:
        return f"(no disponible: {exc})"


def main():
    if not PAT:
        raise SystemExit("FALTA PAT: debe estar en /root/diag_token.txt o GH_PAT")

    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    day = now.strftime("%Y-%m-%d")
    remote_dir = f"{REMOTE_ROOT}/{day}_{ts}"
    local_dir = LOCAL_ROOT / f"{day}_{ts}"
    local_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    missing = []
    for label, source_name in FILES:
        source = Path(source_name)
        if not source.exists():
            missing.append(source_name)
            continue
        raw = source.read_bytes()
        if source.suffix == ".json":
            json.loads(raw.decode("utf-8"))
        shutil.copy2(source, local_dir / source.name)
        destination = f"{remote_dir}/{label}_{source.name}"
        github_put(destination, raw, f"backup bolsa {label} {ts}")
        uploaded.append(destination)

    service = command_text("systemctl is-active bolsa-bot 2>/dev/null || true")
    host = command_text("hostname")
    branch_sha = "desconocido"
    try:
        branch_info = api_request(
            f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"
        )
        branch_sha = branch_info.get("sha", "desconocido")
    except Exception as exc:
        branch_sha = f"no disponible: {exc}"

    report = (
        f"BACKUP COMPLETO BOT DE BOLSA\n"
        f"Fecha: {now.isoformat()}\n"
        f"Servidor: {host}\n"
        f"Servicio bolsa-bot: {service}\n"
        f"Rama: {BRANCH}\n"
        f"SHA rama: {branch_sha}\n"
        f"Copia local: {local_dir}\n"
        f"Archivos subidos: {len(uploaded)}\n"
        f"Archivos ausentes: {', '.join(missing) if missing else 'ninguno'}\n"
        f"No se incluyen tokens ni credenciales.\n"
    ).encode()
    github_put(f"{remote_dir}/informe_{ts}.txt", report, f"informe backup bolsa {ts}")
    (local_dir / f"informe_{ts}.txt").write_bytes(report)

    print(f"BACKUP_BOLSA_LOCAL={local_dir}")
    print(f"BACKUP_BOLSA_GITHUB={remote_dir}")
    print(f"SUBIDOS={len(uploaded)}")
    print(f"AUSENTES={len(missing)}")
    if missing:
        print("AVISO: faltan: " + ", ".join(missing))
    print("OK: backup completo del bot de bolsa subido a GitHub")


if __name__ == "__main__":
    main()
