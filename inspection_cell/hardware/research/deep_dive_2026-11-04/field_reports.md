# Experiencias de usuarios: qué aprender y qué no concluir

Consulta: 2026-11-04. Son testimonios, no ensayos de nuestra celda ni especificaciones verificadas. Las decisiones se apoyan también en documentación primaria. No se ha contactado a sus autores.

| Fuente leída | Observación o consejo del hilo | Utilidad para Machina | Límite |
| --- | --- | --- | --- |
| [Reddit: High precision measurement](https://www.reddit.com/r/computervision/comments/1l3s907/high_precision_measurement/) | Se discuten altura constante, calibración, perfiles de borde y prioridad de la iluminación para piezas de 5–10 cm | Ensayar iluminación y plano de medida antes de cambiar cámara o algoritmo; consultar la guía MVTec enlazada en el hilo | No demuestra ±25 µm ni transfiere prestaciones a un FOV de 200 mm y una espiral alabeada |
| [Reddit: Small measurement drift](https://www.reddit.com/r/MachineVisionSystems/comments/1su7dll/seeing_small_measurement_drift_not_sure_whats/) | El autor observa deriva; otros proponen iluminación ambiente, umbral, temperatura y vibración como causas | Registrar una referencia fija junto a la pieza y repetir durante el calentamiento del equipo | Las causas son hipótesis. La recomendación general de abandonar USB por GigE no está demostrada; no se adopta |
| [Reddit: Experiences with computer vision in quality](https://www.reddit.com/r/manufacturing/comments/18ekgaq/experiences_with_computer_vision_in_quality/) | Experiencias industriales insisten en iluminación, variación de piezas y pruebas con muestras propias | Validar varias condiciones y materiales, incluyendo piezas difíciles; pedir demostración con nuestras muestras | Mezcla testimonios y promoción comercial. No asumir que toda visión solo sirve para presencia/ausencia ni que la IA resuelve cualquier borde |
| [Reddit: HX711 drift](https://www.reddit.com/r/AskElectronics/comments/1ce8ns9/) | Se describe deriva de varios gramos en un montaje propio; cambiar alimentación no resuelve el problema relatado | En un prototipo con célula de carga, probar mecánica, temperatura, cero y tiempo bajo carga por separado | Modelo y montaje diferentes; no establece el error de un HX711 ni de una báscula comercial concreta |
| [Reddit: Load-cell project](https://www.reddit.com/r/embedded/comments/cophkh/) | Un proyecto de pesaje de cargas grandes relata dificultades con temperatura, histéresis y creep | El coste del sensor no representa el coste de conseguir un sistema de medida estable | Cargas y objetivos muy distintos de nuestros 0,01 g; no extrapolar sus cifras |
| [Reddit: Laboratory scales in food science](https://www.reddit.com/r/foodscience/comments/179gn1q/) | Usuarios describen uso continuado de Ohaus y sensibilidad a vibraciones | Probar la báscula en la mesa real, cerca de la máquina, además de en el laboratorio | Satisfacción de compra no equivale a calibración; no valida un modelo económico alternativo |
| [Reddit: Small additions not registered](https://www.reddit.com/r/DIYfragrance/comments/1wixc9m/any_scale_recommendations/) | Un usuario observa que una báscula no refleja incrementos pequeños aunque otra más barata sí | Añadir masas pequeñas después de tarar una precarga grande; comparar colocación rápida y adición gradual | Modelos y protocolo incompletos. No demuestra por sí solo si la causa es filtro, cero automático, resolución o avería |
| [Reddit: Optical metrology hardware and GRR](https://www.reddit.com/r/Metrology/comments/1lrd8ln/help_with_hardware_in_an_optical_metrology_system/) | Un autor obtiene poca variación sin mover la pieza, pero falla al retirar/reponer cinco piezas; usa perfiles de aluminio y reconoce holguras/enfoque | Distinguir repetición estática de reproducibilidad de colocación; probar estructura, localizadores y plano | Los objetivos eran del orden de 10 µm y otra geometría. Los comentarios sobre prestaciones submicrométricas no son ensayos disponibles ni exigen comprar un sistema de 30–50 mil USD |
| [Reddit: Incorrect reading on scale](https://www.reddit.com/r/chemhelp/comments/10ewaez/incorrect_reading_on_scale/) | Con una masa de 2 kg el autor relata aumento de 0,04 g y retorno incompleto al cero tras retirarla | Registrar una secuencia temporal carga/descarga y no solo una lectura final | No identifica modelo ni demuestra causa; no convierte 0,04 g en error típico de todas las básculas de 2 kg |
| [Reddit: Scale shopping](https://www.reddit.com/r/DIYfragrance/comments/1ppxset/scale_shopping/) | Un propietario atribuye perturbaciones de tara a la fuerza necesaria para pulsar el botón y a la flexión de carcasa | Después de tarar, comprobar recuperación y evitar apoyar la mano sobre el conjunto | Otros modelos/capacidades; una unidad fue recibida para reseña. No trasladar el juicio de marca a USS-DBS28-50 |

## Contraste con fuentes técnicas

- MVTec describe perfiles de intensidad y localización subpíxel de bordes: [manual archivado](sources/MVTec_1D_Measuring_26_05.pdf), pp. 9–11. Esto justifica estudiar el borde en gris, pero no garantiza una incertidumbre concreta.
- A&D describe fuerzas electrostáticas de plásticos **y vidrio**, y aclara que conectar a tierra la báscula no elimina toda inducción: [manual archivado](sources/AD4212D_system_weighing_manual.pdf), p. 16. Es un equipo de prestaciones muy superiores; solo trasladamos el mecanismo físico.
- La propia SBS-LW-1030 permite configurar seguimiento de cero y filtros: [manual](../../components/datasheets/SBS-LW-1030_manual.pdf). Por eso el ensayo de pequeños incrementos debe registrar esos ajustes.
- [Basler](https://docs.baslerweb.com/electronic-shutter-types) distingue rolling shutter, global shutter y global reset. Una recomendación de foro no sustituye comprobar el modo de exposición y la iluminación de la cámara concreta.

## Consecuencias para nuestras pruebas

1. Una misma pieza, sin moverla, separa parte del ruido de captura del error de recolocación.
2. Retirarla y recolocarla revela errores que una secuencia de imágenes estáticas oculta.
3. Un patrón rígido repetido al principio y al final ayuda a distinguir deriva del equipo de contracción de una pieza caliente.
4. Una lectura estable puede estar sesgada o filtrada. Comprobar respuesta a incrementos conocidos y retorno al cero.
5. Guardar configuración y material junto a cada ensayo. No llamar «validado para plásticos» a un resultado obtenido con una sola muestra.

No se conserva un volcado masivo de Reddit: estos resúmenes, enlaces y ensayos derivados son el contexto útil para retomarlo.
