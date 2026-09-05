# INSTRUCCIONES PARA OTRA IA: CÓMO HACER BACKUPS DE BOTS POLYMARKET

> Documento de referencia. Compártelo con cualquier otra IA que vaya a gestionar
> los bots de Polymarket, para que sepa cómo hacer backups correctamente.

---

## 🎯 Contexto

Hay 3 bots de Polymarket corriendo en un servidor Hetzner (46.225.146.21). Los bots escriben continuamente en archivos JSON (`real.json`, `real_zelen.json`) que contienen:

- El saldo virtual
- Las operaciones históricas
- La operación activa (si la hay)

**Problema importante**: los JSON contienen un bug (la fórmula del PnL no cuadra con la realidad), así que a veces hay que restaurarlos desde backup. Por eso es crítico hacer backup ANTES de cualquier modificación.

---

## 🗂️ Tipos de backup que se hacen

### 1. Backup de CÓDIGO (.py) en GitHub

- **Cuándo**: cada vez que se modifica un script
- **Cómo**: `git add`, `git commit`, `git push` a la rama `arena/01a058fe-bots-backup`
- **Tags**: se crean tags de backup con `git tag -a "backup-YYYY-MM-DD-descripcion"`
- **Frecuencia**: cada cambio importante
- **Repositorio**: https://github.com/lamegawi/bots-backup

### 2. Backup de DATOS (.json) en GitHub

- **Cuándo**: cuando se hacen cambios importantes (sincronización, limpieza, etc.)
- **Cómo**: el script `backup_completo.py` sube los JSON a `backups_completos/<fecha>_<hora>/`
- **Estructura de la carpeta**:
  ```
  backups_completos/2026-09-05_20260905_074518/
  ├── json_elon_20260905_074518.json
  ├── json_zelenskyy_20260905_074518.json
  ├── git_info_20260905_074518.txt
  └── informe_20260905_074518.txt
  ```

### 3. Backup de DATOS en Hetzner (local)

- **Cuándo**: antes de modificar un JSON
- **Cómo**: el script `sincronizar_saldo_json_v3.py` (o similar) hace `shutil.copy2(fp, fp+".bak.YYYYMMDD_HHMMSS")` antes de tocar nada
- **Patrón**: `*.bak.YYYYMMDD_HHMMSS` junto al JSON original

---

## 🛠️ Scripts indispensables (en `scripts_despliegue/`)

1. **`backup_completo.py`** ← EL MÁS IMPORTANTE PARA BACKUPS
   - Lee los 3 JSON de Hetzner
   - Los sube a GitHub via Contents API (no necesita `git push`)
   - Sube también el `git_info` con el SHA actual (vía API de GitHub)
   - Genera un informe de lo que se hizo

2. **`saldo_real_total_v2.py`**
   - Lee el saldo REAL on-chain (no el virtual del JSON)
   - Usa `eth_call` directo a contratos de Polygon (pUSD, USDC.e, USDC)
   - Compara con el JSON para detectar divergencias

3. **`sincronizar_saldo_json_v3.py`**
   - Hace backup automático del JSON antes de modificarlo
   - Recalcula el saldo virtual para que cuadre con el real
   - Dry-run por defecto, `--apply` para ejecutar

4. **`seguimiento_filtros.py`**
   - Cuenta apuestas descartadas por el filtro p_lado<10% y cuota>25
   - Útil para evaluar si el filtro funciona

5. **`seguimiento_semanal.py`**
   - Análisis completo semanal
   - Configurado en cron: `0 9 * * 1`

---

## 📐 Patrón del script `backup_completo.py`

Estructura clave en Python:

```python
import os
import json
import base64
import urllib.request
from datetime import datetime


# PAT se busca en /root/diag_token.txt
def find_pat():
    for r in ["/root/diag_token.txt", "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            t = open(r).read().strip()
            if t.startswith("ghp_"):
                return t
    return os.environ.get("GH_PAT", "")


PAT = find_pat()
REPO = "lamegawi/bots-backup"
BRANCH = "arena/01a058fe-bots-backup"


def github_put(path, content_bytes, message):
    """Sube un archivo a GitHub via Contents API."""
    if not PAT:
        return False
    b64 = base64.b64encode(content_bytes).decode()
    sha = None
    # ver si ya existe
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/contents/{path}?ref={BRANCH}",
            headers={"Authorization": f"token {PAT}", "User-Agent": "diag"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            pass
    payload = {"message": message, "content": b64, "branch": BRANCH}
    if sha:
        payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/{path}",
        data=json.dumps(payload).encode(),
        method="PUT",
        headers={
            "Authorization": f"token {PAT}",
            "Content-Type": "application/json",
            "User-Agent": "diag",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return True
    except Exception:
        return False


# === MAIN ===
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
fecha = datetime.now().strftime("%Y-%m-%d")
backups_dir = f"backups_completos/{fecha}_{ts}"

# 1) Backup de los JSONs
BOTS = [
    ("elon", "Elon 48h", "/opt/polymarket/bot-polymarket-elon/real.json"),
    (
        "zelenskyy",
        "Zelenskyy sem",
        "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json",
    ),
    ("trump", "Trump mens", "/opt/polymarket/bot-polymarket-trump/real.json"),
]
for slug, nombre, fp in BOTS:
    if not os.path.exists(fp):
        continue
    with open(fp, "rb") as f:
        raw = f.read()
    json.loads(raw)  # validar que es JSON
    dst = f"{backups_dir}/json_{slug}_{ts}.json"
    github_put(dst, raw, f"backup completo {slug} {ts}")

# 2) Git info (vía API, no necesita repo local en Hetzner)
req = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/commits/{BRANCH}",
    headers={"Authorization": f"token {PAT}", "User-Agent": "diag"},
)
with urllib.request.urlopen(req, timeout=15) as r:
    d = json.loads(r.read())
    sha = d.get("sha", "")
    msg = d.get("commit", {}).get("message", "")
github_put(
    f"{backups_dir}/git_info_{ts}.txt",
    f"git rev: {sha}\ncommit: {msg}\n".encode(),
    f"backup info {ts}",
)

# 3) Informe
github_put(
    f"{backups_dir}/informe_{ts}.txt",
    f"BACKUP COMPLETO {ts}\n...".encode(),
    f"backup informe {ts}",
)
```

---

## 🚀 Cómo ejecutar el backup desde Hetzner

El usuario se conecta por SSH a Hetzner y ejecuta:

```bash
curl -sL https://raw.githubusercontent.com/lamegawi/bots-backup/<COMMIT>/scripts_despliegue/backup_completo.py -o /root/backup_completo.py
python3 -u /root/backup_completo.py
```

**Importante**:

- `<COMMIT>` es el hash corto del commit actual (ej. `ea35c9f`)
- El PAT debe estar en `/root/diag_token.txt` con permisos solo para el usuario `root`

---

## 📌 Formato de respuesta al usuario

Cuando el usuario pida ejecutar un script:

```
📌 Commit: ea35c9f
```

Y luego en 2 partes separadas:

**Parte 1: SSH** (incluir el comando SSH)

```
ssh root@46.225.146.21
```

**Parte 2: Comandos** (los comandos para ejecutar una vez conectado)

```
curl -sL https://raw.githubusercontent.com/lamegawi/bots-backup/ea35c9f/scripts_despliegue/backup_completo.py -o /root/backup_completo.py
python3 -u /root/backup_completo.py
```

**NO incluir la contraseña en los mensajes** (el usuario ya la sabe).

---

## ⚠️ Problemas comunes y soluciones

### 1. Otro agente hace push a la misma rama

El agente `arena-agent` también hace pushes a `arena/01a058fe-bots-backup`. Esto puede causar que mis commits se pierdan.

**Solución**: usar `git push --force` solo si es necesario y avisar al usuario.

### 2. El sandbox se resetea

A veces el sandbox donde trabajo se reinicia y pierdo el working tree.

**Solución**: hacer `git fetch origin && git reset --hard FETCH_HEAD` para recuperar el estado.

### 3. El script no encuentra el repo en Hetzner

El script busca el repo en `/root/bots-backup`, `/opt/bots-backup`, etc. Si no está en ninguno, no puede usar `git rev-parse`.

**Solución**: usar fallback a la API de GitHub (como hace el script actual con `https://api.github.com/repos/{REPO}/commits/{BRANCH}`).

### 4. El remote no tiene mis cambios

A veces la rama `arena/01a058fe-bots-backup` no se trackea bien en el sandbox.

**Solución**:

```bash
git fetch origin arena/01a058fe-bots-backup
git update-ref refs/remotes/origin/arena/01a058fe-bots-backup <SHA>
```

### 5. Push rechazado por cambios remotos

Si el push falla porque el remoto tiene commits que no tengo localmente:

```bash
git fetch origin
git rebase FETCH_HEAD
# o si el rebase falla:
git push --force-with-lease
```

---

## 🎯 Tags de backup (referencia histórica)

Tags creados durante el trabajo del 4-5 de septiembre de 2026:

- `backup-2026-09-04-filtros-sync` - tras aplicar filtros p_lado<10% y cuota<25
- `backup-2026-09-04-final` - tras añadir README
- `backup-2026-09-04-proxy-doc` - tras documentar el proxy MANOS POLYMARKET
- `backup-2026-09-05-limpio` - tras eliminar scripts v1/v2 obsoletos
- `backup-2026-09-05-final` - estado limpio con cron
- `backup-2026-09-05-completo` - tras primer backup completo con JSONs

---

## 💡 Reglas de oro

1. **SIEMPRE** hacer backup antes de modificar un JSON
2. **SIEMPRE** publicar el resultado a GitHub para tener redundancia
3. **NUNCA** hacer `git push --force` sin avisar al usuario (puede perder trabajo)
4. **NUNCA** incluir la contraseña en mensajes al usuario
5. **SIEMPRE** dar el hash del commit al usuario para que pueda verificar
6. **SIEMPRE** incluir el `ssh root@46.225.146.21` para que sea copy-paste
7. **SIEMPRE** respetar el formato de respuesta en 2 partes (SSH + comandos)
8. **SIEMPRE** usar el método on-chain (`eth_call` a Polygon) para leer el saldo real, NO el SDK CLOB
9. **SIEMPRE** explicar qué hace el script antes de pedir al usuario que lo ejecute
10. **SIEMPRE** esperar a que el usuario diga "hecho" antes de leer el resultado de `diag-public`

---

## 🔍 Información técnica adicional

### Bots y archivos JSON

| Bot | Servicio | Archivo JSON |
|---|---|---|
| Elon 48h | `poly-elon` | `/opt/polymarket/bot-polymarket-elon/real.json` |
| Zelenskyy semanal | `poly-zelenskyy` | `/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json` |
| Trump mensual | `poly-trump` | `/opt/polymarket/bot-polymarket-trump/real.json` |

### Contratos Polygon para leer saldo on-chain

| Token | Contrato | Decimales |
|---|---|---|
| pUSD | `0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB` | 6 |
| USDC.e | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` | 6 |
| USDC | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` | 6 |

### RPCs de Polygon (probar varios por si uno falla)

```python
rpcs = [
    "https://polygon-rpc.com",
    "https://1rpc.io/matic",
    "https://polygon.llamarpc.com",
    "https://rpc.ankr.com/polygon",
]
```

### Wallet del usuario

- Dirección: `0xb0e1197098e6d427c01720f1631cad24ce740fa0`
- Está en `/root/wallet_address.txt` y en `/etc/polymarket.env`

### Proxy MANOS POLYMARKET (en el PC del usuario)

- Archivo: `poly/codigo/proxy_pc.py`
- Puerto: 8888
- Host: 0.0.0.0
- Función: hace que las operaciones de Polymarket salgan con la IP del PC del usuario
- **Crítico**: el PC debe estar encendido y Tailscale activo

### Filtros aplicados (en senal_vivo.py de los 3 bots)

```python
# Filtro de seguridad (arena 2026-09-04)
if p_lado < 0.10:
    log(f"  · [FILTRO] descartado ...")
    continue
if cuota_lado and cuota_lado > 25:
    log(f"  · [FILTRO] descartado ...")
    continue
```

### Cron semanal instalado

```
0 9 * * 1 /usr/bin/python3 -u /root/seguimiento_semanal.py >> /root/semanal.log 2>&1
```

Todos los lunes a las 9:00 se ejecuta automáticamente y publica en `diag-public`.

---

## 📂 Estructura del workspace

```
/home/user/bots-backup/
├── poly/                              # Código fuente
│   ├── codigo/
│   │   ├── bot-polymarket-elon/
│   │   ├── bot-polymarket-zelenskyy/
│   │   ├── bot-polymarket-trump/
│   │   └── proxy_pc.py                # El proxy que corre en el PC
│   └── ESTADO.md
├── scripts_despliegue/                # Scripts de diagnóstico y backup
│   ├── backup_completo.py             # EL MÁS IMPORTANTE
│   ├── saldo_real_total_v2.py
│   ├── sincronizar_saldo_json_v3.py
│   ├── seguimiento_filtros.py
│   ├── seguimiento_semanal.py
│   ├── verificacion_matutina.py
│   ├── snapshot_jsons.py
│   ├── tarjeta_acciones_5puntos.py
│   ├── install_cron_semanal.sh
│   ├── limpiar_historial_zelen_v3.py
│   ├── verificar_filtros_3bots_v2.py
│   ├── consultar_saldo_clob_v7.py
│   ├── balance_3_bots.py
│   ├── ver_fixcal_3_bots.py
│   ├── analisis_mercados_elon.py
│   ├── MANOS_POLYMARKET_REFERENCIA.md
│   ├── INSTRUCCIONES_DIAGNOSTICO_REMOTO.md
│   ├── INSTRUCCIONES_SSH.md
│   └── CHEATSHEET.txt
├── backups_completos/                 # Backups subidos a GitHub
│   └── YYYY-MM-DD_YYYYMMDD_HHMMSS/
│       ├── json_elon_*.json
│       ├── json_zelenskyy_*.json
│       ├── git_info_*.txt
│       └── informe_*.txt
├── BACKUP_2026-09-04.md               # README de backups
└── INSTRUCCIONES_BACKUPS_PARA_OTRA_IA.md  # Este documento
```

---

## 🎓 Resumen ejecutivo

**Si tuvieras que hacer un backup completo en menos de 1 minuto**:

1. Conectarse al SSH
2. Ejecutar:
   ```bash
   curl -sL https://raw.githubusercontent.com/lamegawi/bots-backup/<COMMIT>/scripts_despliegue/backup_completo.py -o /root/backup_completo.py
   python3 -u /root/backup_completo.py
   ```
3. Esperar a que termine
4. Verificar en `diag-public` o en `backups_completos/` que los archivos están subidos

**Si tuvieras que restaurar un JSON**:

1. Ir a https://github.com/lamegawi/bots-backup
2. Buscar la carpeta `backups_completos/<fecha>/`
3. Descargar el JSON deseado
4. En Hetzner: `cp backup.json /opt/polymarket/bot-X/real.json`
5. Reiniciar: `systemctl restart poly-X`

---

## 🔗 Enlaces útiles

- **Repositorio**: https://github.com/lamegawi/bots-backup
- **Rama de trabajo**: `arena/01a058fe-bots-backup`
- **Documentación Polymarket**: https://docs.polymarket.com
- **Tags de backup**: ver lista en la sección "Tags de backup (referencia histórica)"

---

## 📋 Checklist de "qué hacer cuando el usuario pide un backup"

- [ ] Confirmar que el script `backup_completo.py` está en el último commit
- [ ] Dar el hash del commit al usuario en formato `📌 Commit: xxxxxxx`
- [ ] Dar el comando SSH en la Parte 1
- [ ] Dar el comando de descarga y ejecución en la Parte 2
- [ ] NO incluir la contraseña
- [ ] Esperar a que el usuario diga "hecho"
- [ ] Leer el resultado en `diag-public` o en `backups_completos/`
- [ ] Confirmar al usuario que se hizo correctamente
- [ ] Si falla, diagnosticar y proponer solución

---

**Fin del documento.**
