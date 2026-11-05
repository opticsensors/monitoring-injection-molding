# Alternativas de lente y cómo compararlas

Consulta: 2026-11-04. La conclusión geométrica es **probar primero focal cercana a 35 mm** para el FOV de 150–200 mm y el sensor FLIR. Elegir la focal no selecciona automáticamente fabricante ni garantiza error. Precios sin oferta final a España.

| Lente | Datos relevantes publicados | Precio observado / situación | Qué probar |
| --- | --- | --- | --- |
| [Computar V3522-MPZ](https://www.computar.com/products/v3522-mpz) | 35 mm, f/2,2–16, círculo 16 mm, enfoque desde 0,2 m; ficha local disponible | Precio de STEMMER para esta focal pendiente; la oferta archivada es de **75 mm**, no de esta | FOV, distancia frontal, contraste en esquinas y distorsión residual a abertura/distancia reales |
| [VA-LCM-20MP-35MM-F2.8-110](https://va-imaging.com/en-us/products/lens-c-20mp-35mm-f2-8-1-1-va-lcm-20mp-35mm-f2-8-110) | 1,1 pulgadas, C-mount, f/2,8, MOD 200 mm, 100 g; distorsión anunciada <0,02 % | **280 €** en datos públicos de variante de tienda europea; la página estadounidense muestra USD. Fiscalidad/entrega pendientes | Ficha web recomienda píxel 2,75 µm y anuncia 160 lp/mm; nuestra FLIR tiene 2,4 µm. No es prueba de inutilidad ni de aprovechamiento completo de 20 MP |
| [VA-LCM-25MP-35MM-F2.8-110](https://va-imaging.com/products/lens-c-mount-25mp-35mm-f2-8-1-1-va-lcm-25mp-35mm-f2-8-110) | 1,1 pulgadas, C-mount, f/2,8, MOD 150 mm; distorsión anunciada <0,15 % | **350 €**, fiscalidad/entrega pendientes | No escoger por «25 MP» sin contraste medido; su distorsión anunciada no es menor que la anterior |
| [Basler C11-3520-12M-P](https://docs.baslerweb.com/c11-3520-12m-p) | 35 mm ±5 %, círculo 17,6 mm, f/2–16; diseño 140 lp/mm; distorsión típica −0,10 %, distancia óptima 0,5 m | Sin precio europeo final verificado; candidata técnica secundaria | A 0,63–0,83 m y con píxel 2,4 µm queda por demostrar rendimiento. Su ficha sí publica MTF con condiciones |
| [Kowa LM35FC24M](https://www.kowa-lenses.com/de/LM35FC24M-1.1-35mm-24MP-C-mount-Objektiv/12117) | 35 mm, 1,1 pulgadas, f/1,8–16, 205 g; 200/100 lp/mm centro/borde; TV distortion 0,01 % | **813 € sin IVA** en tienda del fabricante | No aporta ahorro a esta selección; no priorizar salvo ventaja demostrada en muestras |

La tienda VA publica [costes de gestión/envío](https://va-imaging.com/pages/vision-camera-frequently-asked-questions): 19 € estándar y 79 € exprés, con plazos distintos. Confirmar aplicación al pedido conjunto, IVA y disponibilidad; no presentarlos como presupuesto cerrado. La política B2B no garantiza un préstamo gratuito.

## Comparaciones que inducen a error

1. «Sin distorsión» es un nombre comercial. Incluso el 0,0 % redondeado de una ficha no equivale a cero en cada punto y distancia. La distorsión es un campo espacial; no aplicar su porcentaje como si fuese un único error de escala sobre 510 mm.
2. Megapíxeles de lente, píxel recomendado y lp/mm no son unidades intercambiables. Importan MTF, contraste, abertura, distancia, longitud de onda y posición en el campo. El muestreo de la FLIR tiene Nyquist de aproximadamente 208,3 lp/mm en sensor; eso no significa que toda la óptica deba transmitir esa frecuencia para localizar un borde con precisión útil.
3. Una lente para sensor de 2/3 pulgadas no cubre por defecto la diagonal activa de 15,78 mm de esta cámara. No elegir una de 35 mm barata solo por focal y rosca C.
4. Enfoque/iris automáticos o cambiados entre piezas alteran la condición de calibración. Para la maqueta, bloquear ajustes tras calibrar y registrar cada cambio.

## Hallazgos de calidad de fuente

El buscador extrae «LIMITED QUANTITY» y «DISCONTINUED» de la página Computar V3522-MPZ. Al revisar el HTML del fabricante, **ambos elementos tienen `w-condition-invisible`**; sucede también en V7531-MPZ y V3528-MPY. No se puede concluir fin de vida a partir de ese texto extraído. La disponibilidad se confirma comercialmente cuando proceda comprar.

El índice web de [VA, resolución v1.5](https://hs.va-imaging.com/hubfs/Supportshare/Lenses/Lens_resolution_data_v1.5.pdf) muestra para la 20MP de 35 mm MTF >0,35 a 160 lp/mm en centro y aproximadamente 0,3 a 110 lp/mm en esquina, pero la descarga respondió **404** y el portal anuncia v1.7. No hay PDF local ni confirmación de esas condiciones en revisión actual. Pedir curva vigente a distancia y abertura de uso, en vez de tomar un número de marketing como garantía.

Recomendación: pedir demostración/oferta de **Computar 35 mm y VA 35 mm de 280 €** con las mismas muestras. Mantener FLIR y la alternativa Daheng ya documentada como opciones de cámara; cambiar de marca no corrige perspectiva, apoyo ni ocultación por colada.

La [FAQ de VA](https://va-imaging.com/pages/vision-camera-frequently-asked-questions) también anuncia préstamos sujetos a condiciones. Conviene pedir el conjunto óptico de ensayo, con su distancia y apertura, antes de elegir entre 20 y 25 MP comerciales. No se ha contactado al proveedor.
