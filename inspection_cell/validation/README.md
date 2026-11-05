# Validación de la celda

Estado: protocolos iniciales, **ningún ensayo de la celda ejecutado**. Esta carpeta separa los requisitos de la evidencia de que se cumplen.

| Protocolo | Qué debe demostrar |
| --- | --- |
| [Primeras comprobaciones de laboratorio](protocols/first_lab_checks.md) | Resolver peso, sección, apoyo y repetición con el pie de rey y básculas disponibles |
| [Medición dimensional](protocols/dimensional_accuracy.md) | Magnitud definida, error, repetibilidad, altura y campo útil |
| [Pesaje y disparo](protocols/weighing_and_trigger.md) | Peso fiable y detección/captura estable |
| [Integración](protocols/integration.md) | Imagen, peso y resultados asociados a la pieza/ciclo correctos |

Antes de ejecutar, acordar referencias, incertidumbres, muestras/repeticiones y criterios de aceptación. **0,1 mm es orientativo**, no un límite obligatorio común: evaluar longitud y diámetro por separado y determinar variación detectable. En peso se desea 0,01 g y se considera 0,1 g un mínimo justo; verificar sensibilidad real sobre la precarga final y con piezas recién desmoldeadas. No deducir cumplimiento de los decimales de pantalla.

Guardar las conclusiones en [reports/](reports/README.md), con configuración y evidencia. No interpretar una simulación o revisión documental como validación de hardware.

Hay una [plantilla de registro de banco](templates/bench_record.md) para conservar lecturas y condiciones sin inventar datos.
