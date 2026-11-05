# Revisión del montaje y alternativas de hardware

**Antecedente: primera revisión del 2026-11-04.** La ampliación posterior incorpora respuestas del usuario, U.S. Solid, más lentes, manuales, referencias de calibración y ensayos. Consultar el [dictamen vigente](deep_dive_2026-11-04/feasibility.md) antes de decidir; los cálculos de esta revisión conservan sus supuestos.

Fecha: **2026-11-04**. Investigación documental y cálculos propios; todavía no hay pruebas con piezas. Condiciones vigentes: [requisitos](../../docs/requirements.md). Evidencia: [fuentes consultadas](sources_2026-11-04.md) y [PDFs](../components/datasheets/README.md).

## Recomendación de la primera revisión

El concepto del PowerPoint —cámara cenital, silueta con backlight y báscula— es una base razonable para un prototipo. **Mantendría ese concepto, estudiaría primero una óptica de 35 mm y resolvería la plataforma de apoyo antes de cerrar la compra.** Una cámara de más resolución no resolverá por sí sola la altura variable de la espiral.

Para pesaje hay una candidata económica de 3 kg con división de 0,01 g y salida automática documentada: **Steinberg SBS-LW-1030**. Es prometedora para el apilado original, pero faltan prestaciones metrológicas demostradas. La **PCE-BSK 1100** ofrece especificaciones de repetibilidad más explícitas y exige una plataforma mucho más ligera. Ver [comparativa y costes](../components/scales_shortlist.md).

No hay evidencia suficiente para prometer detectar cualquier variación de 0,01 g o de 0,1 mm. La decisión debe basarse en la variación mínima que distingue el conjunto montado, especialmente al recolocar una pieza caliente.

## Por qué longitud y diámetro no tienen el mismo error

La cámara tiene un muestreo común, pero no un único error absoluto que se copie a todas las magnitudes. Tras convertir la imagen a binaria siguen existiendo varias contribuciones:

| Contribución | Efecto sobre ancho/diámetro | Efecto sobre longitud del eje |
| --- | --- | --- |
| Error relativo de escala | Proporcional a un ancho de 3–4 mm | Proporcional a un recorrido de unos 510 mm |
| Umbral de segmentación | Mover ambos bordes hacia fuera aumenta el ancho | Desplazamientos simétricos pueden cancelarse parcialmente en la línea central |
| Curvatura, extremos y unión de colada | Alteran mediciones locales | Cambian recorrido y puntos de inicio/fin |
| Variación de altura | Cambia escala y orientación locales | Cambia escala e introduce diferencia entre proyección y recorrido espacial |
| Ruido de bordes | Puede reducirse promediando, si no es sesgo común | No debe sumarse suponiendo que todos los píxeles tienen errores independientes |

**Ejemplo de escala:** un error del 0,1 % equivale a 0,004 mm sobre un diámetro de 4 mm, pero a 0,511 mm sobre una longitud de 510,5 mm. En cambio, un umbral que ensancha la silueta puede perjudicar más al diámetro que a su eje. Por tanto, tampoco es correcto afirmar que toda fuente de error aumenta siempre en proporción a la longitud.

Con el sensor FLIR y un campo útil cuadrado de 200 mm, el muestreo es **0,0548 mm/píxel**; 0,1 mm ocupa unos **1,82 píxeles**. Un hilo de 3–4 mm ocupa aproximadamente 55–73 píxeles. Esto permite plantear la medición, pero no demuestra exactitud. Conservar la imagen en gris permite estudiar los bordes antes de decidir el umbral; binarizar no elimina los errores ópticos.

Para distinguir piezas interesa separar **sesgo**, **repetibilidad sin mover**, **repetibilidad tras recolocar** y variación térmica real de la pieza. Un sesgo constante puede permitir comparaciones útiles, mientras una altura variable puede parecer contracción. Como ejemplo estadístico propio, dos mediciones independientes con desviación típica de 0,05 mm producen una diferencia con desviación de `sqrt(2) × 0,05 = 0,071 mm`; 0,1 mm de diferencia no queda entonces claramente separado del ruido. No es una estimación de la celda: muestra qué hay que medir experimentalmente.

## Óptica: el problema principal de los 75 mm es la distancia

La [FLIR propuesta](../components/camera_bfs_u3_200s6.md) tiene 5472 × 3648 píxeles de 2,4 µm: superficie activa calculada **13,1328 × 8,7552 mm**. Para encuadrar un cuadrado manda el lado corto del sensor. Un FOV de 200 × 200 mm requiere realmente una imagen completa de aproximadamente **300 × 200 mm**, salvo recorte posterior; no se deben usar 5472 píxeles para calcular el muestreo de ambos lados del cuadrado.

Estimación propia con lente delgada: `m = 8,7552 / lado_del_campo`, `u = f × (1 + 1/m)`.

| Focal | Para cuadrado de 150 mm | Para cuadrado de 200 mm | Interpretación |
| --- | ---: | ---: | --- |
| 25 mm | 0,45 m | 0,60 m | Compacta; mayor sensibilidad a altura |
| **35 mm** | **0,63 m** | **0,83 m** | Primera opción a estudiar con el límite de altura actual |
| 50 mm | 0,91 m | 1,19 m | Considerar si basta 150 mm con margen; menos adecuada para 200 mm |
| 75 mm | 1,36 m | 1,79 m | Difícil de conciliar con el montaje compacto solicitado |

`u` se mide desde el plano principal ideal de la lente, **no desde su frontal, montura o carcasa**. Las cotas definitivas requieren la tabla de trabajo del fabricante o una prueba. Además hay que sumar altura del soporte y posición de la cámara para dimensionar la estructura. El margen de colocación aumenta el FOV y la distancia: estos cuadrados ya deben incluir el margen que se decida.

La **Computar V3522-MPZ** comparte montura C y círculo de imagen de 16 mm con la familia propuesta; su focal es 35 mm y su apertura f/2,2–16. La diagonal activa calculada de la FLIR es 15,78 mm: encaja nominalmente en ese círculo. La **V5024-MPZ** de 50 mm es otra variante. Se guardaron ambas fichas y el catálogo MPZ. Falta oferta actual y comprobar nitidez en todo el campo, diafragma y distancia reales. [Computar V3522](https://www.computar.com/products/v3522-mpz).

El 0,0 % de distorsión de la ficha está redondeado: el catálogo indica una cifra decimal. No significa ausencia garantizada de distorsión. Calibrar a la distancia y enfoque utilizados sigue siendo necesario. Cerrar mucho el diafragma puede aumentar profundidad de campo, pero no elimina la perspectiva y reduce detalle por difracción; no fijar f/16 por defecto.

**Alternativa de cámara:** Daheng MER2-2000-19U3M, también IMX183 monocroma y USB3, permite comparar coste sin cambiar radicalmente el muestreo. VA Imaging mostraba **419 €**, con impuestos y transporte sin confirmar; no es un total comparable directamente con la oferta STEMMER. Mantener como alternativa comercial, sin asumir compatibilidad de SDK ni mejoras de precisión por cambiar de marca. [Fabricante](https://en.daheng-imaging.com/show-106-1998-1.html), [oferta observada](https://va-imaging.com/products/usb-camera-3-0-20mp-monochrome-sony-imx183-mer2-2000-19u3m).

## Alejar la cámara ayuda, pero no resuelve el alabeo

Modelo ilustrativo de perspectiva: calibración en un plano a distancia `Z`, objeto paralelo elevado `h` hacia la cámara; error relativo de escala `h / (Z − h)`.

| Elevación uniforme a Z = 800 mm | Error sobre 4 mm | Error sobre 510,509 mm |
| --- | ---: | ---: |
| 0,1 mm | +0,0005 mm | +0,064 mm |
| 1 mm | +0,0050 mm | +0,639 mm |
| 10 mm | +0,0506 mm | +6,462 mm |

Una espiral real no se eleva uniformemente; esta tabla **no predice su error real**. Demuestra la sensibilidad a altura y explica por qué alejar la cámara no garantiza recuperar longitud espacial. Los 800 mm son una distancia del modelo de proyección, no una cota frontal exacta de la lente de 35 mm. [Fundamento de telecentricidad, Edmund Optics](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/advantages-of-telecentricity/).

Incluso sin perspectiva, una vista superior mide proyección: `ds_3D = sqrt(dx² + dy² + dz²)` y `ds_XY = sqrt(dx² + dy²)`. Aplanar puede reducir esta diferencia, siempre que no estire ni comprima apreciablemente la pieza. Hay que decidir y documentar si el resultado es longitud proyectada o longitud bajo un apoyo definido.

## Revisión concreta del PowerPoint

Referencia visual: [diapositivas 1–2](../../docs/presentation_summary.md). Se mantiene cámara arriba y backlight abajo; estos son los puntos a resolver antes del diseño final.

| Elemento del montaje | Dónde puede fallar | Propuesta de estudio |
| --- | --- | --- |
| Columna y brazo en voladizo | Vibración, giro de uniones y variación de distancia al colocar la pieza | Base rígida, cartelas y brazo corto; anclar cámara a estructura fija, nunca al conjunto pesado |
| Base de 300 × 300 mm | Puede faltar espacio para báscula, panel, puentes y manos del operario | Dibujar envolventes reales; no dar esa base por validada |
| Cámara con sensor rolling shutter | Movimiento durante la lectura puede deformar la imagen | Capturar una vez retirada la mano y asentada la pieza; comprobar con iluminación real |
| Panel bajo la placa | Una placa o soporte opaco interrumpe la silueta; 200 mm útiles exactos no dejan margen | Verificar área emisora, holguras y accesibilidad antes de comprar |
| Luz doméstica económica | Uniformidad, bandas por parpadeo y cambios con temperatura/exposición | Apta para ensayo inicial si pasa prueba de bordes; no asumir equivalencia metrológica con panel industrial |
| PP sobre backlight | Translucidez, refracción y bordes dobles pueden mover el contorno | Probar piezas reales y exposición; una silueta no está garantizada por el material nominal |
| Colada vertical | Puede ocultar el nacimiento de la espiral, cambiar la región visible y complicar apoyo | Conservarla en la imagen y definir región excluida/medible; no inventar geometría oculta |
| Ranura en metacrilato | Puede imponer la forma nominal, ocultar bordes o introducir líneas ópticas propias | Empezar con placa plana y localización holgada; comparar antes/después de cualquier sujeción |
| Todo encima de la báscula | Precarga, excentricidad, calor del panel y tensión del cable alteran la lectura | Pesar el conjunto y probar incrementos pequeños sobre esa tara; estudiar panel independiente |

Una ranura no equivale automáticamente a aplanar: una ranura abierta puede localizar lateralmente y dejar el alabeo intacto. Una tapa o presión sí puede bajar la pieza, pero debe ensayarse con PP caliente para no cambiar sus dimensiones. Si la colada apunta hacia abajo, el alojamiento necesita profundidad y espacio libre frente al panel; si apunta hacia arriba, hay que resolver oclusión y acceso. La orientación aún no está seleccionada.

## Dos configuraciones mecánicas a comparar

### A. Apilado sencillo, cercano al PowerPoint

`pieza + placa/soporte + backlight → plato de báscula → mesa`

Es la primera maqueta más directa si la suma real queda cómodamente por debajo de 3 kg. La cámara y columna se apoyan en estructura fija separada de la carga. El panel necesita cable flexible con holgura y alivio de tensión: ningún contacto lateral debe desviar parte del peso fuera del plato. La tara resta una lectura, **no aumenta la capacidad**. Validar errores con las piezas cerca del centro y desplazadas.

### B. Backlight fijo y soporte ligero sobre la báscula

`pieza + placa transparente + puente de carga → plato de báscula`

`backlight + sus cables + columna de cámara → estructura fija`

La placa debe quedar encima del panel sin tocarlo. Un puente periférico conectado exclusivamente al plato puede rodear el panel; otra posibilidad es desplazar la báscula fuera del paso de luz. Ambas necesitan cálculo de rigidez y excentricidad. **No es un diseño mecánico resuelto**: una placa grande conectada por un brazo lateral puede pesar poco y aun así provocar errores o sobrecarga por momento.

La ventaja es eliminar la masa del panel y sus fuerzas de cableado de la medida. La PCE de 1,1 kg pasa a ser posible solo si placa + puente + pieza quedan dentro de capacidad con margen. Como cálculo de orden de magnitud, PMMA de densidad 1,19 g/cm³ pesa **238 g en 200 × 200 × 5 mm**, **476 g en 200 × 200 × 10 mm**, y **1.071 g en 300 × 300 × 10 mm**. Faltan puente y herrajes; el espesor no se selecciona por masa sin comprobar rigidez. [Ficha PLEXIGLAS](../components/datasheets/PLEXIGLAS_GS_XT.pdf).

## Pieza recién desmoldeada: consecuencia para el hardware

Se mantiene la inspección inmediata solicitada. El riesgo no es la velocidad de cálculo del PC: es que una pieza caliente sigue cambiando de tamaño, calienta el apoyo y puede producir deriva aparente de peso por convección. No se ha cuantificado ese efecto para esta celda. El [manual VIBRA](https://www.vibra.co.jp/files/page_options/global/products/detail/61/enProducts_fileUp03/enProducts_fileUp03.pdf) explica la influencia de diferencias térmicas en el pesaje; no se transfieren cifras de otro instrumento a esta báscula.

PLEXIGLAS publica temperaturas máximas de servicio permanente del orden de **80 °C para GS y 70 °C para XT**. No son la temperatura de la pieza ni un umbral universal de contacto breve. Antes de mecanizar una ranura, medir temperatura real de contacto y elegir material/espesor adecuados. El coeficiente de expansión publicado para 0–50 °C, aproximadamente 0,07 mm/(m·K), implica **0,28 mm en 200 mm para un cambio uniforme de 20 K dentro de ese rango**: cálculo ilustrativo que desaconseja tratar una ranura caliente como patrón dimensional invariable. [Datos del fabricante](https://www.plexiglas.de/files/plexiglas-content/pdf/technische-informationen/211-1-PLEXIGLAS-GS-XT-EN.pdf).

Una cubierta sencilla frente a corrientes, separación térmica del panel y contacto limitado pueden estudiarse sin convertir el proceso en una espera larga. Hay que comprobar que esos elementos no añadan oclusiones, fuerzas parásitas ni calentamiento acumulativo.

## Soluciones existentes y qué aportan

- **Comparadores 2D industriales, como KEYENCE IM-8000:** confirman que la medida automatizada de contornos es una arquitectura comercial establecida. No sustituyen directamente esta celda: falta pesaje integrado, tratamiento de la colada y equivalencia de condiciones térmicas; no se obtuvo un precio comparable. [Fabricante](https://www.keyence.com/products/measure-sys/image-measure/im-8000/).
- **Cámara industrial + óptica convencional + backlight:** mantiene flexibilidad y permite repartir presupuesto entre apoyo, luz y calibración. Es la ruta priorizada para Machina.
- **Telecentricidad:** aborda variación de magnificación con altura, pero no recupera el recorrido 3D oculto. La propuesta de gran FOV recibida queda descartada por coste/volumen; sus 46,7 kg siguen pendientes de modelo verificable. No se generaliza ese peso a todas las telecéntricas.
- **3D o varias vistas:** útiles si fuese imprescindible la longitud espacial libre, pero añaden coste e integración. No se justifican todavía con el requisito orientativo actual.

## Pruebas mínimas para elegir hardware

1. **Geometría y apoyo:** imágenes de una misma pieza sin mover y tras al menos 20 recolocaciones; comparar apoyo libre, localización holgada y sujeción ligera. No confundir repetibilidad de una pieza fría con comportamiento de una caliente.
2. **Sensibilidad a altura:** patrón con ancho/recorrido conocidos a alturas controladas; comprobar escala y bordes en centro y extremos del campo, sin usar el mismo patrón solo para ajustar y validar.
3. **Pesaje real:** pequeñas masas conocidas añadidas sobre la precarga final, repetición de colocaciones y posiciones; repetir con panel encendido, cables colocados y condición térmica representativa. Registrar retorno a cero y datos seriales.
4. **Variación detectable:** comparar dispersión de medida con diferencias entre piezas de interés. Solo después fijar los límites de longitud, ancho y peso; mantener 0,1 mm como referencia inicial, no resultado garantizado.

Estos son ensayos propuestos; sus resultados se guardarán en [validation/reports](../../validation/reports/README.md). No se han ejecutado.

## Consultas técnicas preparadas

No se han enviado mensajes a proveedores.

- **STEMMER/Computar:** confirmar V3522-MPZ para BFS-U3-200S6M-C, campo útil de 150 y 200 mm de lado, distancia desde frontal, distorsión a esa magnificación, apertura recomendada y oferta vigente. Solicitar prueba con pieza y colada antes de fijar el soporte.
- **Expondo/Steinberg:** repetibilidad y linealidad de SBS-LW-1030 bajo aproximadamente 2 kg de precarga, efecto de carga excéntrica, pinout y cable, formato/frecuencia de trama, identificación de estabilidad y disponibilidad de documentación de calibración.
- **PCE:** confirmar conexión y parámetros seriales del equipo suministrado, accesorio/cable exactos, temperatura de validez de especificaciones y precio total entregado. El transporte difiere entre páginas consultadas.

Los [cálculos reproducibles](optics_tradeoffs.py) permiten revisar distancias, muestreo, altura y masas cuando haya medidas reales. La recomendación actual sigue siendo **35 mm + apoyo controlado + prueba de báscula económica**, con decisión entre apilado y panel independiente después de medir la carga real.
