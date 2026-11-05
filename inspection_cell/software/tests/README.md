# Pruebas de software previstas

No hay pruebas implementadas de una celda todavía inexistente. Al desarrollar, cubrir comportamientos con simuladores y muestras identificadas:

- Lectura, unidades y errores del protocolo real de báscula.
- Presencia estable, retirada, recolocación y una inspección por evento.
- Captura/resultado coherentes cuando falla cámara, almacenamiento o comunicación.
- Identidad y reintentos sin duplicar inspecciones ni asociarlas a otro ciclo.
- Reinspección y conflicto con corrección manual.
- Geometrías de longitud/ancho conocidos, curvas, extremos y ramas de colada.
- Rechazo explícito de imágenes recortadas, ocluidas o no medibles.

Una prueba con geometría ideal no sustituye la validación metrológica sobre piezas y referencias físicas. Los protocolos están en [validation](../../validation/README.md).
