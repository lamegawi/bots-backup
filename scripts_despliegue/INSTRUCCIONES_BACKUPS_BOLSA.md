# Backups del bot de bolsa

Este procedimiento es exclusivo para `bot-vm4` y los archivos del bot de bolsa. No utiliza ni toca los JSON de Polymarket.

## Qué respalda

- `/root/bolsa_bot.py`
- `/root/bolsa_config.json`
- `/root/bolsa_cartera.json`
- `/root/bolsa_alertas.json`

El script hace dos copias:

1. Copia local en `/root/backup_bolsa_local/YYYY-MM-DD_YYYYMMDD_HHMMSS/`.
2. Copia en GitHub bajo `backups_bolsa_completos/YYYY-MM-DD_YYYYMMDD_HHMMSS/`.

También sube un informe con servidor, estado de `bolsa-bot.service`, rama y SHA. El PAT nunca se incluye en los archivos.

## Ejecutar desde Hetzner

Primera línea independiente:

```bash
ssh root@49.13.84.168
```

Una vez dentro del servidor:

```bash
curl -sL https://raw.githubusercontent.com/lamegawi/bots-backup/<COMMIT>/scripts_despliegue/backup_bolsa_completo.py -o /root/backup_bolsa_completo.py
python3 -m py_compile /root/backup_bolsa_completo.py
python3 -u /root/backup_bolsa_completo.py
```

El PAT debe estar únicamente en `/root/diag_token.txt`, `/root/.gist_token` o disponible mediante `GH_PAT`, siempre con permisos `600`. No se debe pegar en la terminal ni en el chat.

## Resultado esperado

```text
BACKUP_BOLSA_LOCAL=/root/backup_bolsa_local/...
BACKUP_BOLSA_GITHUB=backups_bolsa_completos/...
SUBIDOS=5
AUSENTES=0
OK: backup completo del bot de bolsa subido a GitHub
```

## Restauración

No restaurar ningún archivo automáticamente. Primero seleccionar una carpeta fechada en `backups_bolsa_completos/`, verificar el informe y conservar una copia local de los archivos actuales antes de sustituirlos.
