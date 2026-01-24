# Canalizaciones

Software para diseño y cálculo de canalizaciones BT con Canvas (PyQt5).

## Ejecutar

Desde la carpeta raíz del proyecto (donde está este README):

```bash
pip install -r requirements.txt
python app/main.py
```

## Flujo rápido

1. Abre un proyecto (o usa `example_project.proj.json`)
2. Revisa la pestaña **Librerías** y asegúrate de tener cargadas:
   - `libs/materiales_bd.lib`
   - `libs/plantillas_bd.lib`
   - `libs/equipment_library.lib`
3. En **Herramientas > Librerías y Plantillas**, carga tu librería de materiales y plantilla base.
   - Define el **tipo de instalación** y guarda la plantilla base si corresponde.
4. En la pestaña **Canvas**, usa la **Biblioteca** lateral para arrastrar Equipos/GAP/Cámaras al canvas.
   - Opcional: en el Canvas puedes cargar un plano como fondo (botón **Cargar plano**) para posicionar equipos y canalizaciones sobre la imagen.
5. Conecta nodos con el botón **Conectar tramo**.
6. Selecciona un tramo para editar:
   - Tipo (DUCT/EPC/BPC)
   - Modo (auto/manual)
   - Tamaño (catálogo)
   - Cantidad
7. Recalcula y revisa **Resultados**.

## Cómo agregar elementos

En **Canvas**, busca el elemento en la **Biblioteca** (panel izquierdo), arrástralo y suéltalo sobre el canvas. No hay botones de inserción manual.

## Gestión de librerías y plantillas

Desde **Herramientas > Librerías y Plantillas**:
- **Librerías de materiales**: carga/guarda librerías JSON y edita ítems por categoría.
- **Plantillas**: carga/guarda plantillas base y define el tipo de instalación.

### Formato JSON (librerías de materiales)

`materials_library.json`:

```json
{
  "schema_version": 1,
  "name": "Mi Librería",
  "items": {
    "cables": [],
    "ducts": [],
    "epc": [],
    "bpc": []
  }
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
1. Crea una nueva categoría en `MaterialsLibrary.items`.
2. Agrega columnas y un diálogo de edición dedicado en UI.
3. Actualiza el editor para mostrar/validar el nuevo tipo.

## Canvas: plano de fondo (para informes)

En la pestaña Canvas:
- **Cargar plano**: carga una imagen (PNG/JPG) como fondo.
- **Ajustar a vista**: encuadra el plano en pantalla.
- **Fondo bloqueado/desbloqueado**: evita mover/seleccionar el fondo accidentalmente.
- **Opacidad**: permite ver mejor los elementos sobre el plano.
- **Exportar PNG / PDF**: exporta la escena para adjuntar directamente en informes.
