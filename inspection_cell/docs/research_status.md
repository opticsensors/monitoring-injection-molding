# Retomar la investigación de la celda

Actualizado: **2026-11-04**, incorporando las últimas respuestas y el estudio específico de calibración píxeles→mm. La celda no está construida; no hay ensayos físicos ni equipos comprados confirmados.

## Lectura de entrada

1. [Requisitos vigentes](requirements.md) y [definición de medidas](measurement_definition.md).
2. **[Dictamen de viabilidad y prototipo recomendado](../hardware/research/deep_dive_2026-11-04/feasibility.md).**
3. **[Calibración dimensional: píxeles→mm](../hardware/research/calibration_2026-11-04/README.md)**: literatura en inglés, FLIR/Computar, alternativas al checkerboard y protocolo de validación.
4. [Investigación ampliada](../hardware/research/deep_dive_2026-11-04/README.md): artículos, Reddit, óptica, pesaje, soporte y cálculos con sus límites.
5. [Básculas comparadas](../hardware/components/scales_shortlist.md) y [primeras pruebas con medios disponibles](../validation/protocols/first_lab_checks.md).
6. [PowerPoint con imágenes](presentation_summary.md) y [geometría original](geometry_reference.md), cuando se necesite la propuesta histórica.

## Respuestas recibidas: no volver a preguntarlas

- **Interesan ambas cosas:** avance de llenado y cambios pequeños/contracción en espirales completas. Son resultados distintos; no imponer la geometría nominal a la pieza observada.
- **0,1 mm es una orientación**, no un límite obligatorio común de longitud y diámetro. Importa distinguir variación de piezas del ruido.
- La colada debe conservarse idealmente en fotos. Se admite estudiar un soporte transparente, incluso ranurado; no hay diseño aprobado.
- Pieza con colada: estimación del usuario de **100 g o menos**. Soporte + luz: unos **2 kg estimados**. Ninguno está pesado.
- Pesaje: **0,01 g deseado; 0,1 g mínimo y justo**. Máximo **300 € con IVA y conexión al PC**.
- FLIR + Computar son recomendaciones de STEMMER, abiertas a alternativas y no compradas.
- **2 m no es aceptable; 1 m ya es alto pero se puede considerar.** Distinguir distancia óptica y altura total desde mesa.
- Se mide **recién desmoldeada**. La prioridad es hardware; estudiar calor/apoyo sin bloquearse por tiempos de software.
- Hay **pie de rey y básculas de laboratorio sin USB ni RS-232**. El usuario desconoce sus modelos y pide continuar buscando sin depender de ellos. Usarlas para comprobaciones manuales; no volver a proponer descubrir RS-232.
- **PP inicialmente y otros materiales futuros.** No asumir sección circular, opacidad ni una receta universal.

## Conclusión provisional que debe conservarse

La arquitectura 2D + backlight + báscula es razonable. La automatización está respaldada por manuales de modelos concretos; la precisión del conjunto no está demostrada. **Una sola proyección no recupera en general la longitud espacial de una espiral libre alabeada.** Ancho, frente y longitud necesitan ensayos/definiciones separados. La [variación detectable](../hardware/research/deep_dive_2026-11-04/detectable_variation.md) distingue sesgos constantes de cambios de altura; el [estudio de referencias](../hardware/research/deep_dive_2026-11-04/calibration_references.md) evita dar por exacta una cuadrícula nominal.

La focal de **35 mm** es más compatible con la altura preferida: aproximadamente 0,635–0,835 m para campo cuadrado útil 150–200 mm con FLIR, frente a 1,36–1,79 m con 75 mm. Son distancias de lente delgada, no cotas de fabricación. Se han añadido alternativas VA de 35 mm; no elegir por etiqueta de megapíxeles.

El apoyo puede dominar el error: ranura ceñida, presión o colada oculta pueden alterar lo medido. Probar apoyo plano/alivio local y localización holgada; conservar observación de la forma. Columna/brazo y carga de báscula requieren rutas mecánicas distintas. La base 300 × 300 del PPT sigue sin validarse.

**Pesaje:** comparar U.S. Solid USS-DBS28-50 de 5 kg con Steinberg SBS-LW-1030 de 3 kg si el conjunto pesa unos 2 kg. U.S. Solid muestra unos 105–119 € sin total España confirmado; manual específico da repetibilidad ±0,03 g, no ±0,01 g. Steinberg: 178 € con IVA observado, unos 218–238 € con reserva de conexión, sin repetibilidad separada publicada. PCE-BSK 1100 queda para plataforma ligera; escenario 233,29 € conectado, capacidad 1,1 kg. Consultar tablas antes de repetir precios como ofertas.

**Luz:** el EFFILUX/Edmund del PPT pesa 1,9 kg y cuesta 765 € sin IVA antes de accesorios. TPL y VA publican programas de préstamo; no se ha solicitado ninguno. Comparar iluminación y fuerzas de cable antes de decidir si sacar panel de la carga.

**Calibración:** obtener un mapa validado del plano real de medida; checkerboard opcional, referencia dimensional necesaria. El estudio específico archiva 17 PDFs y 26 entradas de lectura, distingue intrínsecos/pose/escala y propone validación independiente. No aceptar RMS pequeño como precisión garantizada. Una ráfaga inmóvil puede ocultar sesgos subpíxel; comprobar posición, altura, luz, recolocación y deriva. La propuesta sigue sin ensayo físico.

## Qué evidencia falta ahora

1. Masa real de 3–5 piezas; fotos cenital/lateral/parte inferior de la unión de colada; altura de colada y sección ancho/espesor. Las fotos oblicuas del PPT ya se revisaron.
2. Repetición con pieza fría y apoyo provisional usando calibre/báscula disponibles; después evolución recién desmoldeada, separada del ensayo de repetibilidad.
3. Ensayo óptico con muestras, alturas conocidas y referencia independiente; pesaje con incrementos sobre precarga real.
4. Confirmaciones comerciales/técnicas de modelos concretos: [consultas preparadas, no enviadas](../hardware/research/deep_dive_2026-11-04/supplier_questions.md).

La revisión en SolidWorks quedó pendiente al detenerse el control del ordenador con Escape. No se han extraído nuevas cotas del CAD ni confirmado la sección. No reiniciar automatización del ordenador por inferencia de estas notas.

## Evidencia y mantenimiento

- [Índice estructurado de afirmaciones y fuentes](../hardware/research/deep_dive_2026-11-04/evidence_index.json): alcance, discrepancias y prueba pendiente.
- [Índice de evidencia de calibración](../hardware/research/calibration_2026-11-04/evidence_index.json), [lecturas en inglés](../hardware/research/calibration_2026-11-04/literature_review.md) y [PDFs con hashes](../hardware/research/calibration_2026-11-04/sources/download_manifest.json).
- [Fichas y manuales](../hardware/components/datasheets/README.md), [originales y hashes](references/source_manifest.json), [primeras descargas web](references/research_2026-11-04_manifest.json) y [descargas ampliadas](../hardware/research/deep_dive_2026-11-04/sources/download_manifest.json).
- [Cálculo óptico](../hardware/research/optics_tradeoffs.py) y [sensibilidad geométrica](../hardware/research/deep_dive_2026-11-04/calculation_notes.md): reproducibles, no ensayos físicos.
- [Decisiones](decisions.md) distingue acuerdos y recomendaciones. [Preguntas pendientes](open_questions.md) mantiene lo no resuelto.

No se ha implementado software de inspección ni modificado el contrato de medidas de la aplicación existente.
