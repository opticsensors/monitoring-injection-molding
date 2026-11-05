# Visión general

## Propósito

Relacionar las condiciones registradas durante un ciclo de inyección con la geometría y el peso de la pieza resultante. Tras introducir manualmente la espiral en la celda, la adquisición de imagen y peso debe ser automática y quedar asociada al ciclo pertinente.

## Pieza

La pieza inicial es una espiral de polipropileno (PP); se prevén otros materiales. Idealmente es plana, con hilo de aproximadamente 3–4 mm de ancho/diámetro descrito y una colada vertical; la sección circular no está confirmada. Las contracciones y deformaciones hacen que algunas zonas apoyen en el plano y otras queden hasta aproximadamente 10 mm por encima de él, según la descripción del usuario. Falta precisar si esa altura se refiere a la cara inferior o al eje del hilo y medir la altura de la colada por separado.

La envolvente de trabajo indicada es de unos 150 × 150 mm, con 200 × 200 mm como opción conservadora. La geometría ideal del script tiene 510,5088 mm de recorrido por su línea central; la longitud y el peso reales de cada pieza siguen siendo desconocidos.

## Concepto inicial

- Cámara industrial 2D mirando verticalmente hacia la pieza.
- Óptica convencional y altura ajustadas al campo de visión y al error admisible.
- Iluminación posterior difusa para obtener una silueta.
- Soporte transparente que coloque la espiral de forma repetible; su capacidad para controlar altura sin alterar la medida queda por estudiar.
- Báscula conectada al PC, utilizada para medir peso y detectar la colocación.
- Estructura con perfiles de aluminio, columna vertical y brazo horizontal para centrar la cámara.
- Software independiente de la adquisición DAQ, integrado con los ciclos y servicios del repositorio.

## Alcance inicial

Longitud del recorrido de la espiral, ancho/diámetro del hilo y peso. Interesan tanto avance del llenado como cambios pequeños/contracción en piezas completas; véase la [definición de medidas](measurement_definition.md). Se estudia primero una solución 2D por coste y simplicidad. El usuario aclara que 0,1 mm es una orientación: hay que demostrar qué variaciones se distinguen del ruido. Se inspeccionará recién desmoldeada; presupuesto de báscula de 300 € con IVA y conexión, con 0,01 g deseado. Véase [estado de investigación](research_status.md).

La silueta cenital aporta longitud proyectada y ancho aparente. La equivalencia con longitud espacial y diámetro real depende de la planitud y la sección de la pieza. El análisis de color, textura, defectos superficiales y reconstrucción 3D queda fuera de esta primera propuesta.

## Estado

Hay una presentación conceptual, geometría de referencia, ficheros CAD suministrados y una oferta histórica de cámara/óptica. No hay selección final de báscula, panel, soporte, altura, protocolo de identificación ni aplicación de inspección funcional.
