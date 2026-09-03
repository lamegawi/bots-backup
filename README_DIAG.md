# Rama diag-public

Esta rama se usa para subir resultados del script de diagnóstico
`scripts_despliegue/diag_y_publica.sh`.

Cada ejecución crea un archivo en `diag_hetzner/diag_FECHA_HORA.txt` y
actualiza `diag_hetzner/latest.txt`.

La IA lee estos archivos directamente desde aquí sin que tengas que
pegar nada en el chat.
