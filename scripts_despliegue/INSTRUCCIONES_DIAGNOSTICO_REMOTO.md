# MANUAL DE DIAGNÓSTICO REMOTO — HETZNER → GITHUB → ARENA.AI
==================================================================

**Fecha**: 2026-09-03
**Autor**: lamegawi (con ayuda del agente de Arena.ai)
**Para**: bots de Polymarket desplegados en Hetzner (46.225.146.21, root, pwd 4856)
**Objetivo**: ejecutar diagnósticos en Hetzner, publicarlos automáticamente en GitHub, y que el agente de Arena.ai los lea directamente sin que tú pegues nada.


## RESUMEN EJECUTIVO
-------------------

Cuando trabajas con un agente de IA (como Arena.ai en modo "Agent Mode") sobre un servidor remoto (Hetzner), el agente **NO tiene acceso SSH** a tu servidor. Solo puede:
- Acceder a GitHub (vía `gh api`)
- Leer/escribir archivos en el repo donde trabajas
- Ejecutar comandos en su propio sandbox (que NO llega a `data-api.polymarket.com` ni a `raw.githubusercontent.com`)

Por tanto, **el flujo es**:
1. El agente escribe un script y lo sube a GitHub
2. Tú lo descargas en Hetzner y lo ejecutas
3. El script **publica automáticamente el resultado** en una rama especial de GitHub (`diag-public`)
4. El agente lee el resultado directamente desde GitHub

**Tú no tienes que pegar NADA en el chat. Solo ejecutar un comando y decir "hecho".**


## EL FLUJO COMPLETO, PASO A PASO
---------------------------------

### PASO 1: Crear un Personal Access Token (PAT) en GitHub

1. Ve a https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. **Note**: pon un nombre descriptivo, p.ej. `bots-backup diag hetzner`
4. **Expiration**: 90 días (o lo que prefieras)
5. **Scopes**: marca **SOLO** `repo` (acceso completo al repositorio)
6. Click "Generate token"
7. **COPIA EL TOKEN** (empieza por `ghp_...`). GitHub solo lo muestra UNA VEZ.

**IMPORTANTE**: nunca pegues este token en el chat con el agente. Solo úsalo en comandos SSH directos.


### PASO 2: Subir el PAT a Hetzner de forma segura

Conéctate por SSH desde PowerShell a tu servidor:
```
ssh root@46.225.146.21
```

Crea el archivo con el token (reemplaza `ghp_TU_TOKEN` con tu token real):
```
echo "ghp_TU_TOKEN" > /root/diag_token.txt
chmod 600 /root/diag_token.txt
```

Verifica:
```
ls -la /root/diag_token.txt
cat /root/diag_token.txt
```

Debe mostrar algo como:
```
-rw------- 1 root root 41 Sep  3 18:00 /root/diag_token.txt
ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**⚠️ NUNCA pegues el contenido en el chat. Solo verifica que el archivo existe.**


### PASO 3: El agente escribe el script de diagnóstico

El agente (yo) genera un script Python que:
1. Lee el saldo real on-chain de tu wallet de Polymarket
2. Analiza todas tus posiciones en Polymarket (vía data-api)
3. Clasifica las posiciones en: positivas (en profit), grandes (no tocar), dust (irrecuperables)
4. Sube un informe de texto a la rama `diag-public` del repo

El script usa **GitHub Contents API** (PUT a `https://api.github.com/repos/.../contents/...`) en lugar de `git push`, porque es más robusto y no requiere credenciales SSH de GitHub.

El script se sube a la rama `arena/01a058fe-bots-backup` del repo `lamegawi/bots-backup`, en la carpeta `scripts_despliegue/`.


### PASO 4: Tú ejecutas el script en Hetzner

El agente te pasa un comando (o varios). Tú solo tienes que:

**Descargar el script**:
```
curl -sL https://raw.githubusercontent.com/lamegawi/bots-backup/arena/01a058fe-bots-backup/scripts_despliegue/diag_v4.py -o /root/diag_v4.py
```

**Ejecutarlo** (con `tee` para guardar el log localmente, por si acaso):
```
python3 /root/diag_v4.py 2>&1 | tee /root/diag_v4.log
```

**Esperar 30-60 segundos** (para que GitHub propague el cambio).

**Decirle al agente "hecho"** en el chat.

**NO tienes que pegar nada**. El agente irá a GitHub a leer el informe.


### PASO 5: El agente lee el resultado

El agente ejecuta (en su sandbox):
```
gh api "repos/lamegawi/bots-backup/contents/diag_hetzner?ref=diag-public" --jq '.[] | .name'
```

Y luego lee el último archivo `diag_*.txt` con:
```
gh api "repos/lamegawi/bots-backup/contents/diag_hetzner/diag_YYYYMMDD_HHMMSS.txt?ref=diag-public" -H "Accept: application/vnd.github.v3.raw"
```

Eso es todo. El agente tiene el informe completo, lo analiza, y te responde con conclusiones + siguientes pasos.


## LOS SCRIPTS QUE HEMOS CREADO
--------------------------------

Todos están en `scripts_despliegue/` de la rama `arena/01a058fe-bots-backup`:

| Archivo | Qué hace |
|---|---|
| `diag_v4.py` | **EL PRINCIPAL**. Lee saldo, analiza posiciones, publica. |
| `limpiar_dust.py` | Vende posiciones de dust (irrecuperable en tu caso, no usar). |
| `consultar_saldo_real.py` | Solo lee el saldo on-chain. |
| `verifica_pat.py` | Diagnostica si el PAT está vivo. Útil cuando falla el PUT. |
| `test_red.py` | Comprueba conectividad Hetzner→GitHub. Útil para depurar. |
| `diag_via_ssh.sh` | Versión bash (con git push) que probamos primero. NO recomendada. |
| `diagnostico_pnl.sh` | Versión inicial bash. Superseded. |
| `INSTRUCCIONES.txt`, `INSTRUCCIONES_SSH.md` | Instrucciones previas. |


## EL SCRIPT diag_v4.py — EXPLICACIÓN DETALLADA
------------------------------------------------

Hace 3 cosas en una sola ejecución:

### 1) SALDO REAL ON-CHAIN
Lee el saldo de tu wallet de Polymarket. La fuente de verdad es el contrato de Polymarket (pUSD/USDC/USDC.e en Polygon), no el CLOB.

Para encontrar tu wallet:
- Lee `wallet_address` de `config.json` de cada bot
- Si no está, lo deriva de `wallet_private_key` usando `eth_account`
- Si no está, busca variable de entorno `WALLET_ADDRESS`

Para consultar el saldo:
- Importa `operar_real` del bot de Elon
- Llama a `saldo_usdc_onchain(wallet, "polygon")`
- Esto lee directamente de la blockchain de Polygon (vía JSON-RPC)

**FALLO CONOCIDO**: si el `config.json` no tiene `wallet_address` ni `wallet_private_key` (o están vacíos), el script no puede encontrar la wallet. En ese caso hay que añadir el wallet manualmente al `config.json` o derivarlo de la private key.

### 2) ANÁLISIS DE POSICIONES
Llama a `https://data-api.polymarket.com/positions?user=TU_WALLET&limit=200` y parsea el JSON.

Clasifica cada posición en:
- **Positiva** (cur > 0.01 y pnl > 0): está en profit, vendible
- **Grande** (size > 100): tiene muchas shares, NO se toca (podría tener valor real)
- **Dust** (resto): posiciones pequeñas, intentar vender si tienen valor

Calcula totales: valor actual, invertido, PnL no realizado.

### 3) PUBLICACIÓN EN GITHUB
Sube el informe a `diag-public` (rama pública del repo).

Usa **GitHub Contents API**:
```
PUT https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/diag_YYYYMMDD_HHMMSS.txt
Authorization: token ghp_...
Body: {"message": "...", "content": "<base64>", "branch": "diag-public"}
```

Si el archivo ya existe, primero hace GET para obtener su `sha` y lo incluye en el PUT para sobrescribir.

**FALLO CONOCIDO**: si el PAT está revocado, expirado, o no tiene scope `repo`, el PUT devuelve 401 "Bad credentials". Solución: crear un PAT nuevo.


## PROBLEMAS QUE ENCONTRAMOS Y CÓMO LOS RESOLVIMOS
----------------------------------------------------

### Problema 1: "La terminal de Hetzner (web console) no funciona bien"
**Síntoma**: caracteres como `|`, `grep`, `--`, `@`, `:`, `_` se introducen mal o se pierden.
**Causa**: bug del navegador con el terminal JavaScript embebido.
**Solución**: usar **SSH desde Windows PowerShell** con `ssh root@46.225.146.21`. Funciona perfecto.

### Problema 2: "El agente no puede acceder a data-api.polymarket.com"
**Síntoma**: `curl https://data-api.polymarket.com/...` desde el sandbox da timeout.
**Causa**: el sandbox del agente solo tiene acceso a `api.github.com` (vía `gh`), no a otros dominios.
**Solución**: hacer las llamadas desde Hetzner (que sí tiene acceso a internet completo) y publicar el resultado en GitHub.

### Problema 3: "git push desde Hetzner pide contraseña"
**Síntoma**: al hacer `git push`, GitHub pide usuario y contraseña (que ya no funciona con PAT, ahora pide token).
**Causa**: el PAT no está bien configurado en el remote URL o en el credential helper.
**Solución**: usar **GitHub Contents API** (PUT via `urllib.request`) en lugar de `git push`. No necesita credenciales SSH, solo el PAT en el header.

### Problema 4: "El script dice que publicó pero no aparece nada en GitHub"
**Síntoma**: el script imprime "✓ Publicado: ..." pero `gh api` no ve el archivo.
**Causas posibles**:
- El check de éxito era muy laxo (buscaba `"content"` en el response, pero los errores también lo contienen)
- Eventual consistency de GitHub (raro, suele ser instantáneo)
- **EL PAT ESTÁ REVOCADO** ← esta fue la causa en nuestro caso

**Solución**:
1. Verificar el PAT con `verifica_pat.py` (hace GET + PUT de prueba)
2. Si da 401 "Bad credentials", el PAT está muerto. Crear uno nuevo.

### Problema 5: "PowerShell SSH corta la salida de comandos largos"
**Síntoma**: cuando un script imprime mucho, aparecen líneas truncadas, "Yes" repetidos (autocompletado), etc.
**Causa**: PowerShell interpreta ciertos caracteres y aplica autocompletado.
**Solución**: **redirigir la salida a un archivo** (`> /root/diag.log 2>&1`) y luego `cat` el archivo. O usar el flag `--no-pager` si es un comando git. Pero lo MEJOR es no pegar nada: dejar que el script publique a GitHub y que el agente lo lea de ahí.

### Problema 6: "El saldo on-chain no se puede leer"
**Síntoma**: el script dice "no se pudo encontrar wallet en ningún sitio".
**Causa**: los `config.json` de los bots no tienen `wallet_address` (solo `wallet_private_key`).
**Solución** (pendiente):
- Opción A: añadir `wallet_address` a cada `config.json` (se puede derivar de la private key)
- Opción B: el script lee la private key y deriva la dirección con `eth_account.Account.from_key(pk)`
- Opción C: usar Polygon JSON-RPC directamente (sin pasar por los bots)


## PROCEDIMIENTO ESTÁNDAR PARA OTROS CHATS
--------------------------------------------

Si abres un nuevo chat con el agente de Arena.ai para seguir trabajando en este proyecto, sigue estos pasos:

### Para el usuario (tú):
1. Conecta por SSH: `ssh root@46.225.146.21`
2. Verifica que el PAT sigue vivo: `python3 /root/verifica_pat.py`
3. Si da 401, crea un PAT nuevo y actualiza `/root/diag_token.txt`
4. Dile al agente en el chat: "el PAT está listo, ejecuta el diagnóstico"
5. El agente te dirá qué script descargar y ejecutar
6. Tú lo ejecutas, dices "hecho", y el agente lee el resultado

### Para el agente (en cada nuevo chat):
1. Recordar (o pedir al usuario) que el proyecto es `lamegawi/bots-backup`
2. La rama de trabajo es `arena/01a058fe-bots-backup`
3. La rama de diagnóstico es `diag-public`
4. El servidor Hetzner es `46.225.146.21` (root, pwd 4856)
5. El PAT está en `/root/diag_token.txt` (no leerlo nunca, solo verificar que existe)
6. Los scripts están en `scripts_despliegue/` del repo
7. El último informe está en `diag-public/diag_hetzner/diag_*.txt`

**Comandos clave del agente**:
```bash
# Leer el último informe
gh api "repos/lamegawi/bots-backup/contents/diag_hetzner?ref=diag-public" --jq '.[] | .name' | sort

# Leer un informe específico
gh api "repos/lamegawi/bots-backup/contents/diag_hetzner/diag_YYYYMMDD_HHMMSS.txt?ref=diag-public" -H "Accept: application/vnd.github.v3.raw"

# Subir un script nuevo
git add scripts_despliegue/mi_script.py
git -c user.email="lamegawi@users.noreply.github.com" -c user.name="lamegawi" commit -m "..."
git push origin arena/01a058fe-bots-backup
```


## CHECKLIST DE SEGURIDAD
-------------------------

- [ ] El PAT en `/root/diag_token.txt` tiene SOLO scope `repo` (no `admin`, no `delete_repo`)
- [ ] El archivo tiene permisos `600` (solo root puede leerlo)
- [ ] Cada 90 días (o cuando expire), revocar el PAT viejo y crear uno nuevo
- [ ] **NUNCA** pegar el PAT en el chat con el agente
- [ ] **NUNCA** subir el PAT a un archivo del repo (ni siquiera en privado). Si se sube accidentalmente, revocarlo INMEDIATAMENTE
- [ ] El PAT que se subió a `diag-public/assets/diag_token.txt` (con el bootstrap) **YA ESTÁ REVOCADO** (verificar). Si no, revocarlo ahora
- [ ] Cambiar la contraseña de root de Hetzner si la has compartido con alguien más


## COMANDOS ÚTILES DE DIAGNÓSTICO
----------------------------------

### Ver qué bots están corriendo
```bash
systemctl list-units --type=service --state=active | grep poly
```

### Ver logs de un bot
```bash
journalctl -u poly-elon -n 50 --no-pager
```

### Ver el balance real (si wallet está en config)
```bash
python3 -c "
import sys
sys.path.insert(0, '/opt/polymarket/bot-polymarket-elon')
import operar_real
print(operar_real.saldo_usdc_onchain('0xb0E1197098E6d427c01720F1631cAD24CE740FA0', 'polygon'))
"
```

### Ver las posiciones sin publicar
```bash
curl -s "https://data-api.polymarket.com/positions?user=0xb0E1197098E6d427c01720F1631cAD24CE740FA0&limit=200" -H "User-Agent: Mozilla/5.0" | python3 -m json.tool | head -100
```

### Ver el contenido de real.json (PnL virtual de un bot)
```bash
cat /opt/polymarket/bot-polymarket-elon/real.json
```

### Ver el contenido de cierres_anticipados.json (PnL real del gestor)
```bash
cat /opt/polymarket/cierres_anticipados.json
```


## FLUJO DE TRABAJO RECOMENDADO PARA EL AGENTE
-----------------------------------------------

1. **Al iniciar**: leer este manual (o que el usuario lo referencie)
2. **Verificar el estado del repo**:
   - `git log --oneline -5` en la rama `arena/01a058fe-bots-backup`
   - `gh api repos/lamegawi/bots-backup/branches --jq '.[].name'`
3. **Verificar si hay un diag reciente**:
   - `gh api "repos/lamegawi/bots-backup/contents/diag_hetzner?ref=diag-public"`
   - Si el último es de hace menos de 1 hora, leerlo directamente
4. **Si necesita datos nuevos**:
   - Modificar o crear el script en `scripts_despliegue/`
   - Commit + push a `arena/01a058fe-bots-backup`
   - Pedir al usuario que lo ejecute
5. **Después de la ejecución**:
   - Esperar 30-60 segundos
   - Leer el último archivo `diag_*.txt` con `gh api`
6. **Analizar y responder**:
   - Comparar con el `real.json` de cada bot (PnL virtual)
   - Comparar con `cierres_anticipados.json` (PnL real del gestor)
   - Dar conclusiones accionables


## GLOSARIO
----------

- **CLOB**: Central Limit Order Book. El sistema de matching de Polymarket.
- **pUSD**: Token colateral de Polymarket (pegged a USD).
- **USDC.e**: USDC "bridged" de Ethereum a Polygon.
- **Dust**: Posiciones con valor muy pequeño (típicamente <$1) que no se pueden vender o no merece la pena por las comisiones.
- **PnL no realizado**: pérdida o ganancia de posiciones abiertas (que aún no se han cerrado).
- **PnL virtual**: el que calculan los bots en `real.json` (puede no coincidir con el real por bugs).
- **Bankroll**: capital total disponible para operar.
- **Stake**: cantidad apostada en una operación.
- **Cuota**: precio de la share en el CLOB (entre 0.01 y 0.99).
- **Funder**: dirección del wallet que deposita fondos en Polymarket (proxy address).


## NOTAS FINALES
----------------

- Todo este flujo se ha desarrollado el 2026-09-03 entre las 16:00 y las 18:30 (aprox).
- El proyecto principal es `lamegawi/bots-backup`, 5 bots: elon, elon-semanal, elon-mensual, zelenskyy, trump.
- El bot de Trump aún no está desplegado en Hetzner (estaba pendiente al inicio de la sesión).
- El bankroll inicial era $500, ahora está en ~$450 (estimación, falta confirmar saldo real on-chain).
- El PnL no realizado de las 74 posiciones es **-$550**, lo cual sugiere que la pérdida total es mayor de lo que el usuario pensaba.
- El siguiente paso lógico es desplegar el bot de Trump (para tener un bot nuevo con bankroll fresco) y resolver el problema del saldo on-chain.

---
**FIN DEL MANUAL**
