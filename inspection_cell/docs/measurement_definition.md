# Qué queremos medir y qué no debe confundirse

Actualizado: 2026-11-04. El usuario confirma **ambos objetivos**: avance del llenado y cambios dimensionales/contracción en piezas completas. Este documento propone cómo distinguirlos; los extremos, apoyos y referencias todavía necesitan validarse con piezas/CAD.

## Magnitudes separadas

| Magnitud | Definición de trabajo propuesta | Condición o límite que debe acompañarla |
| --- | --- | --- |
| Masa con colada | Lectura neta del conjunto de polímero colocado, restando plataforma | Incluye colada; no confundir con masa de espiral sola. Material, temperatura/tiempo y tara identificados |
| Ancho local del hilo | Separación entre bordes visibles en dirección normal al recorrido proyectado | Llamarlo «diámetro» circular solo tras confirmar sección; no equivale a diámetro exterior de toda la espiral |
| Longitud proyectada observada | Recorrido del eje visible en el plano calibrado, con extremos definidos | Condición de apoyo y plano; no es automáticamente longitud espacial libre |
| Avance del llenado | Posición del frente respecto al recorrido de la cavidad, si puede establecerse esa correspondencia | Conservar método de alineación y su incertidumbre; contracción y alabeo no deben interpretarse como falta de llenado |
| Cambio dimensional de pieza completa | Diferencia entre medidas observadas de piezas comparables o respecto a referencia independiente | Mismo estado de apoyo/material/tiempo; no forzar radios y longitud al nominal durante el ajuste |

La guía de [Avient sobre espirales de flujo](https://www.avient.com/resources/knowledge-base/article/injection-molding-part-design) presenta el ensayo como comparación de capacidad de llenado bajo condiciones de canal y proceso definidas. Sus cifras de TPE y su sección rectangular no se trasladan a nuestro molde. El [antecedente experimental con espirales](../hardware/research/deep_dive_2026-11-04/existing_solutions.md) muestra además que elegir otro criterio de frente cambia la medida.

## Inicio, final y colada

El [script nominal](geometry_reference.md) suma 510,508806 mm entre extremos de línea central y dibuja remates; no añade los radios de esos remates a la longitud. Si medimos en una imagen hasta la punta exterior de un extremo redondeado, no obtenemos necesariamente el mismo segmento matemático. Con hilo de 3–4 mm, la diferencia de definición puede ser del orden de un radio, mucho mayor que 0,1 mm. **No se ha confirmado que el remate real tenga esa forma.**

Antes de validar hay que fijar en una imagen/CAD:

1. El punto o sección de inicio donde termina la colada y empieza la espiral.
2. El criterio de final: intersección de eje con frente de llenado, centro de un remate geométrico u otra referencia explícita.
3. Las zonas ocultas por colada, salientes o soporte y qué medida sigue siendo observable.

Si falta un tramo, informar longitud visible y motivo, o declarar longitud total no medible. Completarlo con el nominal podría ser una **estimación** separada, nunca una observación. Mantener colada en la foto no impide excluirla de la región dimensional, pero puede impedir ver el inicio.

## Alineación con el nominal sin borrar contracción

Una traslación/rotación cambia colocación, no tamaño. Un escalado libre o deformación que haga coincidir cada vuelta con el CAD puede absorber precisamente la variación dimensional buscada. Conservar siempre el recorrido observado en unidades calibradas, aunque también se calcule una correspondencia con el nominal para localizar el frente o las zonas de sensores.

Para comparar avance de llenado hace falta una referencia de alineación reproducible. No asumir que las huellas de T1/P1/P2/T2 se ven en la pieza solo porque el script las dibuje; son sensores del molde. Tampoco un tope de soporte demuestra por sí solo la posición que tuvo cada punto dentro de la cavidad.

Una pieza completa contraída puede tener menor recorrido que el nominal sin estar incompleta. Buscar evidencia del extremo terminal moldeado y del frente, además del número de longitud. Las fotos y CAD pendientes deben resolver qué rasgos existen.

## Consecuencias para el soporte y la aceptación

Un apoyo que controla altura ayuda a la cámara convencional, pero una ranura ceñida puede imponer recorrido lateral o estirar una pieza blanda. Hay que comparar pieza libre y apoyada. Si se elige medir bajo sujeción, esa condición forma parte de la definición; no declarar que representa sin más la geometría libre.

No hay una única tolerancia de «cámara». Se evaluarán ancho, longitud, frente y masa por separado, comparando variación entre piezas con ruido de recolocación y sesgos. El usuario ha mantenido 0,1 mm como orientación. Las [pruebas de laboratorio](../validation/protocols/first_lab_checks.md) permiten empezar a cuantificarlo sin construir la celda definitiva.

Véanse [variación detectable](../hardware/research/deep_dive_2026-11-04/detectable_variation.md) para separar sesgo estable, altura y contracción, y [referencias de calibración](../hardware/research/deep_dive_2026-11-04/calibration_references.md) para no confundir resolución del patrón con exactitud dimensional.
