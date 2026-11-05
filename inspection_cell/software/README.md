# Software de inspección

Estado: estructura y diseño inicial. Todavía no hay aplicación ejecutable, drivers de la celda, dependencias fijadas ni integración desplegada.

La aplicación deberá detectar colocación/estabilidad desde la báscula, capturar la imagen, calcular medidas con calibración, conservar evidencia y asociar cada inspección con el ciclo de inyección correcto.

| Ruta | Uso previsto |
| --- | --- |
| [architecture.md](architecture.md) | Responsabilidades y contrato de integración por definir |
| [src/inspection_cell/](src/inspection_cell/README.md) | Futura aplicación con módulos de equipos, inspección y persistencia |
| [config/](config/README.md) | Configuración de estación, recetas y referencias de calibración |
| [tests/](tests/README.md) | Pruebas de comportamiento y contratos |
| [tools/](tools/README.md) | Diagnóstico y utilidades de desarrollo |

Se prevé entorno y proceso propios para independizar cámara/báscula de la adquisición DAQ. Cuando se elijan SDK y runtime se añadirá el archivo de dependencias/empaquetado aquí; no se incorporan paquetes de visión a las dependencias actuales por anticipado.

La geometría suministrada permanece en [hardware/mechanical/geometry](../hardware/mechanical/geometry/README.md) como referencia, sin convertirla en un algoritmo de medición de piezas reales.
