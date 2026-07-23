"""
Diálogo de configuración de la aplicación.

Permite editar los parámetros de SQL Server, FTP y configuración
general desde una interfaz con pestañas. Lee y escribe el archivo
config.ini con configparser. Incluye botones de prueba de conexión.
"""

from __future__ import annotations

import configparser
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.sql_service import SqlService, SqlConnectionError
from services.ftp_service import FtpService, FtpConnectionError

logger = logging.getLogger(__name__)


class _ConnectionTester(QThread):
    """Hilo auxiliar para probar conexiones sin bloquear la GUI."""

    result = pyqtSignal(bool, str)

    def __init__(
        self,
        service_type: str,
        params: dict,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service_type = service_type
        self._params = params

    def run(self) -> None:
        """Ejecuta la prueba de conexión."""
        try:
            if self._service_type == "sql":
                service = SqlService(
                    server=self._params["server"],
                    database=self._params["database"],
                    username=self._params["username"],
                    password=self._params["password"],
                )
                service.connect()
                ok = service.test_connection()
                service.disconnect()
                if ok:
                    self.result.emit(True, "Conexión SQL exitosa.")
                else:
                    self.result.emit(False, "Test de conexión SQL falló.")

            elif self._service_type == "ftp":
                service = FtpService(
                    host=self._params["host"],
                    port=self._params["port"],
                    username=self._params["username"],
                    password=self._params["password"],
                    remote_path=self._params["remote_path"],
                    timeout=self._params.get("timeout", 30),
                )
                service.connect()
                ok = service.test_connection()
                service.disconnect()
                if ok:
                    self.result.emit(True, "Conexión FTP exitosa.")
                else:
                    self.result.emit(False, "Test de conexión FTP falló.")

        except (SqlConnectionError, FtpConnectionError) as e:
            self.result.emit(False, str(e))
        except Exception as e:
            self.result.emit(False, f"Error inesperado: {e}")


class SettingsDialog(QDialog):
    """
    Diálogo modal para editar la configuración de la aplicación.

    Organizado en pestañas:
    - SQL Server: servidor, base de datos, usuario, contraseña.
    - FTP: host, puerto, usuario, contraseña, ruta remota.

    Lee y escribe el archivo config.ini con configparser.

    Attributes:
        config_path: Ruta al archivo config.ini.
    """

    def __init__(
        self,
        config_path: Path,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Inicializa el diálogo de configuración.

        Args:
            config_path: Ruta al archivo config.ini.
            parent: Widget padre.
        """
        super().__init__(parent)
        self._config_path = config_path
        self._config = configparser.ConfigParser(interpolation=None)
        self._tester: Optional[_ConnectionTester] = None

        self.setWindowTitle("Configuración")
        self.setMinimumWidth(520)
        self.setMinimumHeight(480)

        self._setup_ui()
        self._load_config()

    # ================================================================
    # Construcción de la interfaz
    # ================================================================

    def _setup_ui(self) -> None:
        """Construye la interfaz del diálogo con pestañas."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Pestaña SQL
        self._tabs.addTab(self._create_sql_tab(), "SQL Server")

        # Pestaña FTP
        self._tabs.addTab(self._create_ftp_tab(), "FTP")

        # Botones de acción
        button_box = QDialogButtonBox()
        self._btn_save = button_box.addButton(
            "Guardar", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._btn_save.setProperty("primary", True)
        self._btn_cancel = button_box.addButton(
            "Cancelar", QDialogButtonBox.ButtonRole.RejectRole
        )
        button_box.accepted.connect(self._save_and_close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_sql_tab(self) -> QWidget:
        """Crea la pestaña de configuración SQL Server."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Grupo de campos
        group = QGroupBox("Conexión SQL Server")
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._sql_server = QLineEdit()
        self._sql_server.setPlaceholderText("servidor\\instancia o IP")
        form.addRow("Servidor:", self._sql_server)

        self._sql_database = QLineEdit()
        self._sql_database.setPlaceholderText("Nombre de la base de datos")
        form.addRow("Base de datos:", self._sql_database)

        self._sql_username = QLineEdit()
        self._sql_username.setPlaceholderText("Usuario SQL Server")
        form.addRow("Usuario:", self._sql_username)

        self._sql_password = QLineEdit()
        self._sql_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._sql_password.setPlaceholderText("Contraseña")
        form.addRow("Contraseña:", self._sql_password)

        group.setLayout(form)
        layout.addWidget(group)

        # Botón de prueba
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._btn_test_sql = QPushButton("Probar conexión SQL")
        self._btn_test_sql.clicked.connect(self._test_sql_connection)
        btn_layout.addWidget(self._btn_test_sql)
        layout.addLayout(btn_layout)

        # Label de resultado
        self._sql_test_result = QLabel()
        self._sql_test_result.setWordWrap(True)
        layout.addWidget(self._sql_test_result)

        layout.addStretch()
        return tab

    def _create_ftp_tab(self) -> QWidget:
        """Crea la pestaña de configuración FTP."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        group = QGroupBox("Conexión FTP")
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._ftp_host = QLineEdit()
        self._ftp_host.setPlaceholderText("ftp.ejemplo.com")
        form.addRow("Host:", self._ftp_host)

        self._ftp_port = QSpinBox()
        self._ftp_port.setRange(1, 65535)
        self._ftp_port.setValue(21)
        form.addRow("Puerto:", self._ftp_port)

        self._ftp_username = QLineEdit()
        self._ftp_username.setPlaceholderText("Usuario FTP")
        form.addRow("Usuario:", self._ftp_username)

        self._ftp_password = QLineEdit()
        self._ftp_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._ftp_password.setPlaceholderText("Contraseña")
        form.addRow("Contraseña:", self._ftp_password)

        self._ftp_remote_path = QLineEdit()
        self._ftp_remote_path.setPlaceholderText("/public_html/img/articulos/")
        form.addRow("Ruta remota:", self._ftp_remote_path)

        group.setLayout(form)
        layout.addWidget(group)

        # Botón de prueba
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._btn_test_ftp = QPushButton("Probar conexión FTP")
        self._btn_test_ftp.clicked.connect(self._test_ftp_connection)
        btn_layout.addWidget(self._btn_test_ftp)
        layout.addLayout(btn_layout)

        # Label de resultado
        self._ftp_test_result = QLabel()
        self._ftp_test_result.setWordWrap(True)
        layout.addWidget(self._ftp_test_result)

        layout.addStretch()
        return tab

        return tab

    # ================================================================
    # Carga y guardado de configuración
    # ================================================================

    def _load_config(self) -> None:
        """Carga los valores del archivo config.ini en los campos."""
        try:
            self._config.read(str(self._config_path), encoding="utf-8")

            # SQL
            self._sql_server.setText(
                self._config.get("SQL", "server", fallback="")
            )
            self._sql_database.setText(
                self._config.get("SQL", "database", fallback="")
            )
            self._sql_username.setText(
                self._config.get("SQL", "username", fallback="")
            )
            self._sql_password.setText(
                self._config.get("SQL", "password", fallback="")
            )

            # FTP
            self._ftp_host.setText(
                self._config.get("FTP", "host", fallback="")
            )
            self._ftp_port.setValue(
                self._config.getint("FTP", "port", fallback=21)
            )
            self._ftp_username.setText(
                self._config.get("FTP", "username", fallback="")
            )
            self._ftp_password.setText(
                self._config.get("FTP", "password", fallback="")
            )
            self._ftp_remote_path.setText(
                self._config.get("FTP", "remote_path", fallback="/")
            )

            logger.debug(f"Configuración cargada desde: {self._config_path}")

        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")

    def _save_config(self) -> bool:
        """
        Guarda los valores de los campos en config.ini.

        Returns:
            True si el guardado fue exitoso.
        """
        try:
            # Asegurar secciones
            for section in ("SQL", "FTP", "General"):
                if not self._config.has_section(section):
                    self._config.add_section(section)

            # SQL
            self._config.set("SQL", "server", self._sql_server.text().strip())
            self._config.set("SQL", "database", self._sql_database.text().strip())
            self._config.set("SQL", "username", self._sql_username.text().strip())
            self._config.set("SQL", "password", self._sql_password.text())

            # FTP
            self._config.set("FTP", "host", self._ftp_host.text().strip())
            self._config.set("FTP", "port", str(self._ftp_port.value()))
            self._config.set("FTP", "username", self._ftp_username.text().strip())
            self._config.set("FTP", "password", self._ftp_password.text())
            self._config.set("FTP", "remote_path", self._ftp_remote_path.text().strip())

            with open(self._config_path, "w", encoding="utf-8") as f:
                self._config.write(f)

            logger.info(f"Configuración guardada en: {self._config_path}")
            return True

        except Exception as e:
            logger.error(f"Error al guardar configuración: {e}")
            return False

    def _save_and_close(self) -> None:
        """Guarda la configuración y cierra el diálogo."""
        if self._save_config():
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Error",
                "No se pudo guardar la configuración.",
            )

    # ================================================================
    # Pruebas de conexión
    # ================================================================

    def _test_sql_connection(self) -> None:
        """Inicia una prueba de conexión SQL en un hilo separado."""
        self._btn_test_sql.setEnabled(False)
        self._sql_test_result.setText("Probando conexión SQL...")
        self._sql_test_result.setStyleSheet("color: #ffa726;")

        params = {
            "server": self._sql_server.text().strip(),
            "database": self._sql_database.text().strip(),
            "username": self._sql_username.text().strip(),
            "password": self._sql_password.text(),
        }

        self._tester = _ConnectionTester("sql", params, self)
        self._tester.result.connect(self._on_sql_test_result)
        self._tester.finished.connect(lambda: self._btn_test_sql.setEnabled(True))
        self._tester.start()

    def _on_sql_test_result(self, success: bool, message: str) -> None:
        """Callback de resultado de prueba SQL."""
        if success:
            self._sql_test_result.setText(f"✓ {message}")
            self._sql_test_result.setStyleSheet("color: #66bb6a;")
        else:
            self._sql_test_result.setText(f"✗ {message}")
            self._sql_test_result.setStyleSheet("color: #ef5350;")

    def _test_ftp_connection(self) -> None:
        """Inicia una prueba de conexión FTP en un hilo separado."""
        self._btn_test_ftp.setEnabled(False)
        self._ftp_test_result.setText("Probando conexión FTP...")
        self._ftp_test_result.setStyleSheet("color: #ffa726;")

        params = {
            "host": self._ftp_host.text().strip(),
            "port": self._ftp_port.value(),
            "username": self._ftp_username.text().strip(),
            "password": self._ftp_password.text(),
            "remote_path": self._ftp_remote_path.text().strip(),
            "timeout": self._config.getint("General", "timeout", fallback=30),
        }

        self._tester = _ConnectionTester("ftp", params, self)
        self._tester.result.connect(self._on_ftp_test_result)
        self._tester.finished.connect(lambda: self._btn_test_ftp.setEnabled(True))
        self._tester.start()

    def _on_ftp_test_result(self, success: bool, message: str) -> None:
        """Callback de resultado de prueba FTP."""
        if success:
            self._ftp_test_result.setText(f"✓ {message}")
            self._ftp_test_result.setStyleSheet("color: #66bb6a;")
        else:
            self._ftp_test_result.setText(f"✗ {message}")
            self._ftp_test_result.setStyleSheet("color: #ef5350;")

    # ================================================================
    # Utilidades
    # ================================================================

    def get_config(self) -> configparser.ConfigParser:
        """
        Retorna una copia del ConfigParser con los valores actuales.

        Returns:
            ConfigParser con la configuración actual.
        """
        self._config.read(str(self._config_path), encoding="utf-8")
        return self._config
