# Hermes

Hermes es un MVP academico y operativo para apoyar la conciliacion de materiales entre requerimientos de ingenieria e inventario disponible.

Este repositorio queda estructurado para el Sprint 1 del proyecto, con una duracion de una semana. El objetivo de este incremento es construir la base funcional del producto: carga de archivos, seleccion de columnas e interfaz inicial.

## Alcance del Sprint 1

El Sprint 1 no incluye todavia el motor de interpretacion dimensional ni la asignacion automatica de inventario. Esos elementos pertenecen al Sprint 2.

El incremento de Sprint 1 incluye:

- Carga de archivo de inventario en formato `.xlsx`.
- Carga de archivo de requerimientos en formato `.xlsx`.
- Seleccion dinamica de columnas relevantes.
- Vista previa de los datos cargados.
- Validacion de configuracion minima.
- Interfaz base para usuarios no tecnicos.
- Documentacion inicial del marco Scrum.

## Estructura del repositorio

```text
hermes/
├── README.md
├── requirements.txt
├── .gitignore
├── main.py
├── src/
│   └── hermes_app.py
└── docs/
    └── scrum/
        ├── product_backlog.md
        ├── sprint_1.md
        └── definition_of_done.md
```

## Requisitos

- Python 3.10 o superior
- pandas
- openpyxl

## Instalacion

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

En Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecucion

```bash
python main.py
```

## Uso esperado en Sprint 1

1. Ejecutar la aplicacion.
2. Cargar el archivo de inventario.
3. Cargar el archivo de requerimientos.
4. Seleccionar columnas relevantes de ambos archivos.
5. Validar la configuracion.
6. Confirmar que el equipo ya tiene una base funcional para iniciar el Sprint 2.

## Roadmap inmediato

- Sprint 1: carga de datos, configuracion e interfaz base.
- Sprint 2: extraccion dimensional y motor de conciliacion.
- Sprint 3: reportes, validacion, documentacion y demo final.
