# Repetibilidad, incertidumbre y variación detectable

2026-11-04. Marco de evaluación propuesto; no hay presupuesto de incertidumbre medido de la celda.

## Tres resultados distintos

**Resolución:** incremento representable, en píxeles o decimales. **Repetibilidad:** dispersión bajo condiciones definidas. **Error respecto a referencia / incertidumbre:** relación con el valor de la magnitud y conocimiento limitado de todas sus contribuciones. Mostrar 510,5088 mm no demuestra conocimiento al micrómetro.

El RMS de reproyección describe el ajuste de puntos de calibración en imagen. Hagemann et al. muestran que puede coexistir con sesgos y que las covarianzas ideales pueden resultar optimistas; proponen remuestreo por **imágenes**, no por esquinas tratadas como independientes. En esta celda usaríamos repetición de campañas y validación dimensional como comprobación principal; no hace falta implementar su método avanzado para empezar. [Artículo](https://arxiv.org/abs/2107.13484).

Steger demuestra detección subpíxel en experimentos concretos, pero su ensayo real también advierte distorsión y una discrepancia aproximada del 3,7 % en ancho respecto al nominal impreso con escala inferida localmente. Esa referencia no era una certificación del ancho. Es un buen motivo para no transformar «detecta 0,1 píxel» en «mide el ancho con error 0,1 píxel» sin validación. [Estudio](https://mv.in.tum.de/_media/members/steger/publications/1998/eemcv-98-steger.pdf), §§4.1–4.3.

## Modelo sencillo de incertidumbre

Para una medida `y=s·p`, con escala `s` y distancia de imagen `p`:

```text
u²(y) ≈ p²u²(s) + s²u²(p) + 2ps·cov(s,p)
```

El modelo de la celda será más amplio: coordenadas del patrón, mapa óptico, altura, bordes, montaje, temperatura y estado de la pieza. La propagación con covarianzas y las correcciones de efectos conocidos se describen en [NIST TN 1297](https://nvlpubs.nist.gov/nistpubs/legacy/tn/nbstechnicalnote1297.pdf), §§4–6 y apéndice A. No sumar tolerancias de catálogo como si todas fueran desviaciones estándar independientes.

| Contribución | Evidencia que necesitamos |
| --- | --- |
| Escala/coordenadas del patrón | Informe de calibración, incertidumbre, temperatura y planitud |
| Modelo residual | Artefacto independiente, posiciones reservadas y mapa de errores |
| Detección de bordes | Repetición, cambios controlados de luz/exposición y comparación con ancho conocido |
| Altura/apoyo | Ensayo a alturas conocidas, recolocación y observación del alabeo |
| Curva y extremos | Artefacto curvo y sensibilidad al muestreo/suavizado |
| Deriva | Referencia en arranque y distintas sesiones |
| Estado térmico/material | Serie específica de pieza caliente y validación por familia de material |

Evitar doble contabilización: la dispersión de recolocación ya incluye parte del ruido de imagen. Si se combinan componentes, estimarlas con un diseño que las separe, o usar una evaluación global coherente.

## Cambios pequeños entre dos piezas

Cálculo propio ilustrativo: si dos lecturas independientes tienen desviación estándar `σ`, su diferencia tiene `σΔ=√2·σ`. Bajo ruido normal estable, sin sesgos variables, un umbral bilateral del 5 % de falsas alarmas es aproximadamente `1,96√2·σ`.

Ese umbral **no garantiza alta probabilidad de detectar** un cambio real de igual tamaño. Para detectar un cambio positivo de 0,1 mm con aproximadamente 95 % de potencia usando ese umbral bilateral, una aproximación es:

```text
0,1 ≈ (1,96 + 1,645)·√2·σ  →  σ ≈ 0,0196 mm por lectura
```

Es un ejemplo de planificación, no un requisito acordado. Las correlaciones, una referencia promediada, muestras pequeñas y múltiples anchos por pieza cambian el cálculo. El sesgo fijo puede cancelarse parcialmente al comparar, pero altura, apoyo y enfriamiento variables no se cancelan por asumirlo. Promediar una ráfaga solo reduce componentes aleatorias suficientemente independientes; no borra error del patrón, deriva ni alabeo.

## Longitud de una curva

La longitud se calcula a partir de una curva central en coordenadas métricas. Ni contar píxeles negros ni sumar pasos de 1 y √2 píxeles del esqueleto garantiza exactitud. Además, sumar segmentos entre puntos ruidosos introduce sesgo positivo: en una recta de paso `d`, con ruido transversal independiente de desviación `σ` por punto y `σ≪d`, la expansión de segundo orden da un exceso medio aproximado `σ²/d` por segmento. Es una derivación ilustrativa, no un modelo del ruido real de la espiral.

Por tanto, más puntos no siempre dan mejor longitud. Elegir muestreo y regularización con artefactos conocidos, mantener extremos definidos y comprobar que el filtrado no elimina la variación física buscada. No imponer el recorrido CAD para estabilizar una medida destinada a detectar cambios del propio recorrido.

La [demostración geométrica reproducible](simulation_notes.md) separa escala, distorsión y altura. No incluye ruido fotométrico, transparencia, calor, flexión ni incertidumbre de referencias; sus resultados no son una certificación ni una previsión de repetibilidad de la FLIR.

## Sesgo subpíxel y respuesta de intensidad

[Duda y Frese (2018)](https://bmva-archive.org.uk/bmvc/2018/contents/papers/0508.pdf) estudian cómo cambia la localización de esquinas según posición fraccionaria, orientación, ruido y desenfoque. Su comparación es con la implementación de referencia de entonces, no una clasificación de todos los detectores actuales. OpenCV incorpora el enfoque sectorial en `findChessboardCornersSB`. Su precisión publicada no se transfiere al borde de una espiral ni certifica su escala.

Una consecuencia práctica propia: una ráfaga inmóvil puede ser muy estable y repetir el mismo sesgo. Además de recolocaciones grandes, comprobar **invariancia de dimensiones de un artefacto rígido con pequeñas traslaciones y giros**, manteniendo altura y enfoque. No hace falta conocer cada desplazamiento para comprobar que el ancho constante cambia; sí para validar el desplazamiento medido. Una mesa con movimiento conocido permitiría estudiar el efecto con más control si estuviera disponible.

[Rosenberger et al. (2016)](https://doi.org/10.21014/acta_imeko.v5i4.356) simulan bordes con parámetros radiométricos medidos y separan dispersión de desplazamiento sistemático. La no linealidad puede sesgar el borde sin aumentar mucho su dispersión; contraste y no uniformidad también importan. Su sensor/modelo no es el IMX183 y sus cifras no son estimaciones para Machina. Motiva barrer luz/exposición con una referencia y conservar la receta, sin saturar.

El estándar [EMVA 1288, General 4.0](https://www.emva.org/wp-content/uploads/EMVA1288General_4.0Release.pdf), §§1 y 6.5, caracteriza sensibilidad, ruido y no uniformidades bajo condiciones controladas. Tener una ficha EMVA resulta útil para elegir sensor; **no equivale a una calibración dimensional de la estación**. No se propone ejecutar todo ese estándar para el primer prototipo.
