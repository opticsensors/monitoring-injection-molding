# Pesaje económico: ampliación y condiciones de validez

Consulta: 2026-11-04. Véase también la [primera comparativa](../../components/scales_shortlist.md). **No se ha comprado ni ensayado ninguna candidata.** La preferencia del usuario sigue siendo 0,01 g, con presupuesto máximo de 300 € incluyendo IVA y conexión al PC.

## Medios existentes y búsqueda de una báscula nueva

El usuario ha aclarado que las básculas del laboratorio **no tienen USB ni RS-232** y no conoce sus modelos. Ha pedido continuar la búsqueda sin depender de ello. Se usarían para comprobaciones manuales; no volver a pedir el modelo como condición para avanzar ni proponer reutilización serial como si siguiese abierta. Al registrar pruebas, anotar división/capacidad visibles y condiciones conocidas; no asumir que son referencias de exactitud.

## Nuevas candidatas con documentación del fabricante

| Candidata | Capacidad / división | Repetibilidad / linealidad publicadas | Conexión | Precio observado y limitación |
| --- | --- | --- | --- | --- |
| [U.S. Solid USS-DBS61-32](https://ussolid.de/u-s-solid-prazisionswaage-digitale-laborwaage-3200g-x-0-01-g-rs232-schnittstelle-ac-dc-netzteil/), SKU JFDBS00061-3200G | 3200 g / 0,01 g | ±0,02 g / ±0,03 g | RS-232 | 86,57 € en tienda alemana; IVA aplicable, transporte a España y adaptador pendientes |
| [U.S. Solid USS-DBS28-50](https://ussolid.de/u-s-solid-prazisionswaage-digitale-laborwaage-5000g-x-0-01-g-rs232-usb-schnittstelle-ac-dc-netzteil/), SKU JFDBS00028-5KG | 5000 g / 0,01 g | Web ±0,02 g / ±0,03 g; **manual específico de 5 kg: ±0,03 g / ±0,03 g** | USB y RS-232; modo serie continuo documentado | 105,37 € en lectura directa de página/JSON-LD; el buscador mostró 115,43 € y otra lectura 119 €. Confirmar precio final; no sumar automáticamente un IVA supuesto |
| [U.S. Solid USS-DBS28-30](https://ussolid.com/products/u-s-solid-precision-balance-digital-lab-scale-600g-1kg-2kg-3kg-x-0-01g-rs232-and-usb-interface-ac-dc-power-ways-html), variante 3000 g | 3000 g / 0,01 g | Web ±0,02 g / ±0,03 g; manual de la familia indica repetibilidad ±0,03 g | USB y RS-232 anunciados | 103,15 USD en datos públicos de producto de tienda estadounidense; **no es precio entregado en España ni conversión a euros** |

La ficha de 3,2 kg indica plato 128 × 157 mm; la de 5 kg, 143 × 192 mm. Son más pequeños que el apoyo conservador de 200 × 200 mm. Un puente ampliado exige comprobar momentos/excentricidad, además de capacidad. Ambas fichas anuncian estabilización de 1,5 s: ese dato no incluye nuestro soporte caliente ni la mesa real.

Fuentes adicionales para la variante de 5 kg: [ficha estadounidense del fabricante](https://ussolid.com/products/u-s-solid-precision-balance-digital-lab-scale-5kg-x-0-01g-rs232-and-usb-interface-html). Describe alimentación AC, sin pantalla protectora ni masa de calibración incluida; la ficha alemana mezcla afirmaciones distintas sobre baterías y protector. **Exigir confirmación de variante y contenido.** La política alemana consultada describe envío a Alemania, no garantiza España: [condiciones](https://ussolid.de/versand-und-rucksendungen/).

## Qué falta resolver en U.S. Solid

Se localizó después el **[manual oficial específico de 5 kg](sources/USS_DBS28_61_51_5kg_manual.pdf)**, enlazado por el fabricante. PDF p. 4 / impresa p. 3: USS-DBS28-50, plato 143 × 192 mm, división 0,01 g, repetibilidad y linealidad ±0,03 g. La repetibilidad discrepa de la web; mantener la cifra más prudente hasta confirmación. Las dimensiones exteriores también discrepan: manual 225 × 220 × 80 mm frente a 200 × 215 × 80 mm en la ficha comercial.

PDF p. 5 / impresa p. 7 confirma **RS-232 a 9600, 8N1**, cable cruzado entre pines 2 y 3 y masa en 5, y modos continuo (`C5-0`) y por pulsación (`C5-2`, botón UNIT). Describe una trama de 14 posiciones con signo, espacio, cifra/unidad y final de línea. No muestra una bandera inequívoca de estabilidad ni el ritmo de actualización. Esto resuelve la existencia de una ruta de lectura automática por RS-232; **no demuestra todavía el funcionamiento del USB ni la compatibilidad de cada revisión entregada**. El manual menciona un programa de terminal; no se ha instalado.

El [manual anterior hasta 3 kg](sources/USS_DBS28_manual.pdf), PDF p. 5 / impresa p. 4, se conserva como referencia de otra familia/revisión, no como sustituto del específico de 5 kg.

Un [usuario que implementó lectura serie](https://github.com/raleighlittles/USS-DBS-Driver) aporta una evidencia práctica interesante para **su USS-DBS28-30**. Sus [notas](https://github.com/raleighlittles/USS-DBS-Driver/blob/main/docs/README.md) describen 9600, 8N1 y tramas ASCII terminadas en CR/LF; observó 17 bytes donde su manual indicaba 14. Su programa convierte la lectura serie en pulsaciones de teclado: eso **no demuestra que el USB de fábrica sea HID**. Es una experiencia con otra unidad/revisión, no prueba de compatibilidad de la actual de 5 kg.

Se conserva el [manual del fabricante archivado por ese usuario](sources/USS_DBS28_30_manual_community_mirror.pdf), indicando la procedencia. Describe modo continuo y por botón y un cableado RS-232 cruzado; comprobarlo en el manual de la unidad suministrada antes de preparar cable. No instalar ni ejecutar el código del repositorio como parte de esta investigación.

Faltan: controlador USB/identificador de dispositivo, frecuencia de salida, bandera de estabilidad o criterio equivalente, comportamiento del cero automático, retorno tras desconexión y repetibilidad con precarga cercana a 2 kg. No se ha demostrado sensibilidad a incrementos de 0,01 g.

## Orden de decisión actualizado

1. Medir manualmente la masa real de pieza y soporte; seguir buscando una báscula nueva conectable sin esperar el modelo de las existentes.
2. **Comparar U.S. Solid 5 kg con Steinberg 3 kg** para un conjunto pesado. U.S. Solid aporta especificaciones de repetibilidad; Steinberg tiene canal español y manual con modos de salida/configuración. Ninguna está validada sobre nuestra precarga.
3. Si una plataforma ligera queda por debajo de 1,1 kg incluyendo pieza, conservar PCE-BSK 1100 como candidata con especificación y soporte documental más claros.
4. No recurrir a PCE-BSK 5100 solo para ganar capacidad si la división de 0,1 g y repetibilidad de 0,2 g no permiten distinguir la variación buscada.

El presupuesto admite investigar alternativas por debajo de 700 €, pero no permite prometer **error ±0,01 g con varios kilos de tara** por el hecho de que la pantalla tenga dos decimales.

## Vía secundaria: 1 mg si se consigue una plataforma muy ligera

Se ha investigado si sacar el panel de la carga permitiría comprar una báscula de menor capacidad y mejor repetibilidad. **No es una sustitución directa del apilado de unos 2 kg.**

La [U.S. Solid USS-DBS46-3](https://ussolid.com/products/u-s-solid-300-x-0-001g-analytical-balance-1-mg-digital-lab-precision-scale-html) anuncia 300 g / 0,001 g, plato Ø90 mm y RS-232, a **133,49 USD** en tienda estadounidense. No es un precio final en España. La web da repetibilidad ±0,002 g y linealidad ±0,003 g; el [manual específico archivado](sources/USS_DBS46_300g_manual.pdf), tabla rasterizada de PDF p4 revisada visualmente, indica **±0,003 g y ±0,004 g**. Conservar la discrepancia. PDF p5 documenta salida continua, 9600 8N1 y cable cruzado 2–3.

La campana del manual mide 174 × 135 × 84 mm; no admite automáticamente el campo conservador ni una colada alta. Hace falta resolver apoyo ampliado, protección de aire y carga excéntrica. Incluso con mejor especificación, no demuestra pesar correctamente una pieza caliente de forma inmediata.

**Inferencia de diseño:** una placa PMMA de 150 × 150 × 2 mm pesaría unos 53,6 g, frente a 238 g para 200 × 200 × 5 mm. Son masas geométricas, no espesores aprobados térmica/mecánicamente. Si pieza, placa y puente quedan con margen por debajo de 300 g, esta clase de báscula merece una prueba. No fabricar un soporte insuficiente solo para encajar en ella.

Como contraste, la [USS-DBS63-10](https://ussolid.com/products/u-s-solid-1-mg-analytical-balance-density-and-dynamic-weighing-0-001-g-x-1000-g-html) de 1 kg / 0,001 g figura a 779 USD; no resuelve el presupuesto actual. Este cribado no demuestra que no exista otra alternativa, pero evita asumir que aumentar simultáneamente capacidad y sensibilidad será barato.

## Cribado adicional de 1 mg con proveedor español

La [Nahita-Blue KBD005, serie 5173](https://www.auxilab.es/es/productos-laboratorio/balanza-de-precision-300g-0-001g-serie-5173/) figura a **245,25 € sin IVA**, con stock anunciado el 2026-11-04. Son **296,75 € con un 21 % de IVA**, antes de transporte y conexión: apenas deja margen en el máximo de 300 €. No es una oferta final entregada.

La [ficha archivada](sources/Nahita_5173_datasheet.pdf), p2 revisada visualmente, declara 300 g / 0,001 g, repetibilidad y linealidad ±0,002 g, plato Ø90 mm, USB/RS-232 y gancho inferior. Son prestaciones publicadas, no ensayadas con un puente o pieza caliente.

El [manual enlazado por el proveedor](sources/Nahita_5173_manual.pdf), PDF pp4–10, usa referencias antiguas 55173210/55173230. Documenta envío pulsando MENU, baudios configurables y cable cruzado 2–3/5–5, pero **no se ha localizado modo continuo ni comando de consulta automática** en esos apartados. El listado de contenido no menciona cable de datos; tampoco se aclaran controlador USB o software. Confirmar revisión y automatización antes de considerarla apta para detectar colocación sin pulsaciones.

Queda como alternativa secundaria si se aligera el conjunto y se resuelven coste conectado y lectura automática. El gancho inferior abre otra disposición mecánica, pero no elimina capacidad, oscilaciones, oclusión de cámara ni exigencia de altura; no se recomienda rehacer la celda alrededor de él sin una ventaja medida.

Se cribaron también [KBD027 de 300 g](https://www.auxilab.es/es/productos-laboratorio/balanza-de-precision-300g-0-001g-serie-5163/) y [KBD028 de 500 g](https://www.auxilab.es/es/productos-laboratorio/balanza-de-precision-500g-0-001g-serie-5163/): precios observados 268,98/289,28 € sin IVA, equivalentes a **325,47/350,03 € con 21 %**, ya por encima del máximo antes de conexión. No se presentan como alternativas que cumplan el presupuesto.

Otra trampa de comparación: la [U.S. Solid USS-DBS3-3](https://ussolid.com/products/300-x-0-001g-analytical-balance-1-mg-digital-lab-precision-scale-html) anuncia 300 g / 0,001 g y 135,90 USD, pero su tabla especifica **sin interfaz**. No confundirla con USS-DBS46-3 ni comprar solo por capacidad y decimales.

## Precarga, cables, calor y estática

La tara resta un número; no descarga el sensor. Una fuerza vertical de apenas **98 µN** equivale a 0,01 g bajo gravedad estándar. Un cable del panel, un apoyo que roce la estructura o una colada que toque un localizador fijo pueden alterar la lectura. El panel fijo elimina de la carga tanto su masa como su cable, a cambio de necesitar un puente mecánico sin contactos parásitos.

El [manual A&D AD-4212D](sources/AD4212D_system_weighing_manual.pdf), pp. 16 y 44, explica efectos de estática y controles de entorno/apoyo. Su escala de prestaciones es distinta: no se extrapola una magnitud de error a nuestras candidatas. **Vidrio también puede cargarse**. Poner a tierra la estructura no garantiza neutralizar la carga de una pieza aislante. Primero diagnosticar mediante ensayos; no añadir un ionizador al presupuesto sin necesidad demostrada.

La guía [EURAMET cg-18 v4, 2015](https://iris.inrim.it/handle/11696/72070) distingue comprobaciones de repetibilidad, indicación y excentricidad. Se usa como referencia metodológica; nuestro protocolo preliminar no equivale a una calibración acreditada. El PDF pudo leerse por la herramienta web, pero su descarga directa respondió 403 y **no hay copia local**.

[NISTIR 6969, edición 2014 revisada en 2015](sources/NISTIR_6969_2014_rev2015.pdf), GMP 10, pp. 24–29 del PDF, describe convección por desequilibrio térmico, deriva, manipulación y estática. Sus ejemplos de masas patrón **no predicen el error de una espiral caliente**. La consecuencia aquí es ensayar evolución caliente/fría y calentamiento del apoyo; no imponer 24 horas de espera de un procedimiento de calibración al ciclo de producción solicitado.

La [foto trasera del fabricante para SBS-LW-1030](https://assets.expondo.com/asset/product_photos/10031315_photo_4?twic=v1/contain=1500x1500) se ha inspeccionado: muestra conector D-sub macho de nueve contactos y alimentación DC 12 V / 1 A. Confirma la forma del conector de la unidad fotografiada, **no su pinout ni el protocolo**. La etiqueta identifica 3 kg, división 0,01 g y carga mínima 0,2 g; esta última no es una incertidumbre ni demuestra detección de incrementos sobre tara.

## Por qué no recomendar todavía una célula + HX711 como ahorro

Ejemplo calculado, **no especificación de una célula seleccionada**: con 3 kg de fondo de escala, sensibilidad 2 mV/V y excitación de 5 V, la señal cambia 3,33 µV/g. Los 50 nV RMS a 10 muestras/s indicados por la ficha de AVIA para HX711 equivaldrían por sí solos a **0,015 g RMS**; 90 nV a 80 muestras/s, a 0,027 g. Con 5 kg serían 0,025 y 0,045 g. Faltan además célula, mecánica, temperatura y creep. Fuente: [ficha AVIA distribuida por LCSC](https://datasheet.lcsc.com/lcsc/Avia-Semicon-Xiamen-HX711_C43656.pdf), tabla eléctrica; descarga local fallida, texto consultado en web.

Promediar puede reducir ruido aleatorio, pero añade tiempo y no elimina deriva, histéresis ni fuerzas externas. Los 24 bits nominales del ADC no son 24 bits útiles de medida. Una célula propia podría facilitar el apoyo transparente, pero debe compararse el coste del montaje y validación con una báscula completa de alrededor de 100–200 €. No se descarta como investigación futura; no es el primer ahorro recomendado.
