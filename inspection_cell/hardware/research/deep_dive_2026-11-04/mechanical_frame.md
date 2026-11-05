# Columna, brazo y envolvente del montaje

Estudio preliminar, 2026-11-04. No es un cálculo constructivo completo ni una validación de estabilidad del conjunto.

## Comparación que sí permite hacer el catálogo

Las fichas de item para [20 × 20, referencia 0.0.370.03](sources/ITEM_profile_20x20.pdf) y [40 × 40, referencia 0.0.026.03](sources/ITEM_profile_40x40.pdf) especifican momentos de inercia de flexión de **0,72 y 13,96 cm⁴**, respectivamente. Sus masas son 0,48 y 2,47 kg/m. Son dos perfiles concretos, no valores universales de todos los perfiles de ese tamaño ni de los V-slot del PPT.

La [guía técnica del fabricante](sources/ITEM_profile_deflection.pdf), apartado de flexión, utiliza para voladizo con fuerza puntual `δ=F·l³/(3·E·I)` con unidades coherentes. Aquí se usa E=70.000 N/mm² e I en mm⁴. Ejemplos propios:

| Hipótesis de carga, empotramiento ideal | Perfil 20 × 20 | Perfil 40 × 40 |
| --- | ---: | ---: |
| Brazo horizontal de 250 mm, masa puntual de 200 g al extremo | 0,0203 mm | 0,00105 mm |
| Columna de 800 mm, fuerza lateral de 1 N al extremo | 0,3386 mm | 0,01746 mm |

Los 200 g y 1 N son cargas de ejemplo, no masas/fuerzas medidas. Se excluyen peso propio, torsión, brazo unido a columna, flexibilidad de escuadras/base, vibraciones y contacto con mesa. No sumar la segunda fila a un error dimensional: un movimiento lateral puede cambiar colocación/ángulo de cámara, y su efecto requiere la geometría óptica completa.

El peso fijo de cámara/lente puede producir una deformación que esté presente al calibrar; los **cambios** de carga, cable, unión o temperatura son los que invalidan esa condición. Un brazo de 500 mm se deforma ocho veces más que uno de 250 mm en este modelo, a igualdad de carga y sección. Por eso acortar y triangular importa tanto como cambiar el perfil.

Recomendación provisional: estudiar columna 40 × 40 y brazo corto con escuadra/arriostramiento, no una torre de 20 × 20 elegida solo por precio. Comprobar el perfil realmente comprado y sus uniones. No es necesario sobredimensionar hasta una bancada de metrología antes de medir la deriva del prototipo.

## La altura total no es la distancia óptica

La estimación de 0,635–0,835 m para una lente de 35 mm se mide en un modelo de planos principales. A la altura desde la mesa se suman báscula, panel, soporte y posición real de cámara/lente. Una estación con esa distancia óptica puede superar un metro de altura total. Pedir al proveedor la distancia desde el frontal de la lente al plano de objeto; dibujar después el conjunto con los equipos y holguras reales.

La [foto dimensional SBS-LW-1030](https://assets.expondo.com/asset/product_photos/10031315_photo_6?twic=v1/contain=1500x1500) muestra cuerpo de 300 × 205 × 95 mm. Si se usa esa orientación, una base de 300 mm queda sin margen de profundidad para columna, conexión o manipulación. El panel EFFILUX de 200 mm útiles mide 239 mm exterior; el TPL de 204 mm útiles, 214 mm exterior. La envolvente del PPT necesita revisión, no solo cambiar la focal.

## Montaje y comprobación sin cerrar todavía el CAD

- Columna y cámara ancladas a una base estable fuera de la plataforma pesada; no apoyar la luz o un tope accidentalmente en ambas estructuras.
- Ruta del USB de cámara fijada a columna, con holgura antes del conector y sin tirar del ajuste. Ruta del cable del panel ensayada si este se pesa.
- Ajustes de altura y orientación que puedan bloquearse y marcarse. La flexibilidad del conector o de la rosca no debe utilizarse como ajuste permanente.
- Comparar una referencia rígida antes/después de colocar y retirar piezas, y durante calentamiento. Separar desplazamiento global, cambio de escala y cambio de borde.
- Comprobar acceso de manos y paso de colada antes de fabricar. No fijar aún una sección de placa o una base por el tamaño exterior de la espiral sola.

La revisión CAD permanece pendiente. Este documento permite evaluar el concepto del PowerPoint, pero no sustituye cotas, elección de uniones ni ensayo de la estructura real.
