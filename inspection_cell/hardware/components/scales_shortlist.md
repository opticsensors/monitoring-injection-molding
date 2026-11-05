# Básculas económicas para la celda

Consulta: **2026-11-04**. Límite del usuario: **300 € con IVA y conexión al PC**. Pieza estimada ≤100 g; posible precarga de unos 2 kg todavía sin medir. Prioridad: 0,01 g; 0,1 g se considera justo. Ninguna candidata está validada ni comprada.

## Comparativa

| Modelo | Capacidad / división | Repetibilidad / linealidad publicadas | Plato | Precio observado / fiscalidad | Encaje |
| --- | --- | --- | --- | ---: | --- |
| **Steinberg SBS-LW-1030** | 3.000 g / 0,01 g | No encontradas como especificaciones separadas | 196 × 160 mm | **178,00 €** | Comparar con U.S. Solid 5 kg si se mantiene el apilado |
| **U.S. Solid USS-DBS28-50** | 5.000 g / 0,01 g | **Manual ±0,03 g / ±0,03 g**; web rep. ±0,02 g | 143 × 192 mm | **105–119 € observados**, entrega/IVA España por cerrar | Más margen de carga, USB y RS-232; no validada |
| U.S. Solid USS-DBS61-32 | 3.200 g / 0,01 g | Web ±0,02 g / ±0,03 g; revisión por confirmar | 128 × 157 mm | **86,57 €**, entrega/IVA España por cerrar | RS-232; plato pequeño |
| **PCE-BSK 1100** | 1.100 g / 0,01 g | ±0,02 g / ±0,03 g en manual | Ø130 mm | **183,80 €** | Requiere aligerar soporte y sacar el backlight de la carga |
| PCE-BSK 5100 | 5.100 g / 0,1 g | ±0,2 g / ±0,3 g en manual | 160 × 160 mm | **201,95 €** | Capacidad suficiente, prestaciones poco atractivas para diferencias pequeñas |

En Steinberg y PCE, los importes de esta tabla incluyen IVA del escenario español consultado. **Los precios U.S. Solid no se han confirmado entregados ni con el tratamiento fiscal de la compra prevista.** No compararlos como presupuestos finales equivalentes.

Fuentes U.S. Solid: [5 kg](https://ussolid.de/u-s-solid-prazisionswaage-digitale-laborwaage-5000g-x-0-01-g-rs232-usb-schnittstelle-ac-dc-netzteil/) y [3,2 kg](https://ussolid.de/u-s-solid-prazisionswaage-digitale-laborwaage-3200g-x-0-01-g-rs232-schnittstelle-ac-dc-netzteil/). La [ampliación](../research/deep_dive_2026-11-04/weighing.md) conserva precios discrepantes, alcance de envío y manuales.

Fuentes de producto: [Steinberg/Expondo](https://www.expondo.es/steinberg-systems-bascula-de-precision-digital-de-0-2-a-3000-g-0-01-g-196-x-160-mm-10031315), [PCE 1100](https://www.pce-instruments.com/espanol/balanza/balanza/balanza-de-precision-pce-instruments-balanza-de-precisi_n-pce-bsk-1100-det_5935470.htm?_list=qr.art&_listpos=1717), [PCE 5100](https://www.pce-instruments.com/espanol/balanza/balanza/balanza-digital-pce-instruments-balanza-digital-pce-bsk-5100-det_5980147.htm). Especificaciones contrastadas con los manuales locales enlazados abajo.

Una lectura de 0,01 g **no demuestra detectar de forma fiable un incremento de 0,01 g**. La repetibilidad del fabricante tampoco se interpreta automáticamente como una desviación típica: falta conocer su método. Verificar con incrementos conocidos sobre la precarga real, no solo alrededor de cero.

## Coste conectado al PC

| Modelo | Cálculo de presupuesto | Qué falta cerrar |
| --- | --- | --- |
| SBS-LW-1030 | 178 € + **reserva estimada de 40–60 €** para adaptador y cable = **218–238 €**; página anuncia transporte gratuito | La reserva no es una oferta de accesorios compatibles. Quedan 62–82 € de margen hasta 300 € |
| U.S. Solid 5 / 3,2 kg | Sin total entregado verificable todavía | Confirmar envío España, fiscalidad, cable/USB/controlador o adaptador. No suponer que 105 € es el total |
| PCE-BSK 1100 | `(151,90 + 32,90 + 8,00) × 1,21` = **233,29 €**, escenario con adaptador y un transporte | Confirmar IVA de accesorios, cable/pinout y transporte conjunto |
| PCE-BSK 5100 | Con adaptador de 32,90 € netos y transporte de 8–9 € netos: **251,44–252,65 €** con IVA | Mismo adaptador solo si compatible; transporte no confirmado |

El accesorio RS232–USB de 32,90 € figura en la página PCE 1100, con precios accesorios tratados como netos para esta estimación. No se ha hecho pedido ni validado una cesta de compra. Las páginas PCE devuelven transportes distintos: se observaron 8 y 9 € netos, y [otra ficha de 5100](https://www.pce-instruments.com/espanol/balanza/balanza/balanza-de-precision-pce-instruments-balanza-de-precisi_n-pce-bsk-5100-det_5935472.htm) muestra 90 €. Con 90 € el total sería **350,66 €** y excedería presupuesto. Conservar esta discrepancia; no dar los escenarios favorables por ofertas cerradas.

No se incluye certificado externo, masas patrón ni fabricación del soporte en estas cifras. Su disponibilidad/coste debe tratarse aparte en la BOM. El software comercial PCE no se presupone necesario para una futura aplicación serial propia; verificarlo con el equipo recibido.

## Automatización: evidencia y pendientes

**Steinberg:** el [manual descargado](datasheets/SBS-LW-1030_manual.pdf), página 13 del PDF —castellano en la 48—, documenta salida al pulsar, automática estable y continua. Permite 1200–9600 baudios, con 9600 por defecto y opción de 8 bits sin paridad. Faltan pinout, bits de parada, formato de trama, frecuencia efectiva e identificación de estabilidad. El modo continuo puede servir para observar presencia y retirada; ensayarlo antes de diseñar el disparo.

**U.S. Solid 5 kg:** [manual específico](../research/deep_dive_2026-11-04/sources/USS_DBS28_61_51_5kg_manual.pdf), PDF p5 / impresa p7: RS-232 a 9600, 8N1, cable cruzado 2–3 y masa 5, envío continuo `C5-0`. Faltan ritmo, bandera de estabilidad y USB exacto; el manual de otra variante no los sustituye.

**PCE:** el [manual español actual](datasheets/PCE-BSK_series_ES.pdf), páginas 8–9, documenta envío por tecla, consulta, continuo y al estabilizarse, además de comandos de consulta/tara. Esto respalda la automatización sin pulsar en cada pieza. Confirmar los parámetros eléctricos/seriales y la trama del modelo suministrado; este estudio no implementa el controlador.

No se deduce de «RS232» que cualquier cable USB funcione. Hay que concretar adaptador, cableado y conector. Una indicación «estable» tampoco garantiza que un peso caliente carezca de deriva.

## Discrepancias resueltas o conservadas

- **SBS:** el texto comercial usa «precisión»; la tabla del manual dice división de 0,01 g. Se registra como división, sin inventar repetibilidad o linealidad.
- **PCE 5100:** el filtro comercial puede mostrar 6000 g; tabla y manual especifican **5100 g**, valor utilizado aquí.
- **PCE temperatura:** el [manual italiano anterior](datasheets/PCE-BSK_series_IT.pdf) pone 17,5–22,5 °C. El español enlazado actualmente y la web coinciden en **0–40 °C de funcionamiento**. Priorizar el actual; confirmar condiciones de validez metrológica. Esto no autoriza poner una pieza a 100 °C sobre el plato.
- **PCE masa del equipo:** manual y web difieren; no usar ese dato para dimensionar hasta confirmar. La capacidad de pesaje sí coincide.

## Selección provisional

**Comparar U.S. Solid de 5 kg con SBS-LW-1030 de 3 kg si se mantienen unos 2 kg de carga**. La primera aporta más margen y especificaciones, pero entrega a España y revisión siguen pendientes; la segunda tiene precio español y manual de configuración, sin repetibilidad separada. **Comparar PCE-BSK 1100 si se logra una plataforma ligera**, por disponer de especificaciones más explícitas. No elegir PCE-BSK 5100 como solución equivalente a 0,01 g: sacrifica justamente la sensibilidad buscada.

Si se logra que pieza y soporte tengan una masa total muy baja, la ampliación estudia también [U.S. Solid de 300 g / 0,001 g](../research/deep_dive_2026-11-04/weighing.md#vía-secundaria-1-mg-si-se-consigue-una-plataforma-muy-ligera) y [Nahita KBD005 con canal español](../research/deep_dive_2026-11-04/weighing.md#cribado-adicional-de-1-mg-con-proveedor-español). Tienen mejor repetibilidad publicada, pero capacidad, campana, coste conectado y automatización requieren comprobación. La Nahita sola ya alcanza 296,75 € con IVA calculado. Ninguna sustituye el apilado de 2 kg.

Las KERN/Adam del PowerPoint se mantienen como referencias históricas en [candidatos](candidates.md). Que sean más caras no demuestra que sean necesarias; tampoco que la alternativa de 178 € sea metrológicamente equivalente.
