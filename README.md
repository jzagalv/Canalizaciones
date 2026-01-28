# Canalizaciones

Software para diseno y calculo de canalizaciones BT con Canvas (PyQt5).

## Como ejecutar

Desde la carpeta raiz del proyecto (donde esta este README):

```bash
pip install -r requirements.txt
python -m app
# Alternativa:
python -m app.main
```

Nota: no se recomienda usar "Run Python File" sobre archivos internos (por ejemplo `data/app/main.py`).

python -m app
# Alternativa:
python -m app.main
```

Nota: no se recomienda usar "Run Python File" sobre archivos internos (por ejemplo `data/app/main.py`).

2. Revisa la pestaña **Librerías** y asegúrate de tener cargadas:
   - `libs/materiales_bd.lib`
   - `libs/plantillas_bd.lib`
   - `libs/equipment_library.lib`
3. En **Librerías > Administrador de Librerías y Plantillas**, carga/edita `materiales_bd.lib` y define la plantilla base.
   - Define el **tipo de instalación** y aplica la plantilla si corresponde.
4. En la pestaña **Canvas**, usa la **Biblioteca** lateral para arrastrar Equipos/GAP/Cámaras al canvas.
   - Opcional: en el Canvas puedes cargar un plano como fondo (botón **Cargar plano**) para posicionar equipos y canalizaciones sobre la imagen.
5. Conecta nodos con el botón **Conectar tramo**.
6. Selecciona un tramo para editar:
   - Tipo (DUCT/EPC/BPC)
   - Modo (auto/manual)
   - Tamaño (catálogo)
   - Cantidad
7. Recalcula y revisa **Resultados**.

## Selección de cables y ductos desde librería

- En **Circuitos**, la columna **Cable** lista cables desde `materiales_bd.lib`, filtrados por servicio.
- En **Características del tramo**, al elegir **Ducto** selecciona primero la **Norma** y luego el ducto específico.

## Cómo agregar elementos

En **Canvas**, busca el elemento en la **Biblioteca** (panel izquierdo), arrástralo y suéltalo sobre el canvas. No hay botones de inserción manual.

## Gestión de materiales_bd.lib y plantillas

Desde **Librerías > Administrador de Librerías y Plantillas**:
- **materiales_bd.lib**: carga/guarda el archivo y edita ítems por categoría (conductors/ducts/epc/bpc).
- **Plantillas base**: carga/guarda plantillas base y define el tipo de instalación.

### Formato JSON (materiales_bd.lib)

`materiales_bd.lib`:

```json
{
  "schema_version": "1.0",
  "kind": "material_library",
  "meta": {
    "name": "Materiales",
    "created": "YYYY-MM-DD",
    "source": "BD.xlsx"
  },
  "conductors": [],
  "containments": {
    "ducts": [],
    "epc": [],
    "bpc": []
  },
  "rules": {}
}
```

### Formato JSON (plantillas base)

`base_template.json`:

```json
{
  "schema_version": 1,
  "installation_type": "Subestación",
  "defaults": {}
}
```

### Extender tipos de material

Para agregar un nuevo tipo:
1. Agrega la nueva lista dentro de `containments` o como raíz si aplica.
2. Crea su diálogo de edición y columnas en el editor.
3. Actualiza el mapeo de categorías en el editor para mostrar/validar el nuevo tipo.

## Canvas: plano de fondo (para informes)

En la pestaña Canvas:
- **Cargar plano**: carga una imagen (PNG/JPG) como fondo.
- **Ajustar a vista**: encuadra el plano en pantalla.
- **Fondo bloqueado/desbloqueado**: evita mover/seleccionar el fondo accidentalmente.
- **Opacidad**: permite ver mejor los elementos sobre el plano.
- **Exportar PNG / PDF**: exporta la escena para adjuntar directamente en informes.

## Arquitectura UI (Dashboard)

La interfaz principal usa un **Dashboard Shell** con:
- Sidebar (navegación global)
- Header (contexto del proyecto + acciones globales)
- ActionBar (acciones por vista)
- Contenido central (QStackedWidget)
- Inspector derecho (propiedades contextuales)

Componentes clave:
- `ui/shell/dashboard_shell.py`: layout principal (sidebar/header/actionbar/stack/inspector)
- `ui/widgets/sidebar_nav.py`: navegación lateral
- `ui/widgets/header_bar.py`: barra superior
- `ui/widgets/inspector_panel.py`: panel contextual
- `ui/widgets/action_bar.py`: barra de acciones por vista

### Cómo agregar una nueva página
1) Crear el widget de la página (ej. `MyPage(QWidget)`).
2) Agregarlo al stack en `ui/main_window.py`:
   - `self.shell.stack.addWidget(my_page)`
   - `self.shell.sidebar.add_item("my_page", "Mi Página")`
3) En `_on_nav_requested`, mapear la key al índice del stack.

### Estilos (QSS)
Usa propiedades para consistencia:
- `primary="true"`, `secondary="true"`, `danger="true"` en botones.
- `card="true"` en `QFrame` para tarjetas.
- Contenedores principales: `#SidebarNav`, `#HeaderBar`, `#ActionBar`, `#InspectorPanel`.
- Roles equivalentes: `QFrame[role="sidebar"]`, `QFrame[role="header"]`, `QFrame[role="actionbar"]`, `QFrame[role="inspector"]`.
