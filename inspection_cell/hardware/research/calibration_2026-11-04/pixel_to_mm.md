# Qué significa convertir píxeles a milímetros

2026-11-04. Síntesis y cálculos para esta celda; no resultados de un equipo ensayado. Referencias primarias y alcance de lectura en [literatura](literature_review.md).

## La escala procede de una referencia física

El píxel de 2,4 µm describe el **sensor** FLIR, no la pieza. La focal nominal y la distancia permiten dimensionar el montaje, pero no sustituyen una calibración del conjunto real.

Si dos marcas distan realmente `D mm` y aparecen separadas `d px`, la estimación elemental es `s = D/d mm/px`. Con imagen de 5472 × 3648 y un campo **realmente calibrado** de 300 × 200 mm, la escala media sería 200/3648 = 0,05482456 mm/px. Un ancho de 4 mm ocuparía unos 73 píxeles; 0,1 mm, unos 1,82 píxeles. Son cifras de muestreo, no garantías de error.

La práctica precisa consiste en estimar un mapa `F(u,v) = (X,Y)` desde coordenadas de imagen hacia coordenadas del plano. Después se calculan distancias y longitudes **en ese plano métrico**.

## Cuatro niveles de modelo

| Modelo | Qué resuelve | Qué necesita y qué no resuelve |
| --- | --- | --- |
| Escala global, con rotación/traslación | Conversión uniforme de unidades | Aceptable solo si la validación confirma escala uniforme en todo el área utilizada. Una regla en el centro no comprueba las esquinas |
| Homografía del plano | Perspectiva de un plano inclinado | Al menos cuatro correspondencias en posición general; usar muchas, distribuidas. No absorbe exactamente la distorsión no lineal del objetivo |
| Intrínsecos `K`, distorsión `D` y pose del plano | Modelo de cámara y transformación a un plano definido | Varias vistas informativas del patrón; después una referencia del plano definitivo. No determina la altura desconocida de cada tramo de espiral |
| Mapa empírico 2D, mediante retícula densa | Relación imagen→plano de un montaje fijo, incluyendo desviaciones locales | Coordenadas reales conocidas y buena planitud. Solo válido en el dominio y altura calibrados; necesita validación entre nodos, no extrapolación |

Base geométrica: Zhang, §§2–4; Szeliski, §§2.1.6 y 6.3. HALCON documenta medición en plano y rectificación por retícula. **La elección para Machina es una propuesta propia:** probar el modelo más sencillo que pase validación independiente, conservando el mapa denso como alternativa si una homografía deja residuos espaciales.

Una homografía inversa sobre coordenadas ya libres de distorsión tiene la forma:

```text
[a,b,c]ᵀ = H⁻¹ [u_ideal,v_ideal,1]ᵀ
X = a/c; Y = b/c
```

Si se usa `undistortPoints`, especificar si devuelve coordenadas normalizadas o píxeles con una matriz de proyección: no mezclarlas con una homografía ajustada en otro sistema. El origen, ejes, unidad y sentido del mapa deben quedar guardados.

**No hace falta conocer por separado la focal y la distancia para medir sobre un único plano fijo.** Sí hacen falta más datos si se pretende trasladar esa calibración a alturas diferentes o reconstruir geometría espacial. Las vistas frontales repetidas pueden definir muy bien el plano y aportar poca información para separar focal y distancia: no son objetivos equivalentes.

## El error de altura permanece después de calibrar

Derivación propia con cámara pinhole perpendicular, plano de referencia a distancia `Z`, y objeto plano situado `h` más cerca de la cámara:

```text
M = Z/(Z-h)
medida interpretada en el plano de referencia = medida real × M
error relativo = h/(Z-h)
```

Ejemplo idealizado con `Z=800 mm`; se desplaza **todo el objeto en paralelo**, no una espiral con alabeo local:

| Diferencia de altura | Error de un ancho de 4 mm | Error de un recorrido plano de 510,508806 mm |
| --- | ---: | ---: |
| 0,1 mm | 0,00050 mm | 0,06382 mm |
| 1 mm | 0,00501 mm | 0,63893 mm |
| 2 mm | 0,01003 mm | 1,27947 mm |
| 10 mm | 0,05063 mm | 6,46214 mm |

La última columna no predice el error de vuestra pieza alabeada: las pendientes, orientaciones y alturas locales cambian la proyección. Demuestra que una calibración perfecta del suelo no basta. Para limitar **solo este efecto uniforme** a 0,1 mm en el recorrido, la diferencia de altura tendría que ser aproximadamente ≤0,157 mm a 800 mm; no queda margen asignado a otras contribuciones.

El plano relevante tampoco es automáticamente el suelo. Si la sección fuera circular y opaca, el contorno lateral se formaría cerca de su zona ecuatorial en una vista casi perpendicular; diámetro, perspectiva y material influyen. Hay que contrastar el plano efectivo con patrones de espesor/ancho semejantes. La sección circular aún no está confirmada.

Un soporte puede reducir variación de altura, pero no debe forzar la longitud nominal ni ocultar el contorno. Medir una pieza apoyada/sujeta define una condición de medida distinta de su forma libre. Un patrón situado bajo una placa transparente tampoco representa necesariamente el mismo plano óptico que una pieza situada encima.

## Por qué diámetro y longitud no heredan el mismo error

1. **Escala común:** un error relativo de 0,02 % produce 0,0008 mm sobre 4 mm y 0,1021 mm sobre 510,508806 mm. No disminuye por utilizar miles de puntos de la curva.
2. **Bordes:** desplazar ambos bordes hacia fuera aumenta el ancho; puede dejar casi inmóvil la línea central. Por el contrario, un extremo mal detectado altera la longitud aunque apenas afecte al ancho medio.
3. **Curva discretizada:** contar píxeles del esqueleto no es medir su longitud de arco con exactitud. Orientación, escalones, suavizado, ramificaciones y extremos requieren tratamiento propio.
4. **Altura y pendientes:** cambian la proyección y pueden confundirse con contracción. Una sola imagen no recupera la longitud espacial general.

No sumar un supuesto error independiente por cada píxel ni multiplicar simplemente el RMS de calibración por la longitud. La correlación espacial importa; una traslación constante ni siquiera cambia las distancias. Ver [incertidumbre y pruebas](repeatability_uncertainty.md).

## Recomendación de cálculo posterior

Conservar la imagen gris original. Localizar bordes subpíxel, transformar sus **coordenadas** al plano y calcular ahí ancho normal y recorrido central. Una imagen rectificada puede facilitar visualización, pero interpolarla varias veces puede modificar los bordes. La elección del extractor se valida con el material, la luz y el soporte reales.

Separar avance del frente respecto a una referencia del molde y longitud observada de una pieza completa. Registrar la pieza con traslación/rotación cuando corresponda; ajustar libremente su escala al CAD eliminaría precisamente la contracción que interesa detectar.
