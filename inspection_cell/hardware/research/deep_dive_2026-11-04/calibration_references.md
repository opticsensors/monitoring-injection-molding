# Referencias para calibrar y comprobar la medida

Revisión: 2026-11-04. **Propuesta de validación, no calibración realizada.** Interesan tanto llenado como cambios pequeños de longitud; una referencia que basta para localizar el frente puede no bastar para cuantificar contracción.

## Tres comprobaciones distintas

1. **Geometría de imagen:** distorsión, perspectiva del plano y conversión a milímetros, para lente, enfoque y resolución concretos.
2. **Extracción de pieza:** posición del borde y recorrido estimado, dependientes de luz, transparencia, sección y algoritmo. Una cuadrícula nítida no valida automáticamente el borde de polímero.
3. **Medida completa:** apoyo, altura, recolocación, estado térmico y referencia independiente. Un error de reproyección bajo no demuestra por sí solo error dimensional bajo.

La referencia debe estar en el plano de medida definido. Calibrar sobre el soporte no corrige automáticamente puntos situados varios milímetros por encima. Los marcadores fijos pueden mostrar que la cámara se ha movido, pero no revelan por sí solos la altura de la espiral; véase [variación detectable](detectable_variation.md).

## Ejemplo comercial: no todos los patrones tienen la misma tolerancia

La [página de Calib.io](https://calib.io/products/checkerboard) mostró **103 €** para CHT200150F, aluminio/LDPE de 200 × 150 mm, el 2026-11-04. IVA y transporte a España no verificados. El precio no corresponde al modelo cerámico ni incluye necesariamente informe individual de coordenadas.

Las tres fichas siguientes se descargaron y sus tablas de primera página se revisaron visualmente. Tolerancias especificadas a 20 °C; `b` es separación entre características expresada en metros.

| Construcción | Tolerancia de distancia publicada | Ejemplo calculado para 100 mm | Planitud publicada | Iluminación |
| --- | --- | --- | --- | --- |
| [Aluminio/LDPE, rev. 04 de 2025](sources/Calib_Alu_LDPE_2025.pdf) | 0,3 mm + 0,2 mm/m · b | 0,320 mm | 0,5 mm por 200 mm | Frontal |
| [Impresión litográfica, rev. 03 de 2025](sources/Calib_Print_Lithography_2025.pdf) | 0,04 mm + 0,08 mm/m · b | 0,048 mm | Vidrio: 0,1 mm por 100 mm; CFRP: 0,5 mm por 100 mm | Frontal; también posterior con vidrio |
| [Cromo sobre cerámica, rev. 04 de 2025](sources/Calib_Ceramic_2025.pdf) | 0,005 mm + 0,010 mm/m · b | 0,006 mm | 0,01 mm por 100 mm | Frontal o posterior |

Estos límites no son desviaciones estándar ni errores medidos de una unidad concreta. Tampoco son la incertidumbre final de la cámara. Las cifras de resolución de impresión —1200, 10000 o 100000 dpi— no sustituyen la tolerancia dimensional.

El fabricante distingue dos extras: certificado de cumplimiento de sus especificaciones e informe con posiciones 3D medidas de cada esquina. Según las fichas, para patrones de hasta 400 mm este último utiliza una máquina óptica calibrada en laboratorio acreditado ISO 17025. Son opciones bajo presupuesto; no asumir que vienen con el tablero ni equiparar ambos documentos. La posición del dibujo respecto al contorno de la placa tampoco está tolerada en las fichas litográficas.

**Implicación para Machina:** el tablero de aluminio puede ayudar en una maqueta, pero su especificación nominal no respalda por sí sola una referencia absoluta de 0,1 mm. Una unidad caracterizada individualmente podría servir con sus coordenadas reales y su incertidumbre. No se propone comprar ahora un patrón cerámico sin probar primero la pieza y consultar referencias disponibles en el laboratorio.

## Por qué longitud y ancho exigen escalas distintas

Cálculo ilustrativo propio: si una referencia supuestamente de 100 mm tuviera un error desconocido de 0,02 mm, el error relativo de escala sería aproximadamente 0,02 %. Aplicado uniformemente a 510,51 mm, contribuiría unos **0,102 mm**; aplicado a 4 mm, unos **0,0008 mm**. La hipótesis de 0,02 mm no es una especificación del pie de rey disponible.

El ejemplo trata solo escala uniforme. No modela distorsión local, planitud, ajuste conjunto de muchas esquinas, iluminación ni extremos. Para medir cambios entre piezas, un sesgo estable puede cancelarse parcialmente; un cambio de plano o de apoyo no tiene por qué hacerlo.

## Ruta de menor coste antes de comprar referencias

1. **Maqueta:** patrón impreso o regla para comprobar encuadre y funcionamiento, etiquetando medidas como orientativas. Registrar cómo se obtuvo el tamaño; no declarar precisión de impresora o pantalla.
2. **Préstamo o laboratorio:** pedir una referencia con dimensiones e incertidumbre conocidas, adecuada para 150–200 mm de campo. Consultar si pueden caracterizar una placa existente; no limitarse a preguntar por una cámara más cara.
3. **Validación independiente:** reservar distancias/rasgos que no se hayan usado para ajustar la calibración; comprobar centro, esquinas, orientaciones y alturas. Una misma regla usada para fijar escala y comprobarla no es una validación independiente.
4. **Pieza real:** comparar ancho y longitud con un método externo adecuado. El calibre sirve para anchos accesibles y cotas entre referencias definidas; no mide directamente el recorrido curvo de 510 mm. Una máquina óptica/CMM puede aportar referencia si la condición de apoyo y los extremos son equivalentes.
5. **Decisión:** elegir la referencia final según la variación que interesa separar y los resultados de repetición. Evitar que todo el presupuesto de error lo consuma el patrón; todavía no hay un presupuesto de incertidumbre cerrado.

Incorporar identificación de referencia, incertidumbre disponible, temperatura y condición de apoyo al [registro de pruebas](../../../validation/templates/bench_record.md). No se han reservado equipos ni enviado muestras a terceros.
