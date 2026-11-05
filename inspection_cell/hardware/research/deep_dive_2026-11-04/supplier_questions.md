# Consultas técnicas preparadas, no enviadas

Documento para futuras consultas o un préstamo, actualizado el 2026-11-04. No se ha contactado a proveedores ni compartido fotos/CAD. Ninguna compra está aprobada.

## Cámara, lente y luz: especificación breve de ensayo

Pieza en espiral de 3–4 mm de ancho aproximado, recorrido nominal 510,5 mm, envolvente 150 × 150 mm y reserva de campo de 200 × 200 mm. Alabeo hasta unos 10 mm, colada vertical conservada, inicialmente PP y futuros materiales distintos. Se busca observar **avance de llenado y variación dimensional de piezas completas**, con 0,1 mm como orientación que debe contrastarse con el ruido. Cámara a menos de 1 m de la pieza preferida; 2 m no aceptable.

Solicitar a STEMMER o proveedor alternativo:

1. Con sensor IMX183 de 13,1328 × 8,7552 mm y lente de **35 mm**, ¿qué distancia frontal, campo completo y área útil con margen se obtienen? Confirmar foco, apertura y MTF/contraste útil en centro y esquinas a esa distancia. Si propone otro sensor, recalcular con sus dimensiones reales.
2. Comparar Computar V3522-MPZ con alternativa equivalente: precio actualizado, disponibilidad, bloqueo de iris/foco, distorsión y condiciones de especificación. No interpretar «20/25 MP» como garantía de error dimensional.
3. ¿Pueden prestar cámara/lente/panel o hacer una prueba con muestras? TPL publica un programa habitual de 15 días laborables y VA también indica préstamos sujetos a condiciones. Confirmar región, disponibilidad, transporte y accesorios; no asumir gratuidad total o aceptación de muestras calientes.
4. Ensayar luz difusa y semicollimada con pieza y soporte reales. Pedir imágenes en gris originales, sin autoexposición/autoajustes, a 0/1/5/10 mm de altura conocida, referencia en plano, centro y esquinas. Registrar exposición, apertura, ganancia, distancia, panel y estado térmico.
5. Incluir 20 capturas estáticas y 20 recolocaciones de una referencia/pieza estable; comprobar colada, inicio/final y materiales opacos/translúcidos disponibles. El alcance es demostrar observabilidad y repetición, no pedir una garantía de ±0,1 mm sin definir magnitudes.

## Básculas: preguntas por candidata

Carga prevista inicialmente: hasta unos 2 kg de soporte/luz, pieza estimada por debajo de 100 g; ambos pendientes de pesar. División preferida 0,01 g. Presupuesto **300 € con IVA y todo lo necesario para leer automáticamente desde PC**.

| Proveedor/modelo | Pregunta que realmente falta |
| --- | --- |
| Steinberg SBS-LW-1030 | Repetibilidad y linealidad con método/condiciones; sensibilidad de 10/20/50 mg con precarga de 2 kg; dimensiones/carga excéntrica admitida de un soporte ampliado |
| Steinberg, comunicación | Pinout del D-sub de 9 contactos, cable cruzado o directo, bits de parada, trama/unidades/estabilidad y ritmo efectivo en modo continuo. Manual ya confirma automático estable/continuo; no volver a preguntar si existe esa función |
| U.S. Solid USS-DBS28-50 / JFDBS00028-5KG | Confirmar repetibilidad **±0,03 g del manual frente a ±0,02 g de la web**, dimensiones y revisión exacta; comportamiento con precarga y pequeños incrementos |
| U.S. Solid, comunicación | Tipo de USB y controlador, cable incluido, envío continuo sin pulsación y bandera de estabilidad. El manual ya confirma RS-232 9600 8N1 y cable cruzado 2–3; verificarlo en la unidad entregada |
| U.S. Solid, comercial | Suministro a España, origen de envío, importe final e impuestos, accesorios incluidos y posibilidad de ensayo/devolución aplicable a la compra prevista. La tienda alemana solo documenta claramente Alemania |
| PCE-BSK 1100 | Presupuesto conjunto con adaptador compatible y transporte; prestaciones con soporte ligero real. Confirmar régimen térmico de validez, no solo rango operativo |
| Nahita KBD005, solo ruta de soporte <300 g | Confirmar lectura continua o consulta desde PC sin MENU, protocolo/controlador USB, revisión del manual y cable incluido. La báscula sola ronda 296,75 € con IVA; falta total entregado y conectado |
| Todas | Desactivar/ajustar seguimiento de cero y filtros, respuesta al retirar pieza, recuperación de puerto/alimentación y tiempo de estabilización sobre el montaje real |

No afirmar que una báscula de división 0,01 g tiene incertidumbre ±0,01 g. Pedir datos de prueba si existen; una respuesta comercial sin método no resuelve esta incertidumbre.

## Iluminación y soporte

- **EFFILUX/Edmund #22-098:** confirmar masa 1,9 kg, fuente/controlador/cable incluidos o aparte, temperatura admisible de contacto y carga mecánica admisible sobre superficie. El rango ambiental no autoriza apoyar directamente una pieza caliente.
- **TPL CSBACK2020:** masa, coste, control de colimación, fuente y kit de préstamo. Ficha documenta 204 × 204 mm útiles, 214 × 214 × 21,1 mm y 45 W; no asumir masa por tamaño.
- **VA-BLBL2-211x200W-COL:** confirmar SKU, precio y **890 g / 20,5 mm del PDF frente a 770 g / 18 mm en web**, accesorios y préstamo. No mezclar variante colimada y ordinaria.
- Para fabricar el apoyo: cotas reales de colada/saliente inferior, carga, temperatura superficial y método de limpieza antes de escoger PMMA, vidrio, espesor o ranura. No facilitar una ranura ajustada al nominal como diseño cerrado.

Fuentes y motivación: [lentes](lens_alternatives.md), [iluminación](lighting_candidates.md), [pesaje](weighing.md), [soporte](fixture_and_materials.md). Las respuestas deberán guardarse con fecha, modelo/revisión y condiciones, actualizando el índice de evidencias y las decisiones.
