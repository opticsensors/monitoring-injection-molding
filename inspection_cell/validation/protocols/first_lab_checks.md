# Primeras comprobaciones con el material del laboratorio

Estado: **propuesta, no ejecutada**. Medios confirmados: pie de rey y básculas sin USB ni RS-232. El usuario no conoce los modelos; no es necesario esperarlos para continuar la búsqueda. No se presupone disponer de cámara industrial, panel, termómetro ni patrones. El objetivo es resolver decisiones de hardware; no certificar la celda con instrumentos todavía sin identificar.

## 1. Información mínima que desbloquea decisiones

| Prioridad | Qué aportar o medir | Qué permite decidir |
| --- | --- | --- |
| A | Al hacer pruebas, anotar capacidad y división visibles de la báscula utilizada; modelo solo si se conoce | Saber qué diferencias permite observar. La ausencia de USB/RS-232 ya está confirmada; no bloquea la investigación |
| A | Peso con colada de 3–5 piezas, indicando báscula y estado frío/caliente | Intervalo real de peso y umbral de presencia; revisar si 100 g era una sobreestimación |
| A | Foto cenital, lateral a ras del apoyo y de la parte inferior de la unión con colada | Resolver oclusión, saliente inferior y apoyo. Las fotos oblicuas del PPT ya se han revisado |
| A | Altura de colada, ancho/largo máximos y hueco bajo las vueltas más elevadas | Encuadre, eje de cámara y necesidad de soporte |
| B | Sección del hilo en un extremo accesible: ancho y espesor; foto cercana | Saber si «diámetro» circular es correcto o debemos medir anchura/espesor |
| B | Dos o tres piezas que representen problemas reales: alabeo, llenado parcial o cambio de material/color | Evaluar los casos difíciles, sin asumir que una muestra valida todos los materiales |

Para las fotos usar una regla en el mismo plano de la zona de interés y cámara lo más perpendicular posible. Sirven para diseño y observación; una foto de móvil con regla no certifica ±0,1 mm. No hace falta cortar una pieza buena para la primera revisión: usar extremo existente o muestra descartada si ya la hay. Identificar qué salientes pertenecen al molde y cuáles serían defectos.

## 2. Pesaje manual inicial, sin USB

1. Identificar báscula, división, capacidad y condiciones/calibración conocidas. Nivelar y seguir su calentamiento indicado. No poner una precarga de 2 kg en una báscula cuya capacidad no lo permita.
2. Con una **misma pieza fría y estable**, hacer diez ciclos retirar–colocar. Registrar lectura aceptada y cero tras retirada, sin redondear más que la pantalla. Mantener primero la posición; después repetir en posiciones representativas del soporte. No tocar la mesa durante lectura.
3. Repetir con el soporte provisional, si existe y cabe en capacidad. Registrar masa bruta además de tara. Comparar panel apagado/encendido y cable en su posición de trabajo si se dispone de panel.
4. Si el laboratorio tiene pequeñas masas de referencia adecuadas, añadir 10/20/50/100 mg sobre la precarga de uso, alternando añadir/retirar. Registrar su valor/certificado. Sin referencias, un objeto estable permite estudiar repetición, **no demostrar exactitud de 10 mg**.
5. Anotar evolución de la lectura tras colocar la carga y tras retirarla. Una cifra momentáneamente quieta no demuestra ausencia de deriva o seguimiento de cero. No ajustar repetidamente hasta conseguir el resultado deseado.

Estas diez repeticiones son un cribado, no un estudio de capacidad completo. Una báscula de división 0,1 g no permite evaluar sensibilidad de 0,01 g por anotación manual, pero sí conocer masa aproximada y variaciones grandes.

## 3. Pie de rey y comportamiento del apoyo

Elegir cinco zonas accesibles del recorrido, fotografiarlas o marcarlas en un croquis y medir tres veces en cada una sobre una pieza fría. Evitar rebabas/salientes salvo que sean la característica buscada. Registrar orientación de mordazas y presión suave consistente. Repetir en otras piezas si hay diferencias visibles. No tomar la resolución del calibre como incertidumbre ni usarlo para validar por sí solo la longitud curva total.

Apoyar la pieza libre sobre una superficie plana; fotografiar de lado y medir huecos sin presionarla. Después probar un apoyo o sujeción suave y comparar posiciones y anchuras accesibles. Registrar si vuelve a la forma anterior al soltar. Si el apoyo cambia permanentemente la pieza, oculta el borde o impide contracción libre, no sirve como referencia neutral; podría servir como condición funcional distinta, si se define así.

La [guía de Mitutoyo](https://www2.mitutoyo.co.jp/eng/useful/E11003/pageindices/index23.html) identifica fuerza excesiva y diferencia térmica entre pieza/calibre como fuentes de error. Se toma como criterio de uso, no como especificación del pie de rey disponible. No hace falta comprar un calibre de fuerza controlada para observar el problema inicialmente.

## 4. Estado recién desmoldeado: separar cambio real y error

No sustituir el requisito de inspección caliente por uno de pieza fría. Hacer una serie exploratoria con lecturas/fotos a tiempos conocidos desde desmoldeo, por ejemplo primera colocación posible, 15, 30, 60 y 120 s, más una lectura fría posterior. Son puntos para caracterizar evolución, **no tiempos impuestos al ciclo de producción**. Ajustarlos a lo que pueda observarse sin alterar la operación.

La repetición de una pieza que se enfría mezcla contracción real y cambios del equipo. Intercalar una referencia fría/estable permite distinguir parte de ambos. No sujetar con el calibre una pieza blanda caliente como referencia de forma libre.

Si hay termómetro, registrar método y punto. Un hilo de 3–4 mm puede ser menor que el área que lee un termómetro IR: el láser no representa necesariamente esa área. [Fluke explica el efecto de tamaño de blanco y distancia](https://www.flukeprocessinstruments.com/en-us/why-use-pyrometers/frequently-asked-questions-about-infrared-instruments). Una sonda de contacto también puede alterar una muestra pequeña; caracterizar aparte si procede. Sin termómetro, los tiempos y la evolución observada ya aportan información, dejando temperatura como pendiente.

## 5. Prueba de cámara/luz prestadas antes de comprar

Aplicar el [protocolo dimensional](dimensional_accuracy.md) a un conjunto pequeño y concreto:

- Referencia rígida: 20 capturas sin mover; después 20 retiradas/recolocaciones. Guardar gris original, sin compresión destructiva, y ajustes fijos.
- Repetir en centro/esquinas y con alturas conocidas 0/1/5/10 mm. El cero debe representar el plano de calibración, no un «suelo» indefinido.
- Misma muestra: luz difusa frente a semicollimada; barrido de intensidad y aberturas próximas a f/4, f/5,6 y f/8. Evitar saturación; no atribuir a la abertura cambios causados por exposición automática.
- Piezas reales con colada intacta, opacas y translúcidas si están disponibles. Comprobar inicio/final y tramos ocultos. Una vista lateral sirve como diagnóstico, no como reconstrucción 3D garantizada.
- Referencia fría al inicio y al final del calentamiento del conjunto. Si aparece deriva, separar desplazamiento de imagen, cambio de escala y cambio de borde.

Para afirmar exactitud de longitud hará falta una **referencia curva independiente** o medición externa de piezas bajo la misma condición. Ni 510,5088 mm del script ni el ajuste al mismo patrón usado para calibrar constituyen esa verificación.

## 6. Cómo interpretar los primeros números

Calcular media, desviación típica muestral y rango por condición; conservar lecturas individuales. Separar repetición estática, recolocación, posición, apoyo y estado térmico. No mezclar sus datos en una única «precisión».

Si dos lecturas tienen ruido independiente con desviación típica `s`, su diferencia tiene desviación típica `√2·s`. Como **cribado orientativo**, comparar una variación de interés con `3√2·s`, además de sesgos y deriva observados. No es una garantía de detección ni un criterio universal de aceptación: para una potencia/confianza concreta hace falta definir el contraste y estimar suficientes datos. La cifra ±0,03 g de un manual no puede sustituirse por `s=0,03 g` sin conocer cómo se obtuvo.

Si la variación entre piezas es parecida al ruido de recolocación, mejorar apoyo/luz/escala antes de comprar más megapíxeles. Si una altura desconocida cambia la longitud demasiado, escoger una condición de apoyo medible o reconsiderar información de altura. Si la báscula no distingue incrementos sobre carga real, bajar carga/mejorar mecánica o cambiar de instrumento.

Registrar con la [plantilla de banco](../templates/bench_record.md) y guardar resultados en [reports](../reports/README.md). De momento no hay resultados físicos.

## Referencia de calibración y comprobación independiente

Antes del ensayo óptico, consultar [patrones, tolerancias y ruta de menor coste](../../hardware/research/deep_dive_2026-11-04/calibration_references.md). Separar rasgos usados para ajustar de rasgos reservados para comprobar; registrar identificación, dimensiones conocidas, incertidumbre y plano. Un patrón de impresión o una regla sin caracterización permiten una prueba orientativa, no acreditar automáticamente 0,1 mm.
