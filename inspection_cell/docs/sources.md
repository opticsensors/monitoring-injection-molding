# Fuentes y procedencia

Investigación ampliada: [dictamen e índice temático](../hardware/research/deep_dive_2026-11-04/README.md), [evidencias estructuradas](../hardware/research/deep_dive_2026-11-04/evidence_index.json) y [nuevas descargas con SHA-256](../hardware/research/deep_dive_2026-11-04/sources/download_manifest.json). Incluye artículos, manuales y experiencias de Reddit, distinguiendo su alcance.

Primera investigación web: [registro del 2026-11-04](../hardware/research/sources_2026-11-04.md), con nueve PDFs adicionales y [manifiesto de descargas](references/research_2026-11-04_manifest.json). El [estado de investigación](research_status.md) recoge las respuestas y recomendaciones vigentes; este documento conserva la procedencia de los originales.

Recopilación: 2026-11-04. Se han leído el código geométrico, el contenido y las imágenes del PowerPoint, las dos fichas técnicas y la oferta. Las fichas de cámara y lente contienen páginas rasterizadas y se han revisado visualmente.

## Fuentes del proyecto

| ID | Fuente | Uso y alcance |
| --- | --- | --- |
| USR-01 | Descripción del usuario en esta conversación, 2026-11-04 | PP, deformación hasta 10 mm, hilo 3–4 mm, envolvente, automatización y objetivo dimensional |
| PPT-01 | [Solución control calidad Machina](references/Solucion_control_calidad_Machina.pptx) | Propuesta de 11 diapositivas; equipos, montaje, fotografías y precios históricos |
| GEO-01 | [spiral_sensors.py](../hardware/mechanical/geometry/spiral_sensors.py) | Arcos, longitud teórica, ancho de dibujo y sensores del molde |
| GEO-02 | [PNG](../hardware/mechanical/geometry/spiral_sensors.png) y [SVG](../hardware/mechanical/geometry/spiral_sensors.svg) originales | Esquema legible y vector editable suministrados junto al script |
| CAM-01 | [BFS-U3-200S6-Datasheet.pdf](../hardware/components/datasheets/BFS-U3-200S6-Datasheet.pdf) | Familia de cámaras mono/color, ficha de 2 páginas, ©2019 |
| LEN-01 | [V7531-MPZ.pdf](../hardware/components/datasheets/V7531-MPZ.pdf) | Óptica Computar de 75 mm, ficha de julio de 2022 |
| QUO-01 | [Oferta IN26-1893](../hardware/components/quotes/IN26-1893.pdf) | STEMMER, 31/07/2026, validez de 15 días; precios e identificación exacta del conjunto |
| CAD-01 | [Referencias CAD](../hardware/mechanical/cad/reference/README.md) | Ficheros suministrados de pieza/molde y componentes asociados; contenido CAD sin validar |

Directorio original de PPT, script, SVG, PNG y CAD:

```text
C:\Users\eduard.almar\OneDrive - EURECAT\Escritorio\proyectos\24. machina\quality control
```

Los tres PDF se localizaron en `C:\Users\eduard.almar\Downloads`. Se copiaron dentro de esta carpeta para que la documentación no dependa de esas ubicaciones.

En la revisión del 2026-11-04 también se localizaron los mismos tres PDF en `C:\edu\projects\Machina`, ubicación indicada posteriormente por el usuario. Se comprobó que los tres coinciden byte a byte con los archivados. Las dos fichas técnicas se copiaron desde esa ubicación sobre los destinos idénticos; la oferta se verificó sin sustituir su copia. Las fuentes adicionales figuran en `verified_sources` del manifiesto, conservando la procedencia inicial.

La extracción técnica ampliada se mantiene en [camera_bfs_u3_200s6.md](../hardware/components/camera_bfs_u3_200s6.md) y [lens_v7531_mpz.md](../hardware/components/lens_v7531_mpz.md). Se revisaron visualmente la tabla y notas de la cámara y la tabla/plano de la lente, ya que las fichas no contienen texto seleccionable.

El [manifiesto de fuentes](references/source_manifest.json) registra ruta original, destino, tamaño y SHA-256 de cada copia y de las imágenes extraídas. El [índice del PowerPoint](references/presentation_index.json) conserva textos, medios y enlaces por diapositiva. Los 11 PNG de diapositivas se exportaron con PowerPoint desde una copia abierta en modo de solo lectura. No se modificaron los originales.

El PowerPoint contiene 20 imágenes PNG/JPEG y formas nativas de PowerPoint; no contiene medios SVG. Se conservan las imágenes originales y los renders completos para no perder las formas del dibujo de la celda. El SVG externo de la espiral se acompaña de su PNG original.

## Fuentes técnicas externas consultadas

Consulta: 2026-11-04. Se usan como explicación técnica, no como comprobación de precios actuales o disponibilidad.

- [FLIR: especificaciones BFS-U3-200S6](https://softwareservices.flir.com/BFS-U3-200S6/latest/Model/spec.html): referencia del fabricante para la familia de cámara. Las tablas locales se basan en la ficha suministrada y la oferta.
- [Edmund Optics: The Advantages of Telecentricity](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/advantages-of-telecentricity/): relación entre distancia, magnificación y error de perspectiva.
- [Edmund Optics: Sensors and Lenses](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/sensors-and-lenses/): el rendimiento depende del sistema óptico completo, no solo del número de píxeles.

Los enlaces de productos de la presentación se mantienen en el [resumen visual](presentation_summary.md). Sus precios se transcriben como valores del documento, sin afirmar vigencia comercial.

## Diferencias y datos por verificar

- El usuario deja longitud real y peso como X. El script aporta una longitud **teórica**, sin resolver esos valores reales.
- La diapositiva 9 titula una báscula como «B.K.Licht Panel». La imagen muestra KERN y los enlaces apuntan a TFKB 8K-4-B y TYKUP-03-B; se documenta como identificación inferida de esos enlaces, pendiente de confirmar.
- Los 46,7 kg y 650 mm de la telecéntrica proceden del usuario. La ampliación localiza una referencia comercial coincidente, sin confirmar que sea la de STEMMER; véase [comparación óptica](../hardware/research/deep_dive_2026-11-04/optics_and_lighting.md).
- El presupuesto global y los precios de alternativas del PowerPoint no especifican de forma uniforme IVA, accesorios o transporte.
