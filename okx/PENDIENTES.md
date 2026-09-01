# Tareas pendientes para mañana

## Bot de bolsa

- [ ] Instalar en `bot-vm4` la última versión de `okx/bolsa_bot.py` desde la rama `arena/01a0587c-bots-backup`.
- [ ] Comprobar que `bolsa-bot.service` queda en estado `active (running)`.
- [ ] Probar en Telegram los botones:
  - [ ] `📊 Precios`: acciones agrupadas por mercado, precio y porcentaje sin enlaces comerciales.
  - [ ] `👀 Seguimiento`: ticker, nombre, precio, mercado y estado abierto/cerrado.
  - [ ] `💰 Saldo`: posiciones agrupadas por mercado, estado, variación diaria y P/L.
  - [ ] `✏️ Modificar`: columnas de seguimiento y cartera correctamente alineadas.
  - [ ] `🔔 Alertas`: añadir, elegir tipo de alerta, cancelar y quitar alertas guardadas.
- [ ] Confirmar que `ACX` aparece como `Acerinox` y no como `AG` o `bet-at-home.com`.
- [ ] Confirmar que `SAN.MC` no se convierte en un enlace automático dentro del saldo.
- [ ] Ejecutar el backup de OKX después de validar la instalación:

```bash
bash /root/backup_okx.sh
```

- [ ] Confirmar que el backup devuelve `OK: backup OKX subido a GitHub`.
- [ ] Revisar que no se han subido tokens, contraseñas ni claves API.

## Nota

La incidencia de Hetzner afecta a Object Storage en NBG. El backup de OKX confirmado utiliza el repositorio local y GitHub, pero conviene verificar mañana que los scripts no dependen de ningún bucket de Object Storage.
