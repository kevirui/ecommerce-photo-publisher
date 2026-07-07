# Backend - Ecommerce Photo Publisher API

API REST construida con **FastAPI** para la recepción, procesamiento automático y publicación de imágenes de productos de e-commerce.

## Funciones Principales

1. **Recepción de Fotos**: Endpoint `/api/v1/photos/upload` que recibe una imagen y metadatos asociados (código de artículo, índice de imagen, opacidad de marca de agua, e indicación de si lleva sello).
2. **Validación en Base de Datos**: Consulta a un servidor **Microsoft SQL Server** para asegurar que el código del artículo sea válido antes de continuar.
3. **Procesamiento de Imagen**:
   - Eliminación del fondo utilizando la librería `rembg` (basada en IA/U-2-Net).
   - Recorte, reajuste y conversión del formato con `Pillow`.
   - Adición opcional de marcas de agua personalizadas y sellos de marca con opacidad regulable.
4. **Respaldo Local**: Guarda una copia local de la imagen procesada en el directorio `/Respaldo_Imagenes/` organizada bajo la nomenclatura `{código_articulo}.jpg` o `{código_articulo}_{índice}.jpg`.
5. **Subida por FTP**: Sube automáticamente la imagen procesada al servidor FTP donde se almacena el catálogo de e-commerce.

---

## Requisitos de Instalación

1. **Python 3.10+**: Asegúrate de tener instalado Python en tu sistema.
2. **Controlador de Base de Datos**: Si usas Windows, asegúrate de tener instalado el driver *ODBC Driver for SQL Server*.

### Instalación de dependencias

Recomendamos crear un entorno virtual:

```bash
# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual (Windows)
.venv\Scripts\activate

# Activar entorno virtual (Linux/macOS)
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

---

## Configuración

El backend obtiene las credenciales de conexión de la base de datos SQL Server y del servidor FTP leyendo el archivo `config.ini` de la carpeta vecina `appdesktop/config.ini`. Si el archivo no existe, utiliza los valores por defecto del código para entornos de desarrollo.

Estructura requerida en `appdesktop/config.ini`:

```ini
[SQL]
server = tu_servidor
database = tu_basededatos
username = tu_usuario
password = tu_password

[FTP]
host = ftp.tudominio.com
username = tu_ftp_user
password = tu_ftp_pass
remote_path = /public_html/imagenes
```

---

## Ejecución del Servidor

Para levantar la API localmente en modo desarrollo:

```bash
uvicorn main:app --reload --port 8000
```

Una vez ejecutándose, puedes visitar la documentación interactiva en:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Redoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
