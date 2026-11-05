# Investigación de hardware

**Último estudio específico:** [calibración de píxeles a mm](calibration_2026-11-04/README.md): FLIR/Computar, literatura en inglés, patrones y alternativas al checkerboard, repetibilidad y validación independiente. Incluye PDFs, índices de evidencia y simulación reproducible, sin ensayo físico.

**Estudio general:** [dictamen de viabilidad](deep_dive_2026-11-04/feasibility.md), [índice ampliado](deep_dive_2026-11-04/README.md) y [pruebas con medios disponibles](../../validation/protocols/first_lab_checks.md). Incluye nuevos candidatos, artículos, Reddit, cálculos de altura/longitud y consultas preparadas.

La [primera revisión del 2026-11-04](2026-11-04_hardware_review.md): evaluación del PowerPoint, error de longitud/diámetro, comparación de focales y alternativas mecánicas. Consultar [básculas hasta 300 €](../components/scales_shortlist.md), [fuentes y limitaciones de acceso](sources_2026-11-04.md), [cálculos reproducibles](optics_tradeoffs.py) y [contexto para futuras sesiones](../../docs/research_status.md).

| Estudio | Pregunta principal |
| --- | --- |
| [Visión y óptica](vision.md) | ¿Qué FOV, distancia y detalle entrega el conjunto candidato? |
| [Metrología](metrology.md) | ¿Qué variación se distingue del ruido, usando 0,1 mm como orientación? |
| [Calibración dimensional](calibration_2026-11-04/README.md) | ¿Cómo convertir píxeles a mm, con qué patrón y cómo verificar repetibilidad y exactitud? |
| [Iluminación](lighting.md) | ¿Cómo obtener bordes estables en los distintos materiales? |
| [Pesaje](weighing.md) | ¿Cómo pesar y detectar colocación de forma fiable? |
| [Soporte y manipulación](handling.md) | ¿Cómo posicionar sin deformar ni ocultar la pieza? |

Cada estudio debe separar datos de ficha, inferencias, hipótesis y resultados de ensayo. Añadir fecha y fuente a nuevas comparaciones. Registrar la selección en [decisiones](../../docs/decisions.md) y sus consecuencias en la [BOM](../components/bom.md).
