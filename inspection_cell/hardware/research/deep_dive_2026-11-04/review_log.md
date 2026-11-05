# Registro de revisión y límites del trabajo

Ampliación del 2026-11-04, solicitada para profundizar aproximadamente dos horas. Inicio registrado: **13:36:08 UTC**. Hora de cierre y comprobaciones finales registradas al terminar abajo.

## Trabajo que aporta a la decisión

- Se distinguieron avance del llenado y cambios de piezas completas, incorporando la confirmación «ambas cosas» a requisitos, definición de medidas y contexto de futuras sesiones.
- Se contrastaron antecedentes de espirales por escáner, microscopio, plantilla y medición 3D en línea. Sus resultados se mantienen ligados a materiales, tamaños y condiciones originales.
- Se revisaron diez hilos de Reddit para identificar problemas de recolocación, deriva, pesaje y comunicación; se contrastaron las conclusiones técnicas con fuentes primarias.
- Se ampliaron alternativas de lentes, luz y básculas. Se comprobaron manuales de salida de datos, modelos/revisiones, cargas, precios y discrepancias. Se añadieron rutas de menor capacidad y 1 mg sin presentarlas como sustitución directa del apilado.
- Se estudiaron apoyo, colada, materiales futuros, rutas de carga, rigidez de perfiles, altura total y referencias dimensionales.
- Se ejecutaron modelos geométricos y se contrastaron casos de altura uniforme con solución analítica. Se prepararon pruebas con medios existentes y consultas técnicas listas para revisar, sin enviarlas.

## Evidencia conservada

Markdown mantiene el razonamiento; el índice JSON permite encontrar fuentes por pregunta y distinguir datos publicados, experiencia, cálculo y prueba pendiente. Las descargas tienen URL, fecha, tamaño y SHA-256. Los fallos de descarga permanecen registrados; no se presentan como archivos disponibles. Los PDFs originales de cámara, óptica y oferta se conservan sin alterar.

El punto de entrada es [research_status.md](../../../docs/research_status.md). Para decidir, leer [feasibility.md](feasibility.md); para aportar evidencia física, usar [first_lab_checks.md](../../../validation/protocols/first_lab_checks.md).

## Límite de lo demostrado

La investigación documental permite elegir qué prototipo y pruebas merecen la pena. No demuestra exactitud, repetibilidad ni cadencia del conjunto sin construirlo y ensayarlo. No se han realizado pruebas físicas, comprado equipos, contactado proveedores o compartido muestras/CAD.

La revisión CAD quedó pendiente cuando se detuvo el control del ordenador con Escape; no se continuó por automatización alternativa. Las observaciones de forma se basan en imágenes suministradas y geometría 2D, sin confirmar la sección real. Se han conservado los ficheros CAD originales para una revisión posterior autorizada.

## Cierre y comprobaciones

Cierre documental: **2026-11-04 15:29:39 UTC**, aproximadamente **114 minutos** desde el inicio registrado, dedicados a búsqueda, lectura, cálculos, archivo y revisión. Es tiempo de trabajo documental; no son horas de ensayo físico.

Comprobación final realizada:

- 70 documentos Markdown y 445 enlaces locales revisados: sin enlaces a archivos inexistentes detectados.
- 36 archivos fuente de la recopilación original verificados; 11 diapositivas conservadas.
- 23 descargas correctas de esta ampliación con SHA-256 verificado; 5 intentos fallidos registrados como tales.
- 76 referencias y 24 conclusiones/preguntas indexadas; identificadores, rutas y relaciones comprobados.
- Sin caracteres de sustitución ni encabezados duplicados detectados en los Markdown.
- Geometría nominal contrastada con suma analítica de arcos; casos de elevación uniforme contrastados con escala pinhole. Concordancia numérica mejor de 0,00001 mm en esos ejemplos. Esto comprueba el cálculo, no la pieza real.
- Distancias de focales 25/35/50/75 mm, masas de placa, ejemplo contracción/altura y sumas de IVA comprobados.
- `git diff --check` sin incidencias; no se han creado commits.

La siguiente evidencia que cambia la decisión es física: masa y geometría de muestras, repetición bajo apoyo y ensayo óptico/pesaje del conjunto. Más catálogos similares no sustituyen esas comprobaciones.
