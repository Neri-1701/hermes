# Hermes 0.4.0

Hermes es una aplicacion para segmentar y conciliar materiales entre
requerimientos de ingenieria e inventario disponible. La version 0.4.0 integra
el parser tecnico trazable con busqueda y asignacion de existencias.

## Alcance actual

La aplicacion conserva las funciones de carga y configuracion del Sprint 1:

- Carga de archivo de inventario en formato `.xlsx`.
- Carga de archivo de requerimientos en formato `.xlsx`.
- Seleccion dinamica de columnas relevantes con sugerencia automatica.
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
- Resolucion de cedula/schedule a espesor de pared canonico con tabla
  operativa versionada.
- Llaves canonicas comparables por familia.
- `confidence_score`, warnings y evidencia con posiciones en el texto original.
- Uso de `Data_DescripcionPartida` solo como respaldo de
  `Data_DescripcionMaterial`.
- Cruce tecnico entre requerimientos e inventario por atributos de familia.
- Descuento secuencial de existencias para evitar asignaciones duplicadas.
- Coincidencias parciales visibles para revision, sin descuento automatico.
- Vistas de cruce, segmentacion de requerimientos y segmentacion de inventario.
- Reporte final para usuario basado en el archivo de requerimientos original,
  con columnas de codigos, descripciones y cantidades asignadas.

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
3. `ColumnMappingPreferences` sugiere mapeos por palabras clave y recuerda la
   ultima seleccion valida del usuario en `~/.hermes/column_mappings.json`.
4. `DataFrameTableModel` limita la cantidad de filas mostradas sin modificar
   el dataframe completo.
5. `SetupValidator` comprueba que ambos archivos y todos los mapeos requeridos
   esten disponibles antes del siguiente procesamiento.
6. `MaterialParser` normaliza, localiza la familia, ejecuta un solo extractor,
   resuelve cedula/schedule a espesor de pared, genera la llave canonica y
   valida la confianza del resultado.
7. `ReconciliationService` segmenta ambos origenes, busca compatibilidad
   tecnica y asigna solamente coincidencias exactas.
8. La interfaz presenta el cruce, el reporte final y los saldos resultantes en
   la misma tabla.

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

- Inventario requiere descripcion, codigo y cantidad disponible.
- Requerimientos requiere solo descripcion solicitada y cantidad requerida.
- Las demas columnas del archivo de requerimientos se conservan como
  informacion del reporte final, sin pedir mapeos adicionales.
- Para tuberia, bridas WN y codos BW, la cedula se conserva como evidencia,
  pero la comparacion tecnica usa `espesor_pared_in`.
- Si una descripcion trae cedula sin espesor, Hermes infiere el espesor con
  `src/hermes/resources/pipe_wall_thickness_reference.csv`.
- Si trae cedula y espesor explicito, Hermes valida ambos con tolerancia de
  `0.005 in`; un conflicto genera `schedule_thickness_conflict` y evita
  asignacion automatica.
- No se asume `STD = 40` ni `XS = 80` globalmente: siempre se resuelve por
  diametro nominal + token de cedula/schedule.
- Las coincidencias exactas descuentan inventario en orden de requerimiento.
- Un requerimiento puede cubrirse con varios renglones de inventario.
- El saldo disponible se conserva por codigo y fila de origen.
- Las coincidencias parciales se muestran como `REVISION_REQUERIDA`, pero no
  reservan ni descuentan existencias.
- Los conflictos de cedula/espesor, dimensiones ambiguas y materiales no
  segmentados nunca se asignan automaticamente.

La tabla de espesor incluida es una referencia operativa para Hermes alineada
con comportamiento publico de B36.10M/B36.19M. No sustituye las normas ASME
oficiales ni una validacion de ingenieria para uso contractual.

## Reportes

Desde la interfaz, `Exportar reporte` genera un Excel practico para el usuario
final. La hoja `Requerimientos` conserva las columnas originales del archivo de
requerimientos y agrega:

- `estado_asignacion`
- `codigo(s) asignado(s)`
- `descripcion(es) asignada(s)`
- `cantidad(es) asignada(s)`
- `cantidad_total_asignada`
- `cantidad_faltante`

El reporte tecnico con hojas de cruce, segmentacion de requerimientos y
segmentacion de inventario queda como script de desarrollo:

```bash
.venv/bin/python scripts/export_reconciliation_debug_report.py \
  inventario.xlsx requerimientos.xlsx \
  --output debug_reconciliacion_hermes.xlsx \
  --inventory-description description \
  --inventory-code code \
  --inventory-quantity available \
  --requirements-description description \
  --requirements-quantity required
```

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
5. Revisar o corregir las columnas sugeridas automaticamente.
6. Pulsar `Segmentar`.
7. Revisar `Reporte final`, `Cruce de inventario`,
   `Segmentacion de requerimientos` y `Segmentacion de inventario` en el
   selector de vistas.
8. Usar `Exportar reporte` para generar el Excel final de requerimientos.
9. Usar `Busqueda rapida` para consultar materiales sin ejecutar el cruce.
10. Activar opcionalmente `Configuracion > Modo oscuro`.

Limpiar la vista previa solo vacia la tabla visible; no elimina los archivos ni
los mapeos ya cargados. Cambiar un archivo o mapeo invalida el cruce anterior.

## Roadmap inmediato

- Validar llaves canonicas contra inventario real.
- Ampliar diccionarios de materiales y aliases.
- Agregar exportacion de resultados y resumen por UDC.
- Incorporar valvulas y su predictor en una segunda fase.
