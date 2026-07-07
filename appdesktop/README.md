# App Desktop - Publicador Ecommerce Client

Cliente de escritorio desarrollado con **PyQt6** para la administración, monitoreo y publicación directa de imágenes para el catálogo de e-commerce.

## Funciones Principales

- **Panel de Control Visual**: Interfaz gráfica amigable construida con PyQt6 para la administración del flujo de subidas de imágenes.
- **Procesamiento Integrado**: Capacidad de procesar y preparar las imágenes localmente si es necesario antes de cargarlas.
- **Monitoreo de Logs**: Muestra y registra en archivos de rotación (`logs/app.log`) el historial de conexiones, respuestas del servidor, errores e información de carga.
- **Multihilo (Multithreading)**: Procesa las solicitudes en hilos de trabajo independientes para evitar bloquear la interfaz de usuario durante la comunicación con la base de datos o el servidor FTP.

---

## Requisitos de Instalación

1. **Python 3.10+**: Asegúrate de tener Python instalado y configurado en el PATH del sistema.
2. **Controlador de Base de Datos SQL Server**:
   - En Windows: Requiere la instalación del driver oficial de Microsoft ODBC para SQL Server.

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

## Configuración (`config.ini`)

Esta aplicación requiere un archivo `config.ini` en la raíz del directorio `/appdesktop`. 

1. Copia el archivo de ejemplo:
   ```bash
   cp config.ini.example config.ini
   ```
   *(O haz una copia de `config.ini.example` y cámbiale el nombre a `config.ini` desde el explorador de archivos).*
   
2. Edita `config.ini` e introduce tus datos de conexión correspondientes para el servidor SQL, servidor FTP y rutas locales.

> **IMPORTANTE**: Nunca compartas ni subas tu archivo `config.ini` a GitHub o repositorios públicos ya que contiene contraseñas en texto plano. Este archivo ya se encuentra excluido en el `.gitignore`.

---

## Ejecución de la Aplicación

Para lanzar la interfaz de usuario:

```bash
python main.py
```
