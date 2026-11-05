# Contexto para trabajar en inspection_cell

Antes de continuar, leer `docs/research_status.md` y `docs/requirements.md`.
Leer después `docs/measurement_definition.md` y el dictamen vigente enlazado desde el estado. El índice de investigación está en `hardware/research/README.md`.
Para preguntas de píxeles→mm, FLIR/Computar, patrones o repetibilidad, consultar `hardware/research/calibration_2026-11-04/README.md` y su índice de evidencia. La calibración del plano, el error de reproyección y la exactitud de medidas son conceptos distintos; no dar por corregida la altura desconocida de la espiral.
No volver a preguntar si interesa avance o contracción: ambas finalidades están confirmadas. Las básculas existentes carecen de USB y RS-232; seguir buscando sin esperar sus modelos. El PP es solo el material inicial.

- Mantener la documentación en español y respetar los requisitos actualizados tras las respuestas del usuario del 2026-11-04.
- El PowerPoint describe una propuesta histórica. Sus 1–2 m y ±0,10 mm obligatorio han sido matizados por el usuario; no reinstaurarlos como requisitos.
- Prioridad actual: hardware y evidencia metrológica. No implementar la aplicación de inspección por inferencia de una petición de investigación.
- Separar datos de fabricante, estimaciones del usuario, cálculos propios y ensayos realmente ejecutados. Mantener fecha, URL y supuestos de precios.
- Resolución de pantalla/píxel no equivale a error garantizado. Medir longitud proyectada no recupera automáticamente longitud espacial de una pieza alabeada.
- Registrar descubrimientos en los estudios correspondientes y actualizar `docs/research_status.md`, requisitos y decisiones cuando proceda.
- Conservar PDFs originales sin alterarlos y añadir procedencia de nuevas descargas al manifiesto correspondiente.
