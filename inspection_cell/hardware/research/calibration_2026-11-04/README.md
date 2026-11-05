# Calibración dimensional: píxeles → milímetros

Estudio del **2026-11-04** solicitado para Machina. Investigación documental, propuesta de ensayo y simulación geométrica; **no hay validación física de la celda**. No se ha implementado el software de inspección.

## Recomendación

Calibrar **la cámara, el objetivo y el montaje reales** mediante una referencia dimensional caracterizada. Para esta estación fija, el resultado necesario es un mapa de coordenadas de imagen a milímetros **del plano de medida**. No basta con dividir el campo nominal por los píxeles ni con aceptar un RMS de reproyección pequeño.

El checkerboard es una opción conocida y útil, pero no obligatoria: también sirven retículas de puntos, ChArUco o una retícula densa que calibre directamente el plano. No evitaría la referencia física para ahorrar una operación ocasional. La calibración se guarda y se reutiliza mientras la configuración y sus controles permanezcan estables; no hay que poner el ajedrez en cada ciclo.

Para el prototipo haría una calibración del plano y, si se puede fotografiar el patrón inclinado con nitidez sin reenfocar, una campaña inicial de intrínsecos/distorsión. Compararía sus **resultados en dimensiones independientes**, no elegiría por el menor residuo de entrenamiento. Los campos estrechos de 35/75 mm pueden hacer que focal y distancia estén muy correlacionadas sin impedir un buen mapa de un plano fijo.

La limitación principal que sigue abierta es la **altura de la espiral y su condición de apoyo**, seguida de bordes/material/iluminación y estado térmico. Una calibración 2D no recupera la longitud espacial de una pieza libre con alturas desconocidas. El apoyo debe mejorar la condición de medida sin imponer el recorrido nominal que queremos evaluar.

## Dónde está cada respuesta

| Necesidad | Documento |
| --- | --- |
| Entender escala, homografía, distorsión y plano | [De píxeles a mm](pixel_to_mm.md) |
| Saber qué se calibra en FLIR + Computar y qué ajustes fijar | [Cámara y objetivos](flir_computar.md) |
| Elegir patrón y valorar alternativas al ajedrez | [Patrones y alternativas](targets_and_alternatives.md) |
| Ejecutar la futura prueba con equipos prestados o comprados | [Protocolo propuesto](recommended_protocol.md) |
| Distinguir ruido, sesgo, incertidumbre y cambios detectables | [Repetibilidad e incertidumbre](repeatability_uncertainty.md) |
| Retomar las fuentes en inglés y las páginas realmente leídas | [Lectura de literatura](literature_review.md) |
| Reproducir los ejemplos y conocer sus supuestos | [Notas de simulación](simulation_notes.md), [script](calibration_sensitivity.py), [resultados](calibration_sensitivity.json) y [figura](calibration_sensitivity.png) |
| Consultar afirmación, respaldo, límite y siguiente prueba | [Índice estructurado](evidence_index.json) |
| Ver procedencia e integridad de PDFs y alcance del trabajo | [Manifiesto](sources/download_manifest.json) y [registro de revisión](review_log.md) |

## Tres números que ayudan a no confundir prestaciones

- **Muestreo:** un campo de 200 mm en 3648 píxeles da 0,05482 mm/px. Localizar un borde a una fracción de píxel es posible; no convierte esa fracción en exactitud garantizada.
- **Escala:** 0,02 % de error relativo supone aproximadamente 0,0008 mm sobre 4 mm, pero 0,1021 mm sobre 510,508806 mm. Una escala equivocada del patrón puede dejar intacto el ajuste en píxeles.
- **Altura:** en el ejemplo perpendicular a 800 mm, elevar uniformemente un recorrido plano 1 mm produce unos 0,639 mm de error al interpretarlo con la calibración anterior; para un ancho de 4 mm serían unos 0,005 mm. Es un cálculo idealizado, **no** una predicción de la espiral con alabeo local.

Los ejemplos se desarrollan en los documentos y en el script. Distorsión, inclinación y errores de la simulación son inventados para aislar efectos; no son mediciones de los Computar.

## Evidencia que falta para decidir si funcionará

1. Definir y observar sección, altura y apoyo de la pieza, incluida colada. Conservar ambos objetivos: avance de llenado y cambios de piezas completas.
2. Probar una referencia dimensional independiente por posición, orientación y altura. Añadir anchos de 3–4 mm y una curva caracterizada; una regla sola no valida la longitud central.
3. Separar capturas inmóviles, recolocación de una pieza fría y evolución de una pieza caliente. Añadir pequeños movimientos y cambios controlados de luz para descubrir sesgos ocultos en una ráfaga estable.
4. Medir la deriva de arranque y entre sesiones; fijar enfoque, iris, luz, exposición, formato y mapa validado.

El pie de rey disponible sirve para primeros contrastes. No se da por suficiente para demostrar por sí solo un error de 0,1 mm sobre una curva de unos 510 mm. No hace falta volver a preguntar por puertos de las básculas: el usuario ya confirmó que no tienen USB ni RS-232.

## Alcance de la documentación

26 entradas de fuentes o grupos documentales en el índice de lectura; **17 PDFs originales archivados** en esta carpeta, además de las fichas ya existentes. Se consultaron artículos, secciones de libros, manuales y documentación oficial. No se afirma haber leído completos todos los libros/manuales descargados. La copia personal autorizada de Szeliski permanece fuera de la documentación versionable; el índice conserva el enlace del autor.

Volver al [estado general de investigación](../../../docs/research_status.md) para óptica, soporte, luz, báscula y requisitos vigentes. El estudio general previo está en [deep_dive_2026-11-04](../deep_dive_2026-11-04/README.md).
