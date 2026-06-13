# Hermes

Hermes es una aplicacion de escritorio para preparar la conciliacion de
materiales entre requerimientos de ingenieria e inventario disponible.

## Alcance del Sprint 1

El Sprint 1 no incluye todavia el motor de interpretacion dimensional ni la asignacion automatica de inventario. Esos elementos pertenecen al Sprint 2.

El incremento de Sprint 1 incluye:

- Carga de archivo de inventario en formato `.xlsx`.
- Carga de archivo de requerimientos en formato `.xlsx`.
- Seleccion dinamica de columnas relevantes.
- Vista previa de los datos cargados.
- Selector de tema claro u oscuro desde el menu de configuracion.
- Validacion de configuracion minima.
- Interfaz base para usuarios no tecnicos.
- Documentacion inicial del marco Scrum.

## Arquitectura

La aplicacion esta separada por responsabilidades:

```text
hermes/
├── main.py
├── pyproject.toml
├── requirements.txt
├── src/
│   └── hermes/
│       ├── application.py
│       ├── config.py
│       ├── domain/
│       ├── services/
│       └── ui/
└── tests/
```

`domain` contiene el estado y los modelos, `services` concentra la lectura y
validacion de datos, y `ui` solo se ocupa de la interfaz PySide6.

## Requisitos

- Python 3.10 o superior
- Un entorno grafico de escritorio

## Instalacion

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

En Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Ejecucion

```bash
source .venv/bin/activate
hermes
```

Tambien se conserva el punto de entrada del repositorio:

```bash
.venv/bin/python main.py
```

## Pruebas

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
pytest
```

Las pruebas usan el backend `offscreen` de Qt, por lo que no abren ventanas.

## Uso

1. Ejecutar la aplicacion.
2. Cargar el archivo de inventario.
3. Cargar el archivo de requerimientos.
4. Alternar entre ambos archivos con el selector de la vista previa.
5. Seleccionar columnas relevantes de ambos archivos.
6. Validar la configuracion.
7. Activar opcionalmente `Configuracion > Modo oscuro`.
8. Confirmar que la informacion esta lista para el siguiente procesamiento.

## Roadmap inmediato

- Sprint 1: carga de datos, configuracion e interfaz base.
- Sprint 2: extraccion dimensional y motor de conciliacion.
- Sprint 3: reportes, validacion, documentacion y demo final.
