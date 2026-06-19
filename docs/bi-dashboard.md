# BI dashboard para Hermes

## Objetivo

Despues de cargar inventario, cargar requerimientos y ejecutar el cruce, Hermes debe mostrar un resumen visual claro del resultado sin obligar al usuario a leer primero toda la tabla.

El dashboard no busca reemplazar el reporte final ni Power BI. Su funcion es responder rapido:

- cuanto se pudo cubrir
- cuanto falta
- que familias concentran el problema
- que partidas requieren revision
- que inventario fue utilizado

## Datos base

La fuente del dashboard es `ReconciliationReport`, generado por `ReconciliationService.reconcile`.

Tablas usadas:

- `matches`: resultado principal del cruce por requerimiento
- `inventory`: inventario segmentado con cantidades iniciales, asignadas y restantes
- `requirements`: requerimientos segmentados
- `user_report`: reporte final exportable para el usuario

## Indicadores incluidos

`build_reconciliation_dashboard_summary` genera:

- cobertura total
- total requerido
- total asignado
- total faltante
- numero de requerimientos cubiertos
- numero de requerimientos con revision requerida
- distribucion por estado
- resumen por familia
- partidas criticas
- uso de inventario

## Archivos nuevos

- `src/hermes/services/bi_summary.py`
  - concentra la logica de agregacion
  - no depende de PySide6
  - se puede probar con pandas y pytest

- `src/hermes/ui/reconciliation_dashboard.py`
  - widget visual de PySide6
  - contiene tarjetas, barra de cobertura, distribucion por estado y tablas resumidas
  - recibe directamente un `ReconciliationReport`

- `tests/test_bi_summary.py`
  - valida totales, cobertura, distribucion y agrupacion por familia

## Punto de integracion sugerido

En `src/hermes/ui/main_window.py`:

1. Importar el widget:

```python
from hermes.ui.reconciliation_dashboard import ReconciliationDashboard
```

2. Crear una llave de vista:

```python
BI_DASHBOARD = "result:bi_dashboard"
```

3. Instanciar el dashboard en `_build_ui`, junto al area de resultados:

```python
self.reconciliation_dashboard = ReconciliationDashboard(self)
```

4. Despues de ejecutar el cruce en `run_reconciliation`, alimentar el dashboard:

```python
self.reconciliation_dashboard.set_report(report)
```

5. Agregar la opcion al combo de vistas en `_add_result_views`:

```python
("Resumen BI", self.BI_DASHBOARD),
```

6. En `_show_result`, cuando la llave sea `BI_DASHBOARD`, mostrar el dashboard en lugar de la tabla.

## Nota tecnica

La rama actual deja separada la logica de BI y el widget visual. El siguiente paso debe ser ajustar `main_window.py` para alternar entre `QTableView` y `ReconciliationDashboard` dentro del panel de resultados.
