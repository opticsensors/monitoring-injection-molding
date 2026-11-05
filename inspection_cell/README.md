# Celda de inspección de espirales

Estado: definición de requisitos y estudio de hardware. Actualizado: 2026-11-04.

Celda del proyecto Machina para obtener automáticamente una imagen cenital y el peso de una espiral inyectada —PP inicialmente y otros materiales futuros—, evaluar avance de llenado, longitud y ancho del hilo, y asociar los resultados al ciclo de inyección correspondiente.

La celda todavía no está construida. Esta carpeta reúne el contexto, las fuentes, las alternativas y el espacio de trabajo para desarrollar hardware y software dentro del mismo repositorio. Los equipos siguen en estudio; **0,1 mm es una orientación, no un límite obligatorio común para longitud y diámetro**. Se inspeccionará recién desmoldeada; báscula hasta 300 € con IVA y conexión, con 0,01 g deseado.

## Empezar aquí

**Para retomar una sesión:** [estado de investigación y respuestas ya recibidas](docs/research_status.md). Última revisión: [dictamen de viabilidad](hardware/research/deep_dive_2026-11-04/feasibility.md), [investigación ampliada y evidencias](hardware/research/deep_dive_2026-11-04/README.md), [básculas económicas](hardware/components/scales_shortlist.md) y [primeras pruebas de laboratorio](validation/protocols/first_lab_checks.md).

1. [Requisitos](docs/requirements.md): datos conocidos, objetivos y magnitudes pendientes.
2. [Resumen visual de la propuesta Machina](docs/presentation_summary.md): contenido del PowerPoint, imágenes y referencias comerciales.
3. [Geometría y sensores](docs/geometry_reference.md): longitud teórica de 510,5088 mm y posiciones extraídas de `spiral_sensors.py`.
4. [Preguntas abiertas](docs/open_questions.md) y [decisiones](docs/decisions.md): qué falta resolver y qué se ha acordado.
5. [Metrología](hardware/research/metrology.md): límites de una imagen 2D, altura de la pieza y plan de comprobación.

## Estructura

```text
inspection_cell/
├── README.md
├── docs/                       Contexto común y especificación de la celda
│   ├── README.md               Índice de documentación
│   ├── overview.md
│   ├── requirements.md
│   ├── measurement_definition.md
│   ├── research_status.md
│   ├── workflow.md
│   ├── decisions.md
│   ├── open_questions.md
│   ├── geometry_reference.md
│   ├── presentation_summary.md
│   ├── sources.md
│   ├── assets/presentation/    Imágenes extraídas y vistas de diapositivas
│   └── references/             PowerPoint original e índices de procedencia
├── hardware/
│   ├── README.md
│   ├── research/               Visión, iluminación, pesaje, manipulación y metrología
│   ├── components/             Candidatos, BOM preliminar, fichas y ofertas
│   ├── mechanical/             Estructura, soporte, geometría y referencias CAD
│   └── electrical/             Alimentación, conexiones y cableado
├── software/
│   ├── README.md
│   ├── architecture.md         Arquitectura e integración propuestas
│   ├── config/                Futuras configuraciones de equipos y recetas
│   ├── src/inspection_cell/    Espacio para la futura aplicación
│   ├── tests/                 Pruebas previstas del software
│   └── tools/                 Espacio para utilidades de desarrollo
└── validation/
    ├── README.md
    ├── protocols/             Ensayos dimensionales, pesaje e integración
    ├── templates/             Plantillas vacías para registrar pruebas
    └── reports/               Resultados de ensayos, todavía sin ejecutar
```

## Cómo mantener este contexto

- Los [requisitos](docs/requirements.md) son la referencia de lo que debe conseguir la celda. Los valores desconocidos se mantienen como **TBD**, sin sustituirlos por estimaciones.
- Las [decisiones](docs/decisions.md) separan acuerdos, propuestas y alternativas descartadas. Una oferta no implica compra ni selección final.
- Las investigaciones registran fuente, fecha, supuestos, cálculo y ensayo pendiente. Los cálculos teóricos no son resultados medidos.
- Las copias de fuentes conservan su contenido. Su procedencia y huellas están en [sources.md](docs/sources.md) y en el [manifiesto](docs/references/source_manifest.json).
- La documentación de esta carpeta está pensada para versionarse; es independiente de las notas locales ignoradas de `/docs/` en la raíz del repositorio.
- Las capturas de operación, credenciales y registros voluminosos irán a almacenamiento de ejecución; aquí se conservarán solo muestras y evidencias seleccionadas.

El software de adquisición existente sigue en la raíz y la infraestructura compartida en `iot/`. Esta fase prepara documentación y referencias; la aplicación de inspección aún no está implementada.
