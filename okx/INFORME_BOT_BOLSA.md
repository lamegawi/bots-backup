# Informe del bot de bolsa

**Fecha:** 2026-09-01  
**Servicio:** `bolsa-bot.service`  
**Servidor:** `bot-vm4` (`49.13.84.168`)  
**Programa:** `/root/bolsa_bot.py`  
**Repositorio de respaldo:** `lamegawi/bots-backup`, carpeta `okx/`

## 1. Situación y objetivo

Bot informativo de acciones para Telegram. Consulta cotizaciones de Yahoo Finance sin clave de mercado, muestra la cartera y la lista de seguimiento, calcula variaciones y envía alertas de precio.

El bot **no ejecuta compras ni ventas**. Las entradas y los stop loss que muestra el análisis son orientativos y no constituyen asesoramiento financiero ni órdenes automáticas.

## 2. Menú actual

- `📊 Precios`
- `🔔 Alertas`
- `💰 Saldo`
- `➕ Añadir`
- `✏️ Modificar`
- `➖ Quitar`
- `👀 Seguimiento`
- `🆘 Ayuda`

## 3. Precios en vivo

El botón `📊 Precios` consulta la cotización actual de cada valor de seguimiento y muestra:

- Ticker.
- Nombre de la acción.
- Precio actual.
- Variación porcentual frente al cierre anterior.
- Mercado correspondiente.
- Estado del mercado en el momento de la petición: `ABIERTO` o `CERRADO`.

Los valores se agrupan y ordenan por mercado. Mercados reconocidos:

- Madrid: sufijo `.MC`, 09:00–17:30, hora de Madrid.
- Frankfurt: sufijos `.F` y `.DE`, 09:00–17:30, hora de Berlín.
- Londres: sufijo `.L`, 08:00–16:30, hora de Londres.
- París: sufijo `.PA`, 09:00–17:30, hora de París.
- Nueva York: resto de símbolos, 09:30–16:00, hora de Nueva York.

Se consideran los días laborables de lunes a viernes. No se consulta todavía un calendario de festivos bursátiles; en un festivo el horario puede indicar abierto aunque el mercado esté cerrado.

Los nombres comerciales que parecen dominios se limpian para evitar enlaces automáticos no deseados. `ACX` se presenta como `Acerinox`.

## 4. Seguimiento

`👀 Seguimiento` muestra cada valor guardado con:

- Ticker.
- Nombre de la acción.
- Precio en vivo.
- Mercado.
- Estado abierto/cerrado.

Cada valor tiene un botón `🤖 Análisis IA`. El análisis técnico orientativo incluye:

- Tendencia alcista, bajista o mixta.
- SMA20 y SMA50.
- Soporte de las últimas 60 sesiones.
- Resistencia de las últimas 60 sesiones.
- ATR aproximado.
- Posible entrada por pullback, ruptura, rechazo o pérdida de soporte.
- Stop loss calculado de forma orientativa a partir del ATR.

Los datos históricos se obtienen de Yahoo Finance. Si Yahoo no devuelve histórico, el bot informa de que no puede calcular los indicadores en ese momento.

## 5. Saldo de cartera

`💰 Saldo` muestra las posiciones compradas agrupadas por mercado y ordenadas por ticker dentro de cada grupo.

Para cada acción muestra:

- Ticker y nombre limpio.
- Mercado y estado abierto/cerrado.
- Cantidad.
- Precio medio de compra.
- Precio actual.
- Valor actual de la posición.
- Variación monetaria del día y porcentaje diario.
- Pérdida o ganancia total de la posición y porcentaje desde la compra.

También muestra los totales:

- Total invertido.
- Valor actual.
- P/L total.

Los círculos visuales son:

- `🟢`: resultado positivo.
- `🔴`: resultado negativo.
- `⚪`: sin variación o sin datos.

## 6. Alertas

Se conserva la alerta diaria global basada en el umbral configurado, actualmente `±3%`.

Además, `🔔 Alertas` tiene este flujo:

```text
ALERTAS
├── AÑADIR
│   ├── Elegir acción guardada
│   ├── Si sube de X
│   ├── Si llega a X
│   ├── Si baja de X
│   └── Cancelar
├── QUITAR
│   ├── Elegir acción con alertas guardadas
│   ├── Elegir la alerta concreta que se quiere borrar
│   └── Cancelar
└── CANCELAR
```

Las acciones disponibles para alertas son la unión de:

- Valores de seguimiento.
- Valores de la cartera.

Las alertas personalizadas se comprueban aproximadamente cada cinco minutos. Al cumplirse, se envía un aviso de Telegram y quedan desactivadas para evitar notificaciones duplicadas. Para volver a vigilar el mismo nivel hay que crear una nueva alerta.

El estado se guarda en `bolsa_alertas.json`. El formato conserva las alertas diarias antiguas y añade la colección `personalizadas`.

## 7. Añadir, modificar y quitar

### Añadir

`➕ Añadir` permite guardar una acción como:

- Comprada: ticker, cantidad y precio de compra.
- Seguimiento: solo ticker y cotización.

Al añadir una compra, si ya existe la posición se acumula la cantidad y se recalcula correctamente el precio medio ponderado. Las compras se incorporan también a la lista de seguimiento si no estaban presentes.

### Modificar

`✏️ Modificar` presenta las acciones en dos columnas diferenciadas:

- `👀 Seguimiento`.
- `💼 Cartera`.

La columna de cartera tiene botones para modificar el precio de compra, la cantidad o ambos. La lista incluye los nombres de las acciones y utiliza formato monoespaciado para mantener la alineación.

### Quitar

`➖ Quitar` permite quitar una posición de cartera o un valor de seguimiento.

## 8. Ficheros de datos

En el servidor se utilizan estas rutas:

```text
/root/bolsa_bot.py
/root/bolsa_config.json
/root/bolsa_cartera.json
/root/bolsa_alertas.json
```

En el repositorio de backup:

```text
okx/bolsa_bot.py
okx/bolsa_config.json
okx/bolsa_cartera.json
okx/bolsa_alertas.json
okx/INFORME_BOT_BOLSA.md
```

Los ficheros de configuración y cartera pueden contener información financiera personal. El repositorio de backup debe mantenerse privado. Nunca deben subirse tokens de Telegram, claves API ni contraseñas.

## 9. Operación y comprobaciones

- El servicio se ejecuta como `bolsa-bot.service`.
- Consulta alertas aproximadamente cada 300 segundos.
- Envía resúmenes automáticos a las 09:00 y 21:00, hora de Madrid.
- Solo procesa mensajes del `CHAT_ID` configurado.
- Las credenciales se leen de variables de entorno (`BOLSA_BOT_TOKEN` y `TELEGRAM_CHAT_ID`).
- El código debe validarse antes de reiniciar:

```bash
python3 -m py_compile /root/bolsa_bot.py
systemctl restart bolsa-bot
systemctl status bolsa-bot --no-pager
```

## 10. Backups

El servidor dispone del backup de OKX que se ejecuta con:

```bash
bash /root/backup_okx.sh
```

La ejecución confirmada más reciente devolvió:

```text
Current branch main is up to date.
OK: backup OKX subido a GitHub.
```

La copia anterior del bot debe conservarse antes de cada instalación, por ejemplo:

```bash
cp /root/bolsa_bot.py /root/bolsa_bot.py.bak_YYYYMMDD_HHMM
```

El repositorio contiene además una copia versionada del código y de los datos de bolsa. Antes de instalar una versión nueva conviene verificar sintaxis, reiniciar el servicio y confirmar que permanece `active (running)`.

## 11. Estado de esta entrega

- Código del bot versionado en la rama `arena/01a0587c-bots-backup`.
- Informe añadido al repositorio.
- Cambios comprobados con `py_compile`.
- No se incluyen credenciales.
- La instalación en Hetzner debe hacerse desde la consola del servidor si el acceso SSH permanece bloqueado.
