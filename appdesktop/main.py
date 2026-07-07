"""
Publicador Ecommerce — Punto de entrada de la aplicación.

Configura el sistema de logging, lee la configuración inicial,
crea la aplicación PyQt6 y lanza la ventana principal.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.styles import APP_STYLESHEET


# ============================================================
# Constantes de la aplicación
# ============================================================

APP_NAME = "Publicador Ecommerce"
APP_VERSION = "1.0.0"
LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "app.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)-20s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """
    Configura el sistema de logging de la aplicación.

    Crea el directorio de logs si no existe, configura un RotatingFileHandler
    para guardar logs en logs/app.log y un StreamHandler para la consola.
    Registra errores, SQL, FTP, tiempos, artículos, reintentos y excepciones.
    """
    # Crear directorio de logs si no existe
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Limpiar handlers previos (evita duplicación en recargas)
    root_logger.handlers.clear()

    # Formatter común
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Handler de archivo con rotación
    file_handler = RotatingFileHandler(
        filename=str(LOG_FILE),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Handler de consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Mensaje de inicio
    root_logger.info("=" * 60)
    root_logger.info(f"{APP_NAME} v{APP_VERSION} — Inicio de sesión")
    root_logger.info("=" * 60)


def main() -> None:
    """
    Función principal de la aplicación.

    1. Configura el logging.
    2. Crea la QApplication con la hoja de estilos global.
    3. Instancia y muestra la ventana principal.
    4. Ejecuta el loop de eventos.
    """
    # Configurar logging
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Crear la aplicación Qt
        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)

        # Aplicar hoja de estilos global
        app.setStyleSheet(APP_STYLESHEET)

        # Establecer fuente por defecto
        font = QFont("Segoe UI", 10)
        app.setFont(font)

        # Habilitar High DPI
        app.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        # Ruta al archivo de configuración
        config_path = Path(__file__).parent / "config.ini"

        # Crear y mostrar la ventana principal
        window = MainWindow(config_path=config_path)
        window.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        window.resize(1100, 800)
        window.show()

        logger.info("Ventana principal creada exitosamente.")

        # Ejecutar el loop de eventos
        exit_code = app.exec()
        logger.info(f"Aplicación finalizada con código: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        logger.critical(f"Error fatal al iniciar la aplicación: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
