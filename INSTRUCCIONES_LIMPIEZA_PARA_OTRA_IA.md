# INSTRUCCIONES PARA OTRA IA: CÓMO HACER LIMPIEZA DE DATOS Y ARCHIVOS

> Documento de referencia. Compártelo con cualquier otra IA que vaya a gestionar
> los bots de Polymarket, para que sepa cómo hacer limpieza correctamente.

---

## 🎯 Contexto

Trabajas con 3 bots de Polymarket en un servidor Hetzner (46.225.146.21). El código está en GitHub (rama `arena/01a058fe-bots-backup`) y los scripts de diagnóstico están en `scripts_despliegue/`.

Con el tiempo se acumulan archivos obsoletos, versiones viejas de scripts, archivos de prueba, logs antiguos, etc. El usuario puede pedir **"haz limpieza"** en cualquier momento.

---

## 🧹 Qué se considera "limpieza"

### 1. Scripts obsoletos (versiones v1, v2 reemplazadas por v3)

Cuando se mejora un script, las versiones anteriores se eliminan.

**Patrón típico**:

- `script_v1.py` → reemplazado por `script_v2.py` o `script_v3.py`
- `script_v1.py` (sin sufijo) → reemplazado por `script_v2.py`
- Scripts únicos sin uso (que solo se usaron una vez y ya no)

**Cómo eliminarlos**:

```bash
# Localmente
git rm scripts_despliegue/script_obsoleto.py
git commit -m "Limpieza: eliminar scripts obsoletos v1 y v2"
git push origin arena/01a058fe-bots-backup
```

### 2. Archivos de logs y temporales

- Archivos `.log` antiguos
- Archivos `.tmp` o `.bak` duplicados
- Salidas de pruebas

**Cómo eliminarlos** (en Hetzner):

```bash
# Ver logs grandes
ls -la /root/*.log 2>&1
du -sh /root/*.log 2>&1

# Eliminar logs antiguos (más de 30 días)
find /root -name "*.log" -mtime +30 -delete
```

### 3. Archivos untracked en el repositorio

A veces quedan archivos que nunca se commitearon.

**Cómo verlos**:

```bash
git status
```

**Cómo eliminarlos** (si no se necesitan):

```bash
# Ver qué hay
git clean -n  # dry-run
# Si todo OK
git clean -fd  # elimina archivos y directorios no trackeados
```

### 4. Tags de backup antiguos (opcional)

A veces se acumulan muchos tags. Se pueden eliminar los más viejos si hay muchos.

**Cómo listarlos**:

```bash
git tag -l
```

**Cómo eliminar uno**:

```bash
git tag -d backup-2026-09-01-viejo
git push origin :refs/tags/backup-2026-09-01-viejo
```

**IMPORTANTE**: solo eliminar tags que el usuario confirme que ya no necesita.

---

## 📋 Procedimiento estándar de limpieza

Cuando el usuario dice **"haz limpieza"** o **"limpia los archivos obsoletos"**:

### Paso 1: Identificar qué sobra

Revisar:

- `scripts_despliegue/` buscando versiones v1, v2, v3, etc.
- `git log` para ver commits que añadieron scripts
- `git status` para ver untracked
- `git tag -l` para ver tags acumulados

### Paso 2: Proponer al usuario qué borrar

**SIEMPRE** antes de borrar nada, hacer una lista propuesta:

```
Voy a eliminar:
- saldo_real_total.py (v1, reemplazado por v2)
- sincronizar_saldo_json.py (v1, reemplazado por v3)
- sincronizar_saldo_json_v2.py (v2, reemplazado por v3)
- limpiar_historial_zelen_v2.py (v2, reemplazado por v3)
- verificar_filtros_3bots.py (v1, reemplazado por v2)
- verificar_filtro_elon.py (sin uso)

¿Confirmas?
```

### Paso 3: Esperar confirmación

**NUNCA** borrar sin que el usuario confirme.

### Paso 4: Hacer backup antes de borrar

Antes de cualquier limpieza importante:

```bash
# Backup de tags
git tag -a "backup-2026-09-05-limpio" -m "Backup antes de limpieza"
git push origin "backup-2026-09-05-limpio"

# Si vas a borrar JSONs, haz backup completo primero
python3 /root/backup_completo.py
```

### Paso 5: Eliminar y commitear

```bash
# Eliminar archivos
git rm archivo1.py archivo2.py
git commit -m "Limpieza: eliminar scripts obsoletos v1 y v2"
git push origin arena/01a058fe-bots-backup
```

### Paso 6: Crear tag de backup post-limpieza

```bash
git tag -a "backup-2026-09-05-final" -m "Backup tras limpieza"
git push origin "backup-2026-09-05-final"
```

### Paso 7: Documentar en el README

Actualizar `BACKUP_2026-09-04.md` (o el README correspondiente) con la sección de limpieza:

```markdown
## LIMPIEZA 2026-09-05

### Scripts eliminados (obsoletos)

- `script_v1.py` → reemplazado por `script_v2.py`
- `script_v2.py` → reemplazado por `script_v3.py`

### Scripts vigentes (limpio)

- `script_v3.py` ← el bueno
- `otro_script.py`
- ...
```

---

## ⚠️ Reglas de oro para limpieza

1. **SIEMPRE** confirmar con el usuario antes de borrar
2. **SIEMPRE** hacer backup antes de borrar (tag de git + backup_completo si afecta JSONs)
3. **NUNCA** borrar archivos de configuración (`config.json`, `.env`)
4. **NUNCA** borrar el `proxy_pc.py` (es crítico para que las operaciones funcionen)
5. **NUNCA** borrar la rama principal o tags de backup sin confirmar
6. **SIEMPRE** explicar qué se va a borrar y por qué
7. **SIEMPRE** crear un tag de backup post-limpieza

---

## 🚫 Lo que NUNCA se debe borrar

| Archivo/Directorio | Por qué es crítico |
|---|---|
| `poly/codigo/proxy_pc.py` | El proxy que permite operar con IP del PC |
| `poly/codigo/bot-polymarket-*/senal_vivo.py` | El motor de los bots |
| `poly/codigo/bot-polymarket-*/operar_real*.py` | Lógica de operación real |
| `/etc/polymarket.env` | Credenciales (aunque tiene secretos) |
| `*.bak.YYYYMMDD_HHMMSS` | Backups de JSONs |
| Tags `backup-2026-09-04-*` y posteriores | Backups de referencia |
| `scripts_despliegue/CHEATSHEET.txt` | Referencia rápida |
| `scripts_despliegue/INSTRUCCIONES_*.md` | Documentación |
| `scripts_despliegue/backup_completo.py` | El script de backup |
| `scripts_despliegue/saldo_real_total_v2.py` | Lee el saldo real |
| `scripts_despliegue/sincronizar_saldo_json_v3.py` | Sincroniza saldos |

---

## 📂 Limpiezas típicas que se hacen

### Limpieza 1: Eliminar scripts obsoletos

**Contexto**: hay versiones v1, v2, v3 de un script. La última es la buena.

**Ejemplo real** (5 sept 2026):

Eliminados:

- `saldo_real_total.py` (v1) → reemplazado por `saldo_real_total_v2.py`
- `sincronizar_saldo_json.py` (v1) → reemplazado por `sincronizar_saldo_json_v3.py`
- `sincronizar_saldo_json_v2.py` (v2) → reemplazado por `sincronizar_saldo_json_v3.py`
- `limpiar_historial_zelen_v2.py` (v2) → reemplazado por `limpiar_historial_zelen_v3.py`
- `verificar_filtros_3bots.py` (v1) → reemplazado por `verificar_filtros_3bots_v2.py`
- `verificar_filtro_elon.py` (sin uso)

### Limpieza 2: Eliminar logs antiguos en Hetzner

```bash
# Ver tamaño
du -sh /root/*.log 2>/dev/null

# Ver archivos grandes
find /root -type f -size +1M -exec ls -la {} \;

# Eliminar logs > 30 días
find /root -name "*.log" -mtime +30 -delete

# Limpiar journalctl (logs de systemd)
journalctl --vacuum-time=30d
```

### Limpieza 3: Eliminar archivos untracked

```bash
# Ver qué hay
git status -uall
git clean -n  # dry-run

# Si todo OK
git clean -fd
```

### Limpieza 4: Limpiar el sandbox de trabajo

El sandbox donde trabajo (en `/home/user/bots-backup`) a veces se resetea. Si hay archivos basura:

```bash
# Ver qué hay
ls -la

# Eliminar archivos .pyc (Python cache)
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} \;

# Eliminar archivos .DS_Store (macOS)
find . -name ".DS_Store" -delete
```

---

## 🎯 Comandos útiles para limpieza

### Ver el tamaño del repo

```bash
du -sh /home/user/bots-backup/
du -sh /home/user/bots-backup/poly/
du -sh /home/user/bots-backup/scripts_despliegue/
```

### Ver los archivos más grandes

```bash
find /home/user/bots-backup -type f -size +100k -exec ls -la {} \;
```

### Ver qué hay en cada carpeta

```bash
ls -la /home/user/bots-backup/scripts_despliegue/
ls -la /home/user/bots-backup/poly/codigo/
```

### Contar archivos por tipo

```bash
find /home/user/bots-backup -name "*.py" | wc -l
find /home/user/bots-backup -name "*.md" | wc -l
find /home/user/bots-backup -name "*.json" | wc -l
```

### Ver el historial de cambios de un archivo

```bash
git log --oneline -- scripts_despliegue/script.py
```

### Ver qué archivos se modificaron recientemente

```bash
git log --name-only --since="1 week ago"
```

---

## 📊 Criterios para decidir si un script se puede borrar

| Criterio | ¿Borrar? |
|---|---|
| Es una versión vieja (v1) y existe v2 o v3 | ✅ Sí |
| Es único pero no se usa hace > 1 mes | ⚠️ Confirmar con usuario |
| Es único y se usa frecuentemente | ❌ No |
| Es de pruebas (nombre empieza con `test_`) y ya no se usa | ✅ Sí |
| Es documentación (.md) vigente | ❌ No |
| Es documentación obsoleta | ⚠️ Confirmar con usuario |
| Es un script de una sola vez que ya cumplió su función | ✅ Sí |

---

## 🔄 Flujo de trabajo recomendado

```
Usuario dice "haz limpieza"
        ↓
Reviso scripts_despliegue/ buscando versiones viejas
        ↓
Reviso git status buscando untracked
        ↓
Reviso git tag -l buscando tags duplicados
        ↓
Hago propuesta al usuario con lista de qué borrar
        ↓
Usuario confirma
        ↓
Hago backup (tag + backup_completo si afecta JSONs)
        ↓
Borro archivos con git rm
        ↓
Commit + push
        ↓
Creo tag de backup post-limpieza
        ↓
Actualizo README con la sección de limpieza
        ↓
Commit + push del README
        ↓
Informo al usuario qué se hizo
```

---

## 📝 Ejemplo completo de limpieza

**Usuario dice**: "haz limpieza"

**IA responde**:

```
Voy a hacer limpieza. Primero reviso qué hay:

1) Scripts obsoletos detectados:
   - saldo_real_total.py (v1) → reemplazado por v2
   - sincronizar_saldo_json.py (v1) → reemplazado por v3
   - sincronizar_saldo_json_v2.py (v2) → reemplazado por v3
   - limpiar_historial_zelen_v2.py (v2) → reemplazado por v3
   - verificar_filtros_3bots.py (v1) → reemplazado por v2
   - verificar_filtro_elon.py (sin uso)

2) Tags de backup: 6, todos útiles, ninguno para borrar

3) Archivos untracked: ninguno

¿Confirmas que borre los 6 scripts?
```

**Usuario dice**: "sí"

**IA ejecuta**:

```bash
cd /home/user/bots-backup

# 1) Backup tag pre-limpieza
git tag -a "backup-2026-09-05-pre-limpio" -m "Antes de limpieza"
git push origin "backup-2026-09-05-pre-limpio"

# 2) Eliminar
git rm scripts_despliegue/saldo_real_total.py
git rm scripts_despliegue/sincronizar_saldo_json.py
git rm scripts_despliegue/sincronizar_saldo_json_v2.py
git rm scripts_despliegue/limpiar_historial_zelen_v2.py
git rm scripts_despliegue/verificar_filtros_3bots.py
git rm scripts_despliegue/verificar_filtro_elon.py

# 3) Commit
git commit -m "Limpieza: eliminar scripts obsoletos v1 y v2"

# 4) Push
git push origin arena/01a058fe-bots-backup

# 5) Tag post-limpieza
git tag -a "backup-2026-09-05-limpio" -m "Tras limpieza"
git push origin "backup-2026-09-05-limpio"

# 6) Actualizar README
# (editar BACKUP_2026-09-04.md añadiendo sección de limpieza)

git add BACKUP_2026-09-04.md
git commit -m "BACKUP_2026-09-04: documentar limpieza"
git push origin arena/01a058fe-bots-backup
```

**IA informa**:

```
Limpieza completada:
- 6 scripts eliminados
- 2 tags de backup creados (pre y post)
- README actualizado

Tags vigentes: backup-2026-09-04-filtros-sync, backup-2026-09-04-final,
backup-2026-09-04-proxy-doc, backup-2026-09-05-limpio, backup-2026-09-05-final
```

---

## 🎯 Resumen ejecutivo

**Si tuvieras que hacer limpieza en menos de 1 minuto**:

1. Revisar `scripts_despliegue/` buscando versiones viejas
2. Proponer lista al usuario
3. Esperar confirmación
4. Crear tag de backup
5. `git rm` los archivos
6. Commit + push
7. Crear tag post-limpieza
8. Actualizar README

**Lo que NUNCA se borra**:

- `proxy_pc.py`
- `senal_vivo.py` y `operar_real*.py` de los bots
- Archivos de configuración
- Scripts de backup y monitoreo
- Tags de backup históricos

---

## 🔗 Enlaces útiles

- **Repositorio**: https://github.com/lamegawi/bots-backup
- **Rama de trabajo**: `arena/01a058fe-bots-backup`
- **Documentación relacionada**: `INSTRUCCIONES_BACKUPS_PARA_OTRA_IA.md`

---

## 📋 Checklist de "qué hacer cuando el usuario pide limpieza"

- [ ] Revisar `scripts_despliegue/` buscando versiones obsoletas
- [ ] Revisar `git status` buscando untracked
- [ ] Revisar `git tag -l` buscando tags duplicados
- [ ] Hacer propuesta al usuario con lista de qué borrar
- [ ] Esperar confirmación
- [ ] Crear tag de backup pre-limpieza
- [ ] Si afecta JSONs, ejecutar `backup_completo.py` primero
- [ ] `git rm` los archivos obsoletos
- [ ] Commit + push
- [ ] Crear tag de backup post-limpieza
- [ ] Actualizar README con sección de limpieza
- [ ] Commit + push del README
- [ ] Informar al usuario qué se hizo

---

**Fin del documento.**
