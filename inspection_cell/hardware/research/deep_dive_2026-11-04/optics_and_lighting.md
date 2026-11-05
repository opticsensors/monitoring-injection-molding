# Óptica e iluminación: límites que no desaparecen al binarizar

Consulta: 2026-11-04. Complementa los [cálculos iniciales](../vision.md). No se ha ensayado la cámara con las piezas.

## Focal y altura

Se mantiene la **35 mm como candidata de prueba**, no selección cerrada. Para el sensor FLIR de 13,1328 × 8,7552 mm y un cuadrado de 200 mm, la estimación de lente delgada da 834,5 mm desde el plano principal; para 150 mm, 634,6 mm. No son distancias frontales certificadas. La 75 mm resulta demasiado larga para el encuadre conservador y la altura deseada.

El FOV debe incluir la espiral real, localizadores y margen de colocación. El script ideal no incluye toda la geometría de colada y salientes. Tampoco se puede dimensionar un panel solo por el ancho horizontal del sensor: un cuadrado de 200 mm utiliza su lado de 3648 píxeles.

## Plano de calibración

Para una altura uniforme `h` hacia una cámara a distancia `Z` del plano calibrado, el modelo pinhole da una escala relativa `Z/(Z-h)`. A `Z=800 mm`, una elevación de 2 mm introduce aproximadamente **1,28 mm sobre 510,51 mm** y **0,010 mm sobre 4 mm**. Esto ilustra por qué longitud y ancho no comparten un error absoluto general.

Incluso una pieza apoyada tiene espesor. Si el hilo fuese circular, su eje estaría por encima del apoyo; la sección todavía no está confirmada. Un patrón situado sobre el suelo no identifica automáticamente el plano efectivo del borde del hilo. Hay que comparar referencias a alturas conocidas y elegir una condición de medida reproducible.

La corrección de distorsión y una homografía plana no eliminan una altura diferente en cada tramo. Una referencia en la imagen ayuda a observar deriva, pero no corrige por sí sola todas las alturas de la pieza.

[Calib.io](https://calib.io/blogs/knowledge-base/calibration-best-practices) recomienda calibrar con enfoque y abertura de trabajo, cubrir el campo y usar vistas inclinadas para identificar los parámetros intrínsecos. Un error de reproyección bajo **no demuestra exactitud dimensional independiente**. Para Machina: separar calibración de cámara, escala/plano de trabajo y verificación con otra referencia. Un tablero impreso puede ayudar a explorar distorsión; sin comprobar tamaño y planitud no es un patrón para afirmar ±0,1 mm.

## Enfoque, abertura y difracción

[Edmund Optics](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/depth-of-field-and-depth-of-focus/) define profundidad de campo junto a una resolución y contraste, y explica el intercambio entre cerrar diafragma y difracción. Una imagen aparentemente enfocada puede seguir cambiando de escala con la altura.

El diámetro de Airy es `2,44 λ N` en imagen para el modelo ideal; para distancia finita se puede aproximar el número f efectivo con `N(1+m)` si la magnificación pupilar es uno. **Su diámetro no es el error de medida**: un borde puede localizarse por debajo del ancho de su transición si el perfil es estable. Tampoco los «20 MP» garantizan contraste útil a todas las frecuencias y aperturas. Fuente de la relación: [Edmund, Airy disk](https://www.edmundoptics.com.sg/knowledge-center/application-notes/imaging/limitations-on-resolution-and-contrast-the-airy-disk/).

Propuesta de ensayo: comparar aberturas próximas a f/4, f/5,6 y f/8, variando exposición para evitar saturación, con referencias en centro y esquinas y a varias alturas. No fijar f/16 simplemente para obtener más profundidad. El enfoque a una altura intermedia puede reducir desenfoque, pero no el error de perspectiva.

## Backlight: difuso y semicollimado no son equivalentes

[Opto Engineering](https://www.opto-e.com/en/products/ltclhp-series) muestra que la iluminación difusa alrededor de superficies redondas puede modificar el contorno aparente. Sus iluminadores telecéntricos son una familia especializada; su rendimiento no se traslada a cualquier panel.

[TPL CSBACK](https://www.tpl-vision.com/overview/backlights/collimated-csback/) ofrece iluminación **semicollimada** compatible también con objetivos C-mount convencionales. El [PDF archivado](sources/TPL_CSBACK_Product_Profile_EN.pdf), pp. 2 y 5–6, identifica reducción angular de intensidad, variantes de color y control a 24 V. El modelo 2020 tiene área luminosa 204 × 204 mm, exterior 214 × 214 mm, grosor 21,1 mm y consumo nominal 45 W. No se ha confirmado precio ni masa. La temperatura de operación especificada es 0–40 °C: no es una autorización para apoyar una pieza caliente sobre el difusor.

**Inferencia para Machina:** comparar un panel difuso con uno semicollimado usando la misma pieza y exposición normalizada. El segundo puede ayudar a definir el borde, pero **no hace telecéntrica la lente** ni elimina deformaciones. Reservar espacio entre panel y plataforma y evitar contacto caliente directo con el panel.

## Materiales y exposición

Un polímero blanco translúcido puede transmitir y dispersar luz; uno transparente puede mostrar bordes por refracción en vez de una silueta negra. No asumir que un umbral sirve para todos los materiales. Primero ensayar luz blanca y, si el borde lo requiere, comparar bandas visibles; no prescribir un color universal sin muestra.

Guardar imágenes en gris sin recorte de altas luces, exposición y ganancia fijas por receta, y perfiles transversales de zonas conocidas. La binarización puede servir para localizar la espiral; para anchuras, estudiar bordes en gris. [MVTec](sources/MVTec_1D_Measuring_26_05.pdf), pp. 9–11, describe proyección/promedio de perfiles y extremos de derivada con localización subpíxel. Esto orienta el ensayo; no implica comprar HALCON ni implementar ahora el algoritmo.

El rolling shutter de la cámara propuesta puede servir con pieza y cámara inmóviles. **Global reset no equivale a global shutter**: [Basler](https://docs.baslerweb.com/electronic-shutter-types) explica la exposición desigual por filas si se usa global reset con iluminación continua. Confirmar los modos y señales de la FLIR concreta antes de elegir flash. Un panel regulado por PWM también merece una prueba de bandas y variación entre capturas.

## Evidencia experimental sobre el borde

Harmatys et al., 2021, [DOI 10.3390/s21072509](https://pubmed.ncbi.nlm.nih.gov/33916771/), estudiaron intensidad de backlight en una máquina óptica ZEISS, con agujeros de 5,5 mm y círculos oscuros de 0,254 mm sobre vidrio, con 30 repeticiones por condición. Al aumentar la iluminación observaron desplazamiento de bordes, crecimiento del diámetro interior y reducción del exterior; algunas posiciones de centros cambiaban menos por compensación geométrica. El intervalo de iluminación más estable dependía del ensayo.

El [artículo completo archivado en XML JATS](sources/Harmatys_2021_backlight_uncertainty.xml) respalda ensayar intensidad y tipo de borde. Sus desplazamientos del orden de micras **no son una previsión para nuestro polímero, FOV ni cámara**. Consecuencia propia: un error de umbral puede cambiar dos bordes de ancho en sentidos opuestos mientras el eje apenas cambia; un error de escala, en cambio, afecta proporcionalmente a toda la longitud. No hay un único «error general de cámara» que resuma ambos.

## Telecéntrica relatada: coincidencia, no identificación confirmada

La ficha [Vision Datum BTL-0.055X-465-H1(LM)](https://www.visiondatum.com/en/productview/1360.html) publica 46,7 kg y 651,5 mm de longitud, coincidentes aproximadamente con lo relatado por el usuario. **No se ha probado que sea el modelo de STEMMER**. Publica magnificación 0,055× y WD 465 ± 6 mm. Con el área activa de nuestra FLIR, el FOV calculado sería 238,8 × 159,2 mm: no cubre un cuadrado de 200 mm. Los ejemplos de FOV de una ficha dependen del sensor elegido. Mantener descartada esta ruta en la fase actual, sin atribuir 46,7 kg a todas las lentes telecéntricas.

La [comparación de paneles y costes](lighting_candidates.md) separa iluminación industrial, colimación y una maqueta económica. La elección necesita imágenes con nuestras muestras.

## Deriva del conjunto

Nimura y Adamczyk, [2022, DOI 10.3390/s22249997](https://www.mdpi.com/1424-8220/22/24/9997), diseñan y verifican un banco para separar deriva de cámara y movimiento del soporte bajo temperatura. Se revisaron método, montaje, resultados y conclusiones del [artículo completo XML](sources/Nimura_2022_camera_thermal_test_stand.xml). Incluso con un bastidor de baja expansión evalúan el movimiento de la referencia y del soporte por separado.

No trasladamos su cifra de píxeles ni proponemos fabricar su banco de invar. Para Machina basta comenzar con una referencia estable durante encendido y colocación, medir distancias además de posición y comprobar el brazo de aluminio. Un desplazamiento rígido de toda la imagen no equivale por sí solo a cambio de longitud; una variación de escala, inclinación o enfoque sí puede afectar la medida. Registrar deriva antes de intentar corregirla con un factor genérico.
