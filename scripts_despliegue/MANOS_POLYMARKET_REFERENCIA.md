# MANOS POLYMARKET - Proxy de salida

## Qué es

Un proxy HTTP/HTTPS que corre en **tu PC Windows** y hace que las
operaciones de Polymarket salgan con la **IP de tu PC** (no la de Hetzner).

**Archivo**: `poly/codigo/proxy_pc.py`
**Puerto**: 8888 (por defecto)
**Host**: 0.0.0.0 (escucha en Tailscale también)

## Por qué

Polymarket rechaza operaciones cuya IP no está autorizada.
Los bots corren en Hetzner, pero las órdenes se enrutan a través
de TU PC para que Polymarket vea tu IP y las acepte.

## Cómo ejecutarlo en tu PC Windows

### Opción 1: comando directo

```cmd
cd path\al\repo\bots-backup\poly\codigo
python proxy_pc.py
```

Verás:
```
✅ Proxy escuchando en 0.0.0.0:8888
   Las conexiones saldrán con la IP de ESTE PC.
   Mantén esta ventana abierta. Ctrl+C para salir.
```

### Opción 2: con puerto personalizado

```cmd
python proxy_pc.py 9000
```

## Requisitos

1. **Tailscale activo** en tu PC
2. **PC siempre encendido** (no suspender)
3. **Ventana del proxy abierta** todo el tiempo
4. **Hetzner** configurado para usar este proxy

## Qué pasa si se cae

| Acción | Resultado |
|---|---|
| Cerrar ventana proxy | Órdenes fallan (timeout) |
| Suspender PC | Órdenes fallan |
| Apagar PC | Órdenes fallan |
| Lock (Win+L) | OK, sigue corriendo |
| Reiniciar Tailscale | Pierde conexión |

## Cómo se usa desde Hetzner

El bot (en Hetzner) está configurado para enviar las órdenes a
través de este proxy. La IP que Polymarket ve es la de tu PC.

## Verificación

Para ver si el proxy está vivo:
1. La ventana muestra "Proxy escuchando en 0.0.0.0:8888"
2. Hetzner puede hacer peticiones a tu IP de Tailscale:8888

## Si Polymarket rechaza una orden

1. ¿El proxy está corriendo en tu PC? → Reiniciar
2. ¿Tailscale está activo? → Reactivar
3. ¿Tu PC está suspendido? → Despertar
4. ¿La IP ha cambiado? → Verificar en Polymarket que la IP actual es la autorizada
