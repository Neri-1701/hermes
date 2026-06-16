# Hermes 0.4.0

Hermes es una aplicacion para segmentar y conciliar materiales entre
requerimientos de ingenieria e inventario disponible. La version 0.4.0 integra
el parser tecnico trazable con busqueda y asignacion de existencias.

## Alcance actual

La aplicacion conserva las funciones de carga y configuracion del Sprint 1:

- Carga de archivo de inventario en formato `.xlsx`.
- Carga de archivo de requerimientos en formato `.xlsx`.
- Seleccion dinamica de columnas relevantes.
- Vista previa de los datos cargados.
- Selector de tema claro u oscuro desde el menu de configuracion.
- Validacion de configuracion minima.
- Interfaz base para usuarios no tecnicos.
- Documentacion inicial del marco Scrum.

Hermes 0.4.0 tambien incluye:

- Normalizacion controlada sin destruir el texto original.
- Localizacion ordenada de ESPARRAGOS, EMPAQUES, TUBERIA, BRIDAS y CODOS.
- Extractores independientes por familia.
- Parsers compartidos de pulgadas, clase, cedula, espesor, material y normas.
- Llaves canonicas comparables por familia.
- `confidence_score`, warnings y evidencia con posiciones en el texto original.
- Uso de `Data_DescripcionPartida` solo como respaldo de
  `Data_DescripcionMaterial`.
- Cruce tecnico entre requerimientos e inventario por atributos de familia.
- Descuento secuencial de existencias para evitar asignaciones duplicadas.
- Coincidencias parciales visibles para revision, sin descuento automatico.
- Vistas de cruce, segmentacion de requerimientos y segmentacion de inventario.

El predictor de valvulas no forma parte de esta entrega.

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
│       │   ├── material_parser.py
│       │   ├── reconciliation.py
│       │   └── material_parsing/
│       └── ui/
└── tests/
```

`domain` contiene el estado y los modelos, `services` concentra la lectura y
validacion de datos, y `ui` solo se ocupa de la interfaz PySide6.

### Flujo de datos

1. `ExcelReader` valida el archivo, normaliza sus encabezados y crea un
   `LoadedDataset`.
2. `HermesState` conserva un dataset por origen y los mapeos elegidos por el
   usuario.
3. `DataFrameTableModel` limita la cantidad de filas mostradas sin modificar
   el dataframe completo.
4. `SetupValidator` comprueba que ambos archivos y todos los mapeos requeridos
   esten disponibles antes del siguiente procesamiento.
5. `MaterialParser` normaliza, localiza la familia, ejecuta un solo extractor,
   genera la llave canonica y valida la confianza del resultado.
6. `ReconciliationService` segmenta ambos origenes, busca compatibilidad
   tecnica y asigna solamente coincidencias exactas.
7. La interfaz presenta el cruce y los saldos resultantes en la misma tabla.

Los archivos `.xlsx` sin filas se rechazan. Tambien se rechazan encabezados
duplicados despues de eliminar espacios al inicio y al final, porque producirian
mapeos ambiguos.

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

## Parser de materiales

El servicio puede procesar una descripcion individual:

```python
from hermes.services import MaterialParser

result = MaterialParser().parse_description(
    'TUBO, DE 2" DE DIAMETRO NOMINAL, CEDULA 80, '
    "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B",
    source_row=2,
)

payload = result.to_dict()
```

Tambien puede procesar un dataframe completo. Por defecto busca
`Data_DescripcionMaterial` y usa `Data_DescripcionPartida` como respaldo:

```python
results = MaterialParser().parse_dataframe(dataframe)
rows = [result.to_dict() for result in results]
```

## Cruce de inventario

El cruce usa los mapeos seleccionados en la interfaz. Una coincidencia se
considera exacta solo cuando los atributos tecnicos relevantes de la familia
coinciden y ninguna descripcion presenta warnings bloqueantes.

- Las coincidencias exactas descuentan inventario en orden de requerimiento.
- Un requerimiento puede cubrirse con varios renglones de inventario.
- El saldo disponible se conserva por codigo y fila de origen.
- Las coincidencias parciales se muestran como `REVISION_REQUERIDA`, pero no
  reservan ni descuentan existencias.
- Los conflictos de cedula/espesor, dimensiones ambiguas y materiales no
  segmentados nunca se asignan automaticamente.

## Busqueda rapida

La barra `Busqueda rapida` interpreta una descripcion escrita por el usuario
con el mismo parser y las mismas reglas tecnicas del cruce. Solo requiere el
archivo de inventario y sus columnas de descripcion, codigo y cantidad.

- Busca ESPARRAGOS, EMPAQUES, TUBERIA, BRIDAS y CODOS.
- Presenta coincidencias exactas y parciales ordenadas por score.
- Muestra cantidad disponible, llave canonica y warnings de ambas partes.
- No descuenta ni reserva inventario.

## Uso

1. Ejecutar la aplicacion.
2. Cargar el archivo de inventario.
3. Cargar el archivo de requerimientos.
4. Alternar entre ambos archivos con el selector de la vista previa.
5. Seleccionar columnas relevantes de ambos archivos.
6. Seleccionar opcionalmente una descripcion de partida como respaldo.
7. Pulsar `Segmentar y buscar inventario`.
8. Revisar `Cruce de inventario`, `Segmentacion de requerimientos` y
   `Segmentacion de inventario` en el selector de vistas.
9. Usar `Busqueda rapida` para consultar materiales sin ejecutar el cruce.
10. Activar opcionalmente `Configuracion > Modo oscuro`.

Limpiar la vista previa solo vacia la tabla visible; no elimina los archivos ni
los mapeos ya cargados. Cambiar un archivo o mapeo invalida el cruce anterior.

## Roadmap inmediato

- Validar llaves canonicas contra inventario real.
- Ampliar diccionarios de materiales y aliases.
- Agregar exportacion de resultados y resumen por UDC.
- Incorporar valvulas y su predictor en una segunda fase.
