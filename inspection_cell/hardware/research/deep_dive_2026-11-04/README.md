# Investigación ampliada de viabilidad

Inicio: **2026-11-04, 13:36 UTC**. Investigación ampliada a petición del usuario: profundizar aproximadamente dos horas, incluyendo Reddit, y conservar conocimiento que ayude a decidir. La revisión documental no sustituye ensayos físicos.

**Empezar por el [dictamen de viabilidad](feasibility.md).** Resume qué parece viable, qué no se puede deducir de una imagen 2D y qué probar antes de comprar. Los [requisitos](../../../docs/requirements.md) y la [definición de medidas](../../../docs/measurement_definition.md) son la referencia vigente.

## Navegación por decisión

| Necesidad | Documento |
| --- | --- |
| Saber si el montaje del PowerPoint funcionará | [Dictamen y prototipo](feasibility.md) |
| Comparar soluciones que ya se han usado | [Antecedentes: espirales, escáner, microscopio, plantilla y 3D en línea](existing_solutions.md) |
| Entender por qué longitud y ancho no comparten error absoluto | [Cálculos y límites](calculation_notes.md), [script](geometry_sensitivity.py), [datos](geometry_sensitivity.json) |
| Separar contracción de cambios de altura o apoyo | [Variación detectable](detectable_variation.md) |
| Elegir una referencia y validar sin circularidad | [Calibración y comprobación independiente](calibration_references.md) |
| Elegir focal/apertura y controlar bordes | [Óptica e iluminación](optics_and_lighting.md), [alternativas de lente](lens_alternatives.md) |
| Comparar luz, masa, coste y préstamo | [Paneles](lighting_candidates.md) |
| Buscar báscula conectable hasta 300 € | [Pesaje ampliado](weighing.md), [tabla vigente de candidatos](../../components/scales_shortlist.md) |
| Resolver apoyo, colada y futuros materiales | [Soporte y materiales](fixture_and_materials.md) |
| Dimensionar columna/brazo y revisar base del PPT | [Estructura](mechanical_frame.md) |
| Conectar imagen y peso sin definir aún la aplicación | [Viabilidad de adquisición](../../electrical/acquisition_feasibility.md) |
| Leer qué falló a otros usuarios | [Diez hilos de Reddit, lectura crítica](field_reports.md) |
| Pedir un ensayo o aclaración de proveedor | [Consultas preparadas, no enviadas](supplier_questions.md) |
| Empezar con los medios que ya hay | [Protocolo de laboratorio](../../../validation/protocols/first_lab_checks.md), [plantilla vacía](../../../validation/templates/bench_record.md) |
| Rastrear una conclusión | [Índice de evidencias](evidence_index.json), [archivos y procedencia](sources/README.md) |
| Saber qué se revisó y qué quedó sin ensayar | [Registro de revisión](review_log.md) |

## Lo confirmado por el usuario durante la ampliación

- Interesan **avance de llenado y contracción/cambios pequeños de piezas completas**.
- Hay pie de rey y básculas **sin USB ni RS-232**. No conoce sus modelos; seguir buscando una nueva sin esperar ese dato.
- PP es el material inicial; habrá otros. Validar luz/apoyo por condición, sin prometer una configuración universal.

Se conserva Markdown para razonamiento y JSON para localizar evidencia. Una base SQL no aporta suficiente valor en esta fase y haría menos sencilla la revisión en Git.

## Cómo interpretar lo guardado

- **Dato primario:** manual, ficha, artículo experimental o guía metrológica. Registrar modelo/revisión y condición; una fuente no valida nuestro montaje.
- **Experiencia de usuario:** Reddit o implementación particular. Sirve para identificar fallos y preparar ensayos, no como garantía de prestaciones.
- **Cálculo propio:** modelo con supuestos explícitos. No es una medición ni una simulación mecánica completa.
- **Pendiente:** dato ambiguo, acceso parcial o prueba no realizada. El manifiesto distingue descargas correctas y fallidas.
- Los precios se observaron el 2026-11-04. Impuestos, transporte y accesorios no uniformes; no tratarlos como ofertas finales.

No se ha contactado a proveedores ni compartido fotos/CAD, comprado equipos o ejecutado pruebas físicas. El control del ordenador se detuvo con Escape durante la revisión CAD; quedó pendiente y no se continuó por otra vía. Las observaciones de forma proceden de fotos y del script 2D.

## Retomar sin repetir la investigación

Leer primero el dictamen y consultar la pregunta concreta en el índice. Priorizar muestras y pruebas de apoyo/altura/precarga sobre añadir candidatos similares. Actualizar [estado central](../../../docs/research_status.md), requisitos y decisiones cuando llegue evidencia nueva; conservar las discrepancias hasta resolverlas. La [primera revisión](../2026-11-04_hardware_review.md) queda como antecedente, no como selección actual de compra.
