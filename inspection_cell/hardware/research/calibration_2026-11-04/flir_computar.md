# Calibrar la FLIR con los Computar candidatos

Consulta: 2026-11-04. Configuración propuesta; **no se ha conectado ni calibrado una cámara física**.

## Qué está confirmado

La [BFS-U3-200S6M-C](https://www.teledynevisionsolutions.com/en-gb/products/blackfly-s-usb3/?model=BFS-U3-200S6M-C&segment=iis&vertical=machine+vision) es monocroma, 5472 × 3648, píxel 2,4 µm, montura C y rolling shutter con global reset. Sus opciones incluyen disparo, ROI, binning/decimación y procesado de imagen. La ficha describe prestaciones de adquisición; no proporciona una transformación métrica de nuestra estación.

Teledyne publica un [ejemplo oficial Spinnaker + OpenCV](https://www.teledynevisionsolutions.com/en-hk/support/support-center/application-note/iis/build-your-own-stereo-vision/) que estima intrínsecos/distorsión y guarda archivos YAML a partir de imágenes de un patrón. Es un ejemplo estéreo con **otro modelo y otra óptica**, útil para confirmar el flujo de trabajo; no demuestra la precisión del conjunto propuesto ni obliga a usar dos cámaras. Su receta de exposición automática posterior no se adopta aquí para medición de bordes.

Los [V3522-MPZ de 35 mm](https://www.computar.com/products/v3522-mpz) y [V7531-MPZ de 75 mm](https://www.computar.com/products/v7531-mpz) son ópticas de focal fija, enfoque e iris manuales. Las [fichas archivadas](../../components/datasheets/README.md) sirven para dimensionar. Una distorsión nominal muy baja o redondeada a 0,0 % no aporta los coeficientes calibrados de una unidad, a una distancia y enfoque concretos.

No hemos localizado una calibración geométrica individual de **esta cámara + este objetivo + este montaje**. No afirmar que FLIR no calibra nada en fábrica: el [manual de FFC](https://softwareservices.flir.com/BFS-U3-200S6/latest/Model/public/FlatFieldCorrectionControl.html) sí describe correcciones de ganancia/offset de fábrica. Son correcciones radiométricas; no son la escala píxel→mm.

## Consecuencia particular de las focales

Cálculo aproximado a infinito usando el área activa 13,1328 × 8,7552 mm y `AOV=2 atan(sensor/(2f))`:

| Focal | Campo angular horizontal | Vertical | Implicación |
| --- | ---: | ---: | --- |
| 35 mm | 21,25° | 14,26° | Cuidar diversidad de inclinaciones si se estiman intrínsecos |
| 75 mm | 10,01° | 6,68° | Geometría aún más débil para separar focal y distancia |

Son estimaciones, no campos calibrados a corta distancia. Strobl 2009 y Stamatopoulos 2010 estudian la dificultad de calibrar campos estrechos. **No trasladar sus umbrales ni errores numéricos directamente a esta FLIR.** Nuestra conclusión práctica: evaluar estabilidad del mapa en milímetros y no aceptar una focal estimada solo porque baja el RMS. Una buena calibración del plano puede ser útil aunque la focal y la distancia individuales sean poco estables.

Para cubrir 150–200 mm de lado corto, 35 mm mantiene la ventaja de altura ya calculada en el [estudio de ópticas](../deep_dive_2026-11-04/lens_alternatives.md). La calibración no vuelve compacto el montaje de 75 mm ni elimina el alabeo.

## Receta de adquisición que dejaría fijada

Propuesta propia para el ensayo; verificar disponibilidad de nodos en la unidad/firmware recibidos. La [referencia pública](https://softwareservices.flir.com/BFS-U3-200S6/latest/Model/Readme.html) consultada identifica firmware 1705.0.124.0 y fecha 2017; no asumir coincidencia exacta con equipos actuales.

| Parámetro | Punto de partida / registro |
| --- | --- |
| Resolución | Completa; binning y decimación a 1. Registrar `Width`, `Height`, `OffsetX/Y`, `ReverseX/Y` |
| Imagen | Monocroma, archivo sin pérdidas; guardar bit depth/ADC y formato reales. Un contenedor Mono16 no implica 16 bits efectivos |
| Exposición y ganancia | Ajustar sin saturar blancos ni recortar sombras; después fijar `ExposureAuto=Off`, `GainAuto=Off` para cada receta validada |
| Procesado | Como base: `GammaEnable=False`, sharpening desactivado, LUT desactivada o identidad. Guardar estado FFC y corrección de píxeles |
| Enfoque e iris | Ajustar a distancia/altura de trabajo, elegir apertura por ensayo de bordes y bloquear ambos. No reenfocar entre imágenes de calibración |
| Iluminación | Misma geometría, espectro/filtro y soporte óptico que se van a validar. Evitar parpadeo e imágenes con movimiento |
| Temperatura | Registrar `DeviceTemperature` y deriva de una referencia fija. Establecer calentamiento por estabilidad observada, no por un número de minutos inventado |
| Disparo | Captura con pieza y patrón quietos. La detección de peso por sí sola no demuestra ausencia de vibración |

Los controles de [formato](https://softwareservices.flir.com/BFS-U3-200S6/latest/Model/public/ImageFormatControl.html), [gamma/sharpening](https://softwareservices.flir.com/BFS-U3-200S6/latest/Model/public/AnalogControl.html) y [temperatura/disipación](https://softwareservices.flir.com/BFS-U3-200S6/latest/Family/Temperature.htm) están documentados por FLIR. Desactivar mejoras visuales es nuestra receta metrológica inicial, que se debe comparar experimentalmente; no implica desactivar indiscriminadamente toda corrección del sensor.

## Qué se guarda y cuándo se repite

Guardar por separado la configuración de adquisición y la calibración geométrica: los User Sets de cámara no equivalen a guardar `K,D,H` o el mapa métrico de la estación.

- Identificadores de cámara y lente, fotos de bloqueos, enfoque, apertura, distancia de montaje y plano de referencia.
- Capturas originales del patrón, ID/certificado/coordenadas reales, altura de su superficie, temperatura y fecha.
- Modelo, matrices/mapa, unidades, dominio válido, versión de librería y resultados de validación independiente.
- Identificador de calibración asociado a cada futura inspección.

| Cambio | Acción propuesta |
| --- | --- |
| Cambio de objetivo, desmontaje, reenfoque o golpe | Recalibrar y validar el conjunto |
| Cámara y lente se mueven juntas, conservando ajustes | Redeterminar plano/extrínsecos y validar; intrínsecos pueden conservarse si se demuestra estabilidad |
| Apertura, filtro, iluminación o procesado cambian | Revalidar dimensiones/bordes; recalibrar si cambia el mapa o el enfoque |
| ROI/resize/flip | Transformar coordenadas explícitamente y validar; no aplicar matrices de la imagen original a coordenadas nuevas |
| Temperatura fuera del rango validado | Esperar estabilidad o usar receta caracterizada; no extrapolar una compensación no ensayada |
| Nada cambia y el control de referencia pasa | Reutilizar calibración. No hace falta fotografiar el checkerboard en cada ciclo |

Para un recorte puro sin otros cambios, se pueden sumar los offsets al punto detectado y usar el mapa de imagen completa. Eso no justifica tratar binning o decimación como un recorte. El [protocolo](recommended_protocol.md) define cómo comprobarlo antes de automatizar.

## Consulta técnica preparada para proveedor, no enviada

- ¿Hay calibración geométrica de la pareja de números de serie, al enfoque y campo previstos, o solo fichas nominales y calibración radiométrica del sensor?
- ¿Cómo se define el 0,0 % de distorsión de la ficha de lente, bajo qué condiciones se mide y con qué tolerancia? ¿Hay curva espacial a la distancia propuesta?
- ¿Se puede ensayar la FLIR con 35 mm y 75 mm usando la misma referencia caracterizada, luz y piezas, sin reenfocar durante cada serie de alturas?
- ¿Podéis entregar imágenes originales, ajustes y errores dimensionales en puntos independientes, además del RMS de calibración?

Estas preguntas concretan la evaluación; no se ha contactado ni comprometido una compra.
