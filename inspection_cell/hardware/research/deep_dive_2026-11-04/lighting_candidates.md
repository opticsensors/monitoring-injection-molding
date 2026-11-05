# Paneles de iluminación: coste, carga y prueba antes de compra

Consulta: 2026-11-04. Precios observados, no ofertas entregadas. El límite de 300 € se refiere a la báscula; el usuario no ha fijado presupuesto total de celda. No se ha comprado ni solicitado préstamo.

## Comparación útil

| Panel / fuente | Área útil y exterior | Masa / potencia publicadas | Precio observado | Lectura para Machina |
| --- | --- | --- | --- | --- |
| [Effilux blanco, Edmund #22-098](https://www.edmundoptics.es/p/white-200-x-200-high-power-led-backlight/49405/), referencia del PPT | 200 × 200; exterior 239 × 239 mm | **1900 g**; alimentación/control según variante | **765 € sin IVA**, 925,65 € aplicando 21 %, antes de fuente/cable | La estimación de unos 2 kg es razonable para este panel. Uniformidad anunciada >90 % no garantiza estabilidad del borde |
| [VA-BLBL2-211x200W](https://va-imaging.com/products/bottom-lit-backlight-industrial-illumination-va-blbl2) | 211 × 200; 225 × 214 × 18 mm | Web 770 g; 24 V, 24,2 W | 710 € en variante pública; fiscalidad y accesorios pendientes | Más ligero que el Effilux; pedir revisión exacta y ensayo de contraste |
| [VA-BLBL2-COL-211x200W](https://va-imaging.com/products/bottom-lit-backlight-collimated-industrial-illumination-va-blbl2-col) | 211 × 200; PDF 225 × 214 × 20,5 mm | PDF **890 g**; 24 V, 24,2 W | 710 € en variante pública; confirmar que incluye colimación | Web reutiliza datos de 18 mm/770 g; **discrepancia con PDF**, no fabricar a partir de la tabla web |
| [TPL CSBACK 2020](https://www.tpl-vision.com/overview/backlights/collimated-csback/) | 204 × 204; 214 × 214 × 21,1 mm | Masa pendiente; 24 V, 45 W | Sin precio verificado | Semicollimado; buen candidato para una comparación prestada antes de decidir |
| [VA-BLSLH2-200x200W](https://va-imaging.com/products/side-lit-direct-backlight-illumination-va-blslh2) | Web 200 × 200; 234 × 234 × 10,5 mm | Web 840 g; 24 V, 24 W | 444 € en variante pública; IVA/accesorios pendientes | **No seleccionado:** la descripción habla de colocar luz encima y mirar a través, incompatible con una interpretación simple de panel opaco inferior. Confirmar construcción y ficha |

En VA, se consultaron tanto página como datos públicos de la variante del producto (`.js`, precio en céntimos). No se rellenó carrito ni se asumió precio con IVA español. La variante BLSLH2 de 250 × 200 mostraba 416 €, menos que 200 × 200: conservar como discrepancia comercial a confirmar, no como ahorro garantizado. Su PDF requiere registro; no se creó cuenta.

El [PDF VA de backlight colimado v2.6](sources/VA_BLBL2_collimated_datasheet.pdf), pp. 1–2, identifica 0–40 °C de operación, colores, alimentación y dimensiones. Su tabla omite `COL` en los nombres aunque el documento dice colimado: confirmar SKU y revisión. No aplicar sus 890 g al modelo difuso. El [PDF TPL](sources/TPL_CSBACK_Product_Profile_EN.pdf), pp. 5–6, contiene la tabla de tamaños y conexión. Ninguno de estos rangos ambientales autoriza contacto directo con polímero recién desmoldeado.

La ficha de Edmund especifica AIC analógico, fuente separada y película de colimación opcional #22-104. El PDF actual de Effilux respondió 403; se registra el fallo en el manifiesto y no se afirma disponer de copia.

## Consecuencia para pesaje

Ejemplo de carga, no pieza pesada: Effilux 1900 g + PMMA 200 × 200 × 10 mm, 476 g calculados + pieza estimada 100 g = **2476 g antes de herrajes**. En una báscula de 3 kg quedan 524 g hasta capacidad nominal; falta comprobar excentricidad y carga durante colocación. Con ese panel, 5 kg da más margen. Una solución más ligera o con luz fija puede cambiar la elección.

El área luminosa de 200 × 200 mm tampoco garantiza margen si la pieza ocupa realmente los 200 × 200 completos. Medir envolvente real y posición de colada/localizadores; el diseño ideal del script ocupa menos, pero no incluye todo lo fotografiado.

## Maqueta de bajo coste

Un panel doméstico o mesa de calco puede servir para **descartar problemas de transmisión, apoyo y oclusión**. No lo descartaría antes de probarlo. No tiene demostradas uniformidad, estabilidad temporal, comportamiento PWM, calentamiento ni definición de borde para metrología. La palabra comercial «backlight» a veces describe iluminación decorativa trasera, no la cara emisora que necesitamos.

Ensayo económico: iluminar una placa plana con referencias en centro/esquinas; fijar exposición/ganancia; variar intensidad y separar la pieza 0/1/5/10 mm; repetir capturas. Medir cambio de ancho y perfil, no solo mirar si la imagen parece bonita. Una corrección de fondo puede compensar parte de la intensidad espacial, pero no recupera un borde saturado ni deshace refracción/oclusiones.

## Oportunidad para evitar una compra a ciegas

[TPL ofrece pruebas de viabilidad con muestras y préstamos de iluminación](https://www.tpl-vision.com/services/material-loans/), normalmente **15 días laborables**, sujetos a disponibilidad. Confirmar alcance geográfico, transporte, responsabilidad y modelo con el proveedor. No se ha enviado ninguna muestra ni contactado a nadie.

Petición preparada para una futura demostración: mismo objeto y cámara, luz difusa frente a semicollimada, piezas opaca/translúcida, altura variable, colada intacta y archivos originales. Solicitar perfiles y repetibilidad de ancho/longitud, no únicamente una foto de silueta ni una afirmación de «20 MP».

## Préstamo adicional: VA Imaging

La [FAQ vigente de VA](https://va-imaging.com/pages/vision-camera-frequently-asked-questions) indica que ofrece productos en préstamo sujetos a disponibilidad y condiciones. Esto aporta otra vía para probar panel/cámara/lente. Confirmar kit, duración, transporte y región antes de contar con él; no se ha solicitado. Una reseña antigua que diga que no había préstamos no describe necesariamente la política actual.
