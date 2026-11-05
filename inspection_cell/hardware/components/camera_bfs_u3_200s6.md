# Cámara FLIR Blackfly S BFS-U3-200S6

Extracción revisada visualmente el 2026-11-04 desde [BFS-U3-200S6-Datasheet.pdf](datasheets/BFS-U3-200S6-Datasheet.pdf), páginas 1–2. Archivo suministrado en `C:\edu\projects\Machina`, idéntico al archivado previamente desde Descargas. La ficha identifica la revisión `BFS-U3-200S6-v2` y copyright de 2019; no acredita disponibilidad comercial actual.

La ficha cubre **BFS-U3-200S6M-C (monocroma)** y **BFS-U3-200S6C-C (color)**. La [oferta IN26-1893](quotes/IN26-1893.pdf) corresponde a la variante **M-C**, código comercial `FLI-BFS-U3-200S6M-C`. Los datos comunes de ambas variantes se indican a continuación; el procesamiento descrito corresponde a la mono.

## Imagen y adquisición

| Parámetro | Valor de la ficha, página 2 |
| --- | --- |
| Resolución | 5472 × 3648 píxeles; 20,0 MP |
| Sensor | Sony IMX183, CMOS, formato comercial 1 pulgada |
| Tamaño de píxel | 2,4 µm |
| Lectura | Rolling shutter con global reset |
| Conversor ADC | 10 y 12 bits |
| Frecuencia indicada | 18 FPS; mínimo indicado de 1 FPS |
| Exposición | 67 µs a 30 s |
| Ganancia | 0 a 27 dB |
| Modos de adquisición | Continua, una imagen y varias imágenes |
| Imagen parcial | Binning de píxeles, decimación y ROI |
| Procesamiento en variante mono | Gamma, tabla de consulta (LUT) y nitidez |
| Secuenciador | Hasta 8 conjuntos con 5 funciones |
| Búfer de imágenes | 240 MB |
| Configuraciones de usuario | 2 conjuntos configurables |
| Memoria flash | 6 MB no volátiles |

Condiciones de la cifra de FPS: `Device Link Throughput Limit` de 500 MB/s, `Acquisition Frame Rate` deshabilitado y valores redondeados hacia abajo a enteros. La nota de ficha indica que frecuencia mínima, ganancia y exposición mantienen los rangos en modos con y sin binning. Los límites no implican que todas las combinaciones de exposición, formato y frecuencia sean simultáneamente alcanzables.

La página 1 menciona API GenICam3 con biblioteca gráfica y registro de eventos/errores. La ficha no incluye instrucciones de instalación, versión de SDK compatible con el PC ni la secuencia de comandos para disparar una imagen; siguen pendientes del manual/SDK.

## Conexiones y alimentación

| Parámetro | Valor de la ficha, página 2 |
| --- | --- |
| Interfaz de datos | USB 3.1 Gen 1 |
| Estándar de visión | USB3 Vision v1.0 |
| I/O optoaislada | 1 entrada y 1 salida |
| I/O no aislada | 1 línea bidireccional y 1 entrada |
| Salida auxiliar | 3,3 V, máximo 120 mA |
| Alimentación | 8–24 V mediante GPIO o 5 V mediante USB3 |
| Consumo máximo | 3 W |

Estos datos no especifican pinout, niveles admisibles de entrada, temporización ni cable GPIO. Antes de diseñar disparo físico o conectar un controlador de luz se necesita el manual correspondiente. El cable USB de 2 m pertenece a la oferta, no a esta tabla de características.

## Montaje y ambiente

| Parámetro | Valor de la ficha, página 2 |
| --- | --- |
| Montura de lente | C-mount |
| Dimensiones del cuerpo | 29 × 29 × 30 mm |
| Masa | 36 g |
| Temperatura de operación | 0 a 50 °C |
| Temperatura de almacenamiento | −30 a 60 °C |
| Humedad de operación | 20–80 %, sin condensación |
| Humedad de almacenamiento | 30–95 %, sin condensación |

El cuerpo no incluye las dimensiones de lente, conectores, soporte ni espacio de curvatura del cable. La ficha no aporta un plano acotado de los puntos de fijación; se requiere para cerrar el soporte mecánico.

## Datos derivados y uso en la celda

Por cálculo con el número de píxeles y su tamaño, el área activa es aproximadamente **13,1328 × 8,7552 mm**, con diagonal **15,7837 mm**. Es un valor derivado, no una cota mecánica del encapsulado. El sensor tiene relación de aspecto 3:2; la etiqueta «1 pulgada» no equivale a 25,4 mm de lado o diagonal activa.

El modo de una imagen es relevante para la captura tras estabilización del peso, pero se debe comprobar el disparo y sus tiempos con el SDK. El rolling shutter con global reset debe conservarse como descripción exacta del modelo y evaluarse con pieza inmóvil e iluminación estable.

La variante mono encaja con el estudio de silueta. Los ajustes de gamma, nitidez, binning, ROI y exposición deben quedar identificados en cada configuración de medición y comprobarse durante la calibración. Los 20 MP no constituyen una garantía de error de ±0,10 mm.

Véanse el [estudio de FOV y distancia](../research/vision.md), la [ficha extraída de la lente](lens_v7531_mpz.md) y la [arquitectura de conexiones](../electrical/README.md).

## Comprobación comercial y documental actual

La [página oficial del modelo M-C](https://www.teledynevisionsolutions.com/en-150/products/blackfly-s-usb3/?model=BFS-U3-200S6M-C&segment=iis&vertical=machine+vision), consultada el 2026-11-04, indica **In Production**. No hay evidencia en esta consulta de descatalogación. Se observaron **620,00 y 645,50 € sin IVA** en consultas de la misma jornada; conservar la discrepancia y solicitar precio entregado. El total con IVA aproximado del 20 % que muestra esa página no es un total español verificado.

La web confirma disparo por software/hardware, rolling shutter con global reset y 18 FPS con ADC de 12 bits en PC con chipset Intel USB3. Su exposición mínima figura como 69 µs frente a 67 µs de la ficha suministrada; comprobar revisión real si fuese relevante. La [nota de adquisición](../electrical/acquisition_feasibility.md) reúne la documentación de integración. La oferta histórica de STEMMER y el PDF original se conservan sin alterar.
