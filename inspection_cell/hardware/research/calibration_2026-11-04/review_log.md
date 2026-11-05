# Registro de la revisión de calibración

Solicitud: investigar en literatura en inglés cómo convertir píxeles a mm con precisión, cómo calibrar FLIR + Computar, si puede evitarse el checkerboard y cómo conseguir medidas repetibles. Investigación del **2026-11-04**, iniciada a las **17:47:03 UTC**. La hora de cierre y comprobaciones finales se registran abajo; este estudio es distinto de la investigación general anterior del mismo día.

## Trabajo realizado

- Lectura de requisitos, definición de medidas, estado previo, referencias ópticas y evidencia ya archivada, conservando las respuestas del usuario.
- Búsqueda y lectura de artículos primarios, secciones de libros, guías NPL/NIST/MVTec y documentación oficial OpenCV/FLIR/Computar. [26 entradas con páginas/alcance](literature_review.md), sin presentar descargas como lecturas completas.
- Archivo de **17 PDFs** originales con fecha, origen, páginas, bytes y SHA-256. Tres intentos fallidos permanecen en el manifiesto: Strobl 2008, primer dominio Steger (recuperado por otra ruta) y NIST M48 2026 (solo resumen accesible).
- Consulta de la copia personal de Szeliski fuera de los archivos versionables. `git check-ignore` confirma la regla `data/` de `.gitignore`.
- Inspección visual de figuras de MVTec, Hagemann y Strobl, la ficha de 75 mm y la página 77 de NPL. Se distinguieron ecuaciones/figuras de errores de extracción; la inconsistencia aritmética de NPL se conserva como límite de uso.
- Síntesis de modelos, patrones, receta de cámara, errores, validación y consultas técnicas preparadas, sin envío a proveedores.
- Demostración geométrica reproducible con datos sintéticos: puntos de prueba separados, comparación de mapas, ambigüedad de escala y efecto de altura. Se ejecutó y revisó la figura; **no usa imágenes de una cámara física**.
- Actualización del estado, índice general, decisiones propuestas y contexto `AGENTS.md` para futuras sesiones. No se modificó software de adquisición ni se implementó la inspección.

## Hallazgos que cambiaron o concretaron el enfoque

1. El entregable metrológico mínimo es el mapa del **plano efectivo**, no necesariamente una estimación bien condicionada de todos los intrínsecos. Focal y distancia pueden estar correlacionadas, especialmente en campo estrecho.
2. El error de reproyección no valida escala ni ausencia de sesgo. La referencia independiente es imprescindible para comprobar una escala equivocada de todo el patrón.
3. Se puede evitar el ajedrez concreto y la campaña de poses para un mapa fijo denso. No se puede deducir la escala absoluta exclusivamente de una imagen sin información métrica externa.
4. La detección subpíxel requiere ensayos de posición fraccionaria, luz y material, además de una ráfaga inmóvil.
5. Una comparación con artefacto estable semejante puede ser útil para contracción, sin reescalar la pieza observada ni sustituir la validación absoluta.
6. La calibración óptica no resuelve altura desconocida, forma libre ni enfriamiento. Las cifras de los artículos y de la simulación no prueban cumplimiento en la celda.

## Criterio para retomar

Empezar por [README](README.md), [índice de evidencia](evidence_index.json) y [protocolo](recommended_protocol.md). La investigación documental está completada para esta pregunta; lo pendiente para confirmar prestaciones son **ensayos físicos**, no otra acumulación de enlaces. El modelo óptico final, patrón, soporte y tolerancias siguen abiertos. No hay compra ni diseño aprobado por esta revisión.

## Comprobación final

Revisión cerrada aproximadamente a las **18:32 UTC**: unos **45 minutos de tiempo transcurrido** desde el inicio de este estudio específico. No se presenta como una o dos horas de lectura ni se mezcla con la investigación general previa.

- 79 documentos Markdown de `inspection_cell/` y 512 enlaces locales comprobados: sin destinos ausentes ni caracteres Unicode de sustitución.
- 17 PDFs contrastados contra SHA-256, tamaño y número de páginas del manifiesto: sin diferencias. Tres fallos de descarga conservados como tales.
- 26 IDs de fuentes únicos; las 12 afirmaciones del índice remiten a fuentes y notas existentes. JSON del estudio válido.
- Script sintético ejecutado; verificaciones internas superadas, cifras contrastadas y figura revisada con 1260 puntos de prueba. Se corrigió una etiqueta de figura y una notación de pasos del esqueleto antes del cierre.
- `git diff --check` sin incidencias en archivos rastreados. `git status` conserva las modificaciones de contexto existentes y la carpeta `inspection_cell/` no rastreada; no se ha hecho commit ni alterado software DAQ.
- Carpeta de este estudio: 31 archivos, aproximadamente 58,85 MiB, principalmente PDFs originales. Sin enlaces externos comprobados por fuerza bruta ni garantías de disponibilidad futura de webs.
