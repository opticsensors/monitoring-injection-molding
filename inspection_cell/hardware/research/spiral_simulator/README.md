# Simulador 3D de espiral, altura y perspectiva

Creado el **2026-11-05** a petición del usuario. Herramienta de investigación geométrica, independiente de la aplicación DAQ y del futuro software de inspección. **No utiliza fotos ni resultados de una celda física.**

## Abrir y utilizar

Abrir **[simulador.html](simulador.html)** con Chrome o Edge mediante doble clic. El archivo incluye el motor 3D: no necesita instalación, servidor ni conexión a Internet. El navegador debe disponer de WebGL.

El visor ocupa la pantalla, con proyección ortográfica y paneles inicialmente cerrados.

- **Ratón:** botón central para girar, Ctrl + central para desplazar, rueda o Shift + central para zoom. También admite arrastre izquierdo para girar y derecho para desplazar.
- **Encuadre:** F ajusta el montaje completo; **Pieza** o doble clic centra la espiral. Las vistas y el indicador XYZ cambian el observador, no la cámara de medida.
- **Parámetros:** primer icono de la barra. Incluye escenarios, focal, altura, deformación e inclinación. En **Más** están las opciones avanzadas y la amplificación visual del relieve, que no altera los cálculos.
- **Errores simulados:** segundo icono. Abre un panel junto a Parámetros con sesgo de escala y distorsión radial, ambos a cero inicialmente. «Poner a cero» restablece solo estos errores; cerrar el panel los conserva y el icono queda marcado si hay alguno activo.
- **Medidas:** icono de regla. **Guardar:** icono de descarga, con PNG, JSON y CSV.

Los controles permiten modificar el plano calibrado y desplazar el eje óptico en XY. La calibración ideal se actualiza al modificar la configuración óptica; el plano no sigue automáticamente a la pieza. No se modela el error de reutilizar una calibración hecha con otra focal.

## Geometría y referencia de altura

Arcos idénticos a [spiral_sensors.py](../../mechanical/geometry/spiral_sensors.py): radios 13, 26, 39, 52 y 65 mm; cuatro semicírculos y un cuarto de círculo. Longitud analítica **510,5088062083 mm**. Se mantienen los ejes XY del archivo original y el eje óptico inicial en X=Y=0. No se modela la colada ni se validan sus cotas CAD.

La referencia solicitada por el usuario se implementa explícitamente:

- **Centro fijo (predeterminado):** el extremo interior de la espiral, originalmente X=Y=0, permanece en Z=elevación al cambiar desnivel, fase o inclinación. La rotación pivota sobre ese extremo y la deformación sin estirar no recentra después la envolvente XY. Con elevación 0, el bulto parte de Z=0 y alcanza el desnivel positivo indicado.
- **Centro entre mínimo y máximo:** después de deformar y rotar, trasladar Z para que `(zmin+zmax)/2 = 0`. Un desnivel de 1 mm da −0,5/+0,5 mm.
- **Punto mínimo:** trasladar Z para que `zmin=0`. Un desnivel de 1 mm da 0/+1 mm.
- **Subir/bajar toda la pieza:** desplazamiento uniforme posterior a esa referencia.

El centro de los extremos **no es necesariamente la altura media** ponderada por longitud; esta última se incluye en el JSON. z=0 es un plano matemático, no una placa que impida puntos negativos. La inclinación es una rotación rígida alrededor de un eje horizontal cuyo azimut se puede cambiar; conserva la longitud.

Para las ondas se usa una sinusoide a lo largo de la longitud nominal, normalizada al desnivel seleccionado. El bulto usa un perfil gaussiano localizado en la mitad del recorrido. La fase permite desplazar los máximos respecto a los arcos.

**Caída radial:** `z = elevación − desnivel·r/rmax`, con r medido desde el extremo interior. Mantiene XY nominal y el centro fijo; sin inclinación añadida llega exactamente a Z=elevación−desnivel. La vista superior ortográfica conserva su trazado. La imagen de la cámara de medida sí cambia por perspectiva. Este perfil fuerza XY fijo: al introducir pendiente sin acortar XY aumenta la longitud espacial, por lo que no representa una flexión inextensible. La inclinación adicional rota el conjunto alrededor del centro y puede cambiar su planta.

### Dos formas de deformar

**Sin estirar:** para cada segmento nominal de longitud `ds`, se prescribe `dz` y se reduce su avance horizontal a `sqrt(ds²−dz²)`, conservando la dirección XY nominal. Por construcción, cada segmento conserva su longitud. Con «Centro fijo» no se añade traslación XY; las referencias antiguas de alturas conservan el centrado de envolvente para reproducir los resultados anteriores. Es una curva posible, no una solución de equilibrio mecánico ni una predicción de cómo se deforma el polímero. La forma XY puede cambiar.

**XY fijo:** se conservan X e Y y solo se modifica Z. La longitud espacial aumenta. Permite reproducir el tipo de contraejemplo del estudio previo; no debe interpretarse como doblar una pieza inextensible.

El visor representa el **eje** con grosor gráfico. No se deduce una sección circular ni se renderiza una silueta metrológica del hilo.

## Cámara y cálculo

Sensor de referencia: **FLIR Blackfly S BFS-U3-200S6M-C**, variante mono de la oferta, [especificaciones oficiales](https://softwareservices.flir.com/BFS-U3-200S6/latest/Model/spec.html): 5472 × 3648 píxeles de 2,4 µm; área activa derivada 13,1328 × 8,7552 mm. Fuente consultada de nuevo el 2026-11-05; ficha también archivada en el proyecto. Se supone resolución completa, sin binning, decimación ni ROI. «1 pulgada» no es una dimensión activa de 25,4 mm.

Modelo de lente delgada enfocada en el plano calibrado `zc`, cámara a `Z`:

```text
D = Z − zc
v = f·D/(D−f)
FOVx = sensor_x·D/v       FOVy = sensor_y·D/v
mm_por_pixel = 0,0024·D/v

X_interpretada = cx + (X−cx)·D/(Z−z)
Y_interpretada = cy + (Y−cy)·D/(Z−z)
```

La distancia Z parte del centro de proyección del modelo; no se presenta como distancia desde el frontal real de un Computar. Se ignoran diferencias de planos principales/pupila de entrada. Se puede añadir distorsión radial residual sintética; no se dispone de una calibración de la lente real. No se incluyen otras aberraciones, desenfoque, ruido, cuantización, extracción de bordes ni oclusiones.

Con Z y zc fijos, cambiar focal modifica FOV y muestreo, pero el error geométrico continuo de altura **no depende de f**. La focal sí puede provocar recorte. Con distorsión activada, cambiar focal también cambia dónde cae la espiral dentro del campo y su error de distorsión. El botón FOV 200 mm cambia Z según la focal y por tanto sí cambia la sensibilidad a altura.

Se informan tres longitudes, integradas por segmentos:

- **Espacial:** recorrido 3D de la curva construida.
- **Proyección horizontal:** recorrido XY sin perspectiva.
- **Interpretada:** recorrido de los puntos proyectados y convertidos a mm en el plano calibrado.

`Error L = interpretada final − espacial = pérdida de proyección + perspectiva ideal + distorsión residual + sesgo de escala`.

**Error L** es el sesgo determinista de longitud de la configuración simulada, incluyendo los dos errores opcionales; no una incertidumbre, promedio probabilístico ni máximo sobre todas las deformaciones posibles. Un mismo desnivel puede dar distintos errores según pendientes, distribución de alturas y posición. El tooltip desglosa geometría, distorsión y escala.

**Error Ø** muestra el error local de mayor valor absoluto, conservando su signo, para un ancho horizontal ideal de 4 mm por defecto (ajustable en «Más → Ø ideal»). Se construye un segmento perpendicular a la tangente XY local, se proyectan sus dos extremos con la distorsión y escala seleccionadas, y se resta su ancho real. Incluye altura, sesgo de escala y distorsión sintética; no simula una silueta volumétrica, ovalidad, inclinación transversal de una sección física, bordes ni ruido. Con ambos errores a cero se recupera `eØ(z) = Ø·[(Z−zc)/(Z−z)−1]`. A Z=800, zc=0 y z=+1 mm, da +0,005006 mm para Ø=4 mm. Entre −0,5 y +0,5 mm, el máximo absoluto es 0,002502 mm. El tooltip y JSON conservan mínimo y máximo; el grosor del tubo del visor sigue siendo gráfico. La variación de aumento con distancia en óptica convencional está descrita por [Edmund Optics](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/advantages-of-telecentricity), consultado el 2026-11-05; los valores anteriores son cálculos propios.

La escala del panel corresponde al plano calibrado. El factor radial exportado para cada punto escala un **segmento horizontal** a esa altura; no es el Jacobiano completo de una superficie inclinada o alabeada: sus pendientes también alteran las distancias proyectadas.

Se recortan segmentos distorsionados contra el rectángulo del sensor **antes** de aplicar el sesgo de mm/px: equivocarse de escala no cambia qué entra físicamente en la imagen. Si el eje no cabe completo, el panel muestra «Recortada». El error Ø también se oculta si los extremos de los segmentos transversales salen del sensor. El JSON conserva los resultados teóricos completos y sus indicadores de cobertura. No se comprueba una sección volumétrica ni la autooclusión.

## Errores simulados de escala y lente

Son supuestos para estudiar sensibilidad, no coeficientes extraídos de la ficha Computar ni incertidumbres aleatorias. Ambos controles tienen valor inicial **0 %**, que reproduce los resultados anteriores.

- **Escala (−1 a +1 %):** multiplica todas las coordenadas métricas respecto al eje óptico por `S = 1 + escala/100`. Un valor positivo hace las medidas mayores. La escala mostrada en el panel es la aplicada; el campo físico nominal no cambia. Para una espiral plana en el plano calibrado, +0,02 % produce +0,102102 mm en longitud y +0,000800 mm en ancho de 4 mm.
- **Distorsión radial (−5 a +5 %):** porcentaje de desplazamiento radial en la esquina ideal del sensor. Con `R` igual a media diagonal del FOV nominal, `a = distorsión/100` y `r² = x²+y²`, se usa `(xd,yd) = (x,y)·[1+a·r²/R²]`. Es el término radial `k1` de Brown expresado con una normalización intuitiva. Negativo: barril; positivo: cojín. No equivale a aumentar uniformemente la longitud ese porcentaje. El centro coincide con el eje óptico, sin distorsión tangencial.

Orden: geometría 3D → proyección ideal → distorsión → conversión con sesgo de escala → medidas. La escala multiplica el resultado ya distorsionado; no se suman porcentajes de forma aproximada. El JSON conserva `geometry_error_mm`, `distortion_delta_mm` y `scale_delta_mm`, cuya suma es `error_mm`. El CSV incluye coordenadas ideales/finales, error Ø local y ambos parámetros. «Ver proyección» muestra la curva interpretada en el plano; no deforma la pieza física.

Para puntos muy alejados del sensor, a partir de `r=2R` se continúa linealmente el radio distorsionado con su pendiente en 2R. Con el rango permitido sigue siendo monótono y siempre fuera del sensor. Esta extensión evita que un polinomio de barril extrapolado pliegue puntos lejanos hacia la imagen; no cambia el modelo dentro del campo visible. El FOV dibujado sigue siendo el campo nominal sin distorsión.

Base del modelo: [OpenCV, distorsión radial](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html) y [Edmund Optics, definición de distorsión](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/distortion/). La simulación no toma el «0,0 %» redondeado de la ficha como una calibración real.

### Realismo y magnitudes de ensayo: revisión web del 2026-11-05

El control implementa correctamente una distorsión radial de primer orden. Es un modelo de sensibilidad físicamente razonable, pero no identifica la curva del objetivo Computar ni reproduce una campaña de calibración. OpenCV permite términos radiales de orden superior y tangenciales. Edmund explica que objetivos diseñados para poca distorsión pueden presentar distorsión ondulada, con signo variable según el radio; un único `k1` no puede representarla. Un cero nominal en el borde no demuestra cero en todo el campo.

Computar identifica [V3522-MPZ, 35 mm](https://www.computar.com/products/v3522-mpz) y [V7531-MPZ, 75 mm](https://www.computar.com/products/v7531-mpz) como objetivos de muy baja distorsión. Las fichas del fabricante distribuidas en [35 mm](https://cdn.g4.com.tw/wp-content/uploads/images/computar/mpz/mpz_v3522-mpz_datasheet.pdf) y [75 mm](https://www.rmaelectronics.com/content/ComputarGanz-Lenses/V7531-MPZ_en.pdf) indican **0,0 %** para formato 1". No contienen coeficientes, mapa medido de esta pareja cámara/objetivo ni un límite de error dimensional residual. No convertir el redondeo de una cifra decimal en una garantía de ±0,05 %. La FLIR tiene radio de esquina activo calculado de 7,891831 mm; el formato óptico nominal llega a 8 mm, pero esto tampoco identifica la distorsión interior. La página global de la serie anuncia recursos de distorsión, pero devolvió HTTP 503 en esta revisión; no se afirma haber contrastado sus curvas.

Los extremos ±1 a ±5 % del visor son ensayos exagerados, no valores esperados avalados para estos objetivos. Para explorar sensibilidad cerca de cero se proponen **±0,01 %, ±0,05 % y ±0,1 %**, exclusivamente como hipótesis, sin probabilidades ni límites garantizados. Después de corregir la lente real, el control debería representar la **distorsión residual**. Ejemplo reproducido: espiral plana a z=0, cámara a 800 mm, focal 35 mm, eje X=Y=0, ancho 4 mm y escala sin sesgo; +0,05 % radial en esquina produce Error L = +0,018509684 mm y Error Ø = +0,000863605 mm. No son mediciones del equipo.

Tampoco hay un error de escala «típico» deducible de la ficha de cámara. [Calib.io](https://calib.io/pages/faqs) publica para su patrón compuesto estándar una tolerancia de distancias entre marcas de 0,3 mm + 0,2 mm/m: sobre 200 mm equivale a 0,34 mm, o **0,17 %** relativo, si se usan cotas nominales. Es una tolerancia de referencia, no la media de errores de calibración ni necesariamente un sesgo uniforme. Su [guía de calibración](https://calib.io/blogs/knowledge-base/calibration-best-practices) pide fijar enfoque/apertura, trabajar a distancia representativa, cubrir el campo y verificar el patrón; un RMS bajo no acredita escala métrica exacta. Ejemplo geométrico propio: un cambio uniforme de plano de 0,1 mm a 800 mm da aproximadamente 0,0125 % de aumento, ya modelado mediante altura y que no debe sumarse otra vez al control de escala. La [ficha de placas MVTec](https://www.mvtec.com/fileadmin/Redaktion/mvtec.com/products/calibration-plates/2022.07.28_datasheet_calibration_plates_HALCON12_newer.pdf) da 9,5 ppm/K para su vidrio; una variación de 10 K implica 0,0095 % de cambio dimensional del patrón, antes de compensación. Son fuentes diferentes, no cifras transferibles al conjunto sin ensayo.

Para el control de escala se proponen barridos **±0,005 %, ±0,01 %, ±0,02 %, ±0,05 % y ±0,1 %**. Son escenarios para fijar un presupuesto y diseñar la validación, no prestaciones prometidas. Sobre L=510,508806 mm y Ø=4 mm, respectivamente: 0,01 % → 0,051051/0,0004 mm; 0,02 % → 0,102102/0,0008 mm; 0,05 % → 0,255254/0,0020 mm; 0,1 % → 0,510509/0,0040 mm. Reservar 0,1 mm completo a escala de longitud exigiría |sesgo| <0,0195883 %; si se reparte con otras contribuciones, la parte de escala debe ser menor. No se cambian rangos, valores iniciales ni interfaz por esta revisión documental.

## Resultados de referencia

[scenarios.json](scenarios.json) se genera con Python, paso máximo 0,02 mm. Cámara Z=800 mm, focal 35 mm, plano calibrado zc=0, eje óptico X=Y=0. Todas las curvas de esta tabla están dentro del FOV y usan errores simulados a cero. La inclinación se realiza alrededor del eje Y; las ondas son tres ciclos con fase cero. Los siete casos históricos de la tabla conservan sus referencias originales; el JSON añade cinco casos de centro fijo, bulto y caída radial y cuatro casos con errores de escala/distorsión.

| Caso | Alturas (mm) | Error interpretada − espacial (mm) |
| --- | --- | ---: |
| Plana en referencia | 0/0 | 0 |
| Elevación uniforme | +1/+1 | +0,638935 |
| Inclinación rígida centrada | −0,5/+0,5 | −0,023126 |
| Inclinación rígida desde apoyo | 0/+1 | +0,296120 |
| Tres ondas sin estirar, centradas | −0,5/+0,5 | −0,022390 |
| Tres ondas sin estirar, desde apoyo | 0/+1 | +0,296877 |
| Tres ondas, XY fijo, centradas | −0,5/+0,5 | −0,022383 |

Son resultados de **esas curvas y posiciones**. No son errores garantizados para una pieza con el mismo alabeo máximo. En el caso centrado sin estirar, la proyección contribuye aproximadamente −0,043502 mm y la perspectiva +0,021112 mm; se compensan parcialmente.

## Reproducir y comprobar

Python usa solo biblioteca estándar:

```powershell
py -3.11 -X utf8 inspection_cell/hardware/research/spiral_simulator/model.py
py -3.11 -X utf8 inspection_cell/hardware/research/spiral_simulator/model.py --output inspection_cell/hardware/research/spiral_simulator/scenarios.json
```

Desde esta carpeta, para modificar/reconstruir el visor:

```powershell
npm ci
npm run build
npm run check
npm run check:browser
```

`model.py` y `model.js` contienen el cálculo; `app.js` el visor; `index.template.html` la interfaz; `build.mjs` produce el HTML autónomo. Dependencias de construcción aisladas: Three.js 0.180.0, esbuild 0.25.0 y playwright-core 1.56.1. La prueba de navegador utiliza Chrome instalado en la ruta Windows indicada en `browser_checks.mjs`; puede adaptarse a otra instalación. Licencia de Three incluida en [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).

Verificación realizada el 2026-11-05:

- Elevación uniforme contrastada con fórmula analítica, plano de calibración trasladado y rotación rígida.
- Conservación de **cada segmento** en 18 combinaciones de forma, desnivel y ondas; comparación XY fijo.
- Correspondencia Python/JavaScript en dieciséis escenarios, tolerancia 5·10⁻⁸ mm para las magnitudes contrastadas.
- Centro fijo en XYZ al cambiar desnivel, fase, elevación e inclinación; bulto entre 0 y desnivel; caída radial con XY nominal, descenso progresivo y extremos de altura correctos.
- Error Ø contrastado con fórmula analítica para elevación positiva, caída negativa, cambio de diámetro y cambio de plano calibrado.
- Comprobaciones de FOV, recorte parcial/total, invariancia del error geométrico con focal a Z fijo y descomposición del error total.
- Sesgo de escala contrastado analíticamente y distorsión radial contrastada en orientaciones radial/tangencial; comprobación de que los controles no modifican la pieza física ni que el sesgo de escala cambie la cobertura del sensor.
- Convergencia de 0,05 a 0,02 mm: diferencia del error inferior a 10⁻⁶ mm en el ejemplo centrado inicial. El déficit de longitud nominal por discretización se informa aparte, no como deformación física.
- Prueba del HTML sin servidor en Chrome: WebGL, paneles plegados, controles, giro con botón central, desplazamiento con Ctrl, zoom, vistas, exportaciones y pantalla de 390 px, sin peticiones de red ni errores JavaScript. Capturas de revisión en `qa/`, ignoradas por Git.

La resolución numérica comprueba este modelo, **no la exactitud de la celda ni la mecánica del material**.

## Auditoría independiente de cálculo — 2026-11-05

Solicitada tras añadir centro fijo, caída radial y error Ø. Se verificaron la cámara de la oferta y las ecuaciones frente a documentación primaria, además de contrastar el cálculo sin reutilizar la fórmula directa de proyección del simulador.

- **52 configuraciones con OpenCV:** proyección 3D a píxeles mediante `projectPoints`, con coeficiente radial independiente, y vuelta al plano mediante la inversa de una homografía. Incluye 16 referencias, 24 combinaciones de geometría/óptica y 12 combinaciones adicionales de escala/distorsión. Se comprueban coordenadas, longitud, límites del sensor y segmentos transversales. Máxima diferencia de coordenadas: 4,0·10⁻¹³ mm; es concordancia numérica, no precisión física.
- **7 curvas analíticas:** integración continua de la longitud 3D y de la derivada proyectada con SciPy, independiente de la suma de cuerdas. Incluye inclinación de 12°, ondas de 20 mm/8 ciclos, bulto y caída radial. Máxima diferencia del error mostrado frente a esta referencia: 0,0000070 mm en estos casos.
- **Refinamiento aplicado:** paso por defecto reducido de 0,05 a **0,01 mm** en Python y JavaScript. En el caso extremo sin estirar probado, la diferencia frente al paso 0,005 mm baja de 0,00046925 a 0,00001524 mm. Estos valores describen los casos ensayados, no una cota global certificada.
- **16 comparaciones Python/JavaScript**, conservación de longitud por segmento, centro fijo, signos, referencias de altura, escala analítica y estiramiento radial/tangencial. Prueba de navegador con panel nuevo, valores iniciales cero, composición, restauración, exportación y disposición móvil. La longitud se identifica como «Error L» a petición del usuario.

Resultados y reproducción: [audit.py](audit.py), [audit_results.json](audit_results.json). El script de auditoría requiere NumPy, SciPy y OpenCV; sus versiones quedan registradas en el JSON. No son dependencias del HTML ni de `model.py`.

```powershell
py -3.11 -X utf8 audit.py
```

Con zc=0, Z=800 mm y la **focal inicial de 35 mm**, el modelo obtiene FOV **287,045486 × 191,363657 mm** y muestreo **0,052457143 mm/px**. Elevar una curva plana 1 mm produce **+0,638934676 mm** en longitud y **+0,005006258 mm** en el ancho horizontal de 4 mm.

La cámara no determina la focal. La oferta original incluye la **Computar de 75 mm**; los 35 mm del visor corresponden a la alternativa priorizada en el estudio. Con 75 mm y Z=800 mm, el FOV ideal baja a **126,9504 × 84,6336 mm** y recorta esta espiral. El visor identifica ese recorte.

**Alcance de Ø confirmado:** se mide la proyección de un segmento horizontal, ahora incluyendo los errores opcionales. No es una fórmula completa del ancho de una sección inclinada ni de la silueta de un tubo. Contraejemplo sin errores añadidos: un segmento de 4 mm centrado en Z=0 e inclinado 12° presenta aproximadamente −0,0874 mm de error proyectado, mientras el término de escala por altura de su centro es cero. No se asume que ese segmento describa la sección real; demuestra por qué el máximo mostrado no limita el error físico completo.

**Alcance óptico confirmado:** el modelo combina proyección central y lente delgada enfocada al plano calibrado, con sesgos sintéticos opcionales de escala y distorsión. No reenfoca punto a punto al deformar la pieza. La altura parte del centro de proyección ideal; no equivale a medir 800 mm desde la carcasa o el frontal del objetivo. La focal nominal y el píxel bastan para esta estimación, pero el montaje real requiere calibrar intrínsecos/distorsión o el mapa del plano, y validar bordes, desenfoque y sección. No se dispone de una calibración individual de la pareja FLIR/Computar.

Fuentes contrastadas, consultadas el 2026-11-05:

- [FLIR: especificaciones del modelo](https://softwareservices.flir.com/BFS-U3-200S6/latest/Model/spec.html): resolución, paso, sensor y modos parciales.
- [OpenCV: Camera Calibration and 3D Reconstruction](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html): proyección pinhole, intrínsecos, extrínsecos y distorsión. Sustenta la comprobación de proyección, no certifica este simulador.
- [Edmund Optics: Understanding Focal Length and Field of View](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/understanding-focal-length-and-field-of-view/): formato del sensor, focal, campo y límites de distancias paraxiales frente a cotas mecánicas.
- [Edmund Optics: The Advantages of Telecentricity](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/advantages-of-telecentricity): variación de aumento con distancia en óptica convencional.
- [Computar V3522-MPZ](https://www.computar.com/products/v3522-mpz): focal nominal de 35 mm; la [ficha archivada del V7531-MPZ](../../components/lens_v7531_mpz.md) documenta los 75 mm de la oferta.
