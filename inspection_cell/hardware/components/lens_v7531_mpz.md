# Óptica Computar V7531-MPZ

Extracción revisada visualmente el 2026-11-04 desde [V7531-MPZ.pdf](datasheets/V7531-MPZ.pdf), página 1, revisión/fecha impresa **2022.07**. Archivo suministrado en `C:\edu\projects\Machina`, idéntico al archivado previamente desde Descargas.

La ficha describe una óptica de focal fija para cámaras 1 Type de 20 MP. La [oferta IN26-1893](quotes/IN26-1893.pdf) la identifica mediante el código comercial `CBC-IPZ-V7531`.

## Características ópticas

| Parámetro | Valor de ficha |
| --- | --- |
| Distancia focal | 75 mm, fija |
| Apertura máxima | f/3,1 |
| Rango de iris | f/3,1 a f/16, ajuste manual |
| Enfoque | 0,25 m a infinito, ajuste manual |
| Formato máximo de imagen | 12,8 × 9,6 mm; círculo de imagen Ø16 mm |
| Apertura efectiva de lente | Frontal Ø23,6 mm; trasera Ø16,5 mm |
| Distorsión tabulada | 0,0 % para formatos 1 Type, 2/3 Type y 1/1,8 Type |

Los diámetros de apertura efectiva no son el diámetro exterior de la carcasa ni sustituyen al número f. La distorsión tabulada con una cifra decimal no demuestra distorsión nula del sistema montado ni sustituye su calibración.

| Formato de la tabla del fabricante | Campo en la distancia mínima al objeto | Ángulo diagonal | Ángulo horizontal | Ángulo vertical |
| --- | --- | --- | --- | --- |
| 1 Type | 38,9 × 29,2 mm | 12,2° | 9,8° | 7,3° |
| 2/3 Type | 26,8 × 20,1 mm | 8,4° | 6,7° | 5,0° |
| 1/1,8 Type | 21,9 × 16,4 mm | 6,9° | 5,5° | 4,1° |

La ficha define `M.O.D.` como distancia mínima al objeto. Su mínimo de 0,25 m no es la distancia prevista para encuadrar la espiral de 150–200 mm: en esa condición el campo indicado es mucho menor. Los campos y ángulos de la tabla corresponden a los formatos del fabricante; el FOV de esta cámara concreta se estudia a partir de su área activa y se verifica físicamente.

## Cotas de integración

| Parámetro | Valor de ficha/plano |
| --- | --- |
| Montura | C-mount; el plano indica rosca 1–32 UNF |
| Distancia focal posterior (`Back Focal Length`) | 12,0 mm |
| Distancia de registro (`Flange Back Length`) | 17,526 mm; el plano indica «in air» |
| Rosca de filtro | M30,5, paso 0,5 mm |
| Diámetro exterior | Ø42,0 mm |
| Longitud de cuerpo tabulada | 79,8 mm |
| Longitud de cuerpo en plano | 79,8 mm a infinito; 81,3 mm máxima, entre las referencias dibujadas |
| Masa | 176,1 g |
| Temperatura de operación | −10 a 50 °C |

La distancia focal posterior y la distancia de registro son parámetros internos/de montura; no representan la distancia cámara-pieza. Para diseñar soporte y envolvente hay que respetar las referencias del plano, la zona de acoplamiento y el acceso a los anillos de foco e iris. No obtener una altura de montaje sumando sin más las longitudes tabuladas de cámara y lente.

## Compatibilidad y comprobaciones pendientes

La cámara candidata tiene montura C y un área activa calculada de 13,1328 × 8,7552 mm, diagonal de 15,7837 mm. Esa diagonal es menor que los 16 mm de círculo de imagen indicados por la lente: es una comprobación geométrica inicial, no una validación de iluminación, resolución o contraste en las esquinas.

El [estudio de visión](../research/vision.md) conserva las estimaciones de FOV, muestreo y distancia de una lente delgada, separadas de estos datos de fabricante. Antes de fijar la estructura se deben medir campo útil, calidad de borde, distancia real, apertura y sensibilidad a la altura de la espiral.

La ficha no incluye curvas MTF, profundidad de campo para esta aplicación, error de calibración del conjunto ni garantía de medida de ±0,10 mm. Esas prestaciones requieren ensayo con cámara, iluminación, soporte y piezas reales.
