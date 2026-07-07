"""
Ventana principal de la aplicación Publicador Ecommerce.

Contiene la interfaz completa: selectores de carpeta/Excel, indicadores
de conexión, tabla de artículos, barra de progreso, botones de acción,
controles de simulación/lotes/conflictos FTP, y panel de log en tiempo real.

La GUI no contiene lógica de negocio — todo se delega a los servicios.
"""

from __future__ import annotations

import configparser
import logging
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.article import Article, ArticleStatus, FtpConflictPolicy
from services.sql_service import SqlService, SqlConnectionError
from services.ftp_service import FtpService, FtpConnectionError
from services.ecommerce_repository import EcommerceRepository
from services.image_service import ImageService, ImageServiceError
from services.excel_service import ExcelService
from services.publish_service import PublishService
from services.report_service import ReportService
from ui.progress_dialog import ProgressWidget
from ui.settings_dialog import SettingsDialog
from ui.sync_tab import SyncTab
from ui.audit_tab import AuditTab
from ui.photo_editor_tab import PhotoEditorTab
from ui.photo_processor_tab import PhotoProcessorTab
from ui.styles import (
    COLOR_SUCCESS,
    COLOR_ERROR,
    COLOR_WARNING,
    COLOR_ACCENT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_BG_SECONDARY,
    COLOR_SIMULATION_BORDER,
    INDICATOR_CONNECTED,
    INDICATOR_DISCONNECTED,
    SIMULATION_FRAME_STYLE,
    get_status_color,
    get_status_bg_color,
)
from workers.publish_worker import PublishWorker

logger = logging.getLogger(__name__)

# Columnas de la tabla
TABLE_COLUMNS = [
    "Código",
    "Imagen Principal",
    "Cant. Imágenes",
    "Estado",
    "Fecha",
    "Error",
]

# Opciones de lote
BATCH_OPTIONS = [
    ("Todos", 0),
    ("100", 100),
    ("250", 250),
    ("500", 500),
    ("1000", 1000),
]


class MainWindow(QMainWindow):
    """
    Ventana principal de la aplicación Publicador Ecommerce.

    Organiza la interfaz en secciones verticales: selectores de entrada,
    indicadores de estado, controles de publicación, tabla de artículos,
    barra de progreso, botones de acción, y panel de log.

    No contiene lógica de negocio directa — todo se delega a servicios
    y al worker de publicación.
    """

    def __init__(
        self,
        config_path: Path,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Inicializa la ventana principal.

        Args:
            config_path: Ruta al archivo config.ini.
            parent: Widget padre.
        """
        super().__init__(parent)
        self._config_path = config_path
        self._config = configparser.ConfigParser(interpolation=None)

        # Servicios (se inicializan al conectar)
        self._sql_service: Optional[SqlService] = None
        self._ftp_service: Optional[FtpService] = None
        self._ecommerce_repo: Optional[EcommerceRepository] = None
        self._publish_service: Optional[PublishService] = None
        self._image_service: Optional[ImageService] = None
        self._excel_service: Optional[ExcelService] = None
        self._report_service = ReportService()

        # Worker
        self._worker: Optional[PublishWorker] = None

        # Datos
        self._articles: list[Article] = []

        # Construir UI
        self._setup_ui()
        self._load_config()
        self._update_button_states()

    # ================================================================
    # Construcción de la interfaz
    # ================================================================

    def _setup_ui(self) -> None:
        """Construye toda la interfaz de la ventana principal con pestañas."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(16, 12, 16, 12)

        # Título
        main_layout.addWidget(self._create_header())

        # Crear TabWidget
        self._tab_widget = QTabWidget()

        # --- TAB 1: Publicador (Layout original) ---
        tab_publish = QWidget()
        publish_layout = QVBoxLayout(tab_publish)
        publish_layout.setSpacing(10)
        publish_layout.setContentsMargins(0, 8, 0, 0)

        # Selectores de entrada
        publish_layout.addWidget(self._create_input_section())

        # Indicadores de estado + controles
        publish_layout.addWidget(self._create_status_and_controls())

        # Splitter: tabla + log
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Tabla
        self._table = self._create_table()
        splitter.addWidget(self._table)

        # Panel de log
        log_container = self._create_log_panel()
        splitter.addWidget(log_container)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        publish_layout.addWidget(splitter, 1)

        # Progreso
        self._progress_widget = ProgressWidget()
        publish_layout.addWidget(self._progress_widget)

        # Botones de acción
        publish_layout.addWidget(self._create_action_buttons())

        self._tab_widget.addTab(tab_publish, "Publicador")

        # --- TAB 2: Sincronización ---
        self._sync_tab = SyncTab(self._sql_service, config_path=self._config_path, parent=self)
        self._tab_widget.addTab(self._sync_tab, "Sincronización")

        # --- TAB 3: Auditoría ---
        self._audit_tab = AuditTab(self._sql_service, self._ftp_service, parent=self)
        self._tab_widget.addTab(self._audit_tab, "Auditoría")

        # --- TAB 4: Editor de Fotos ---
        self._photo_editor_tab = PhotoEditorTab()
        self._tab_widget.addTab(self._photo_editor_tab, "📸 Editor de Fotos")

        # --- TAB 5: Procesador IA ---
        self._photo_processor_tab = PhotoProcessorTab()
        self._tab_widget.addTab(self._photo_processor_tab, "🤖 Procesador IA")

        main_layout.addWidget(self._tab_widget, 1)

    def _create_header(self) -> QWidget:
        """Crea el encabezado con el título de la aplicación."""
        header = QLabel("Publicador Ecommerce")
        header.setProperty("heading", True)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return header

    def _create_input_section(self) -> QWidget:
        """Crea la sección de selección de carpeta e archivo Excel."""
        group = QGroupBox("Entrada de datos")
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # Carpeta de imágenes
        img_row = QHBoxLayout()
        img_row.addWidget(QLabel("Carpeta de imágenes:"))
        self._txt_image_folder = QLineEdit()
        self._txt_image_folder.setPlaceholderText(
            "Seleccione la carpeta con las imágenes de artículos..."
        )
        self._txt_image_folder.setReadOnly(True)
        img_row.addWidget(self._txt_image_folder, 1)
        self._btn_browse_folder = QPushButton("Examinar")
        self._btn_browse_folder.clicked.connect(self._on_browse_folder)
        img_row.addWidget(self._btn_browse_folder)
        layout.addLayout(img_row)

        # Archivo Excel
        excel_row = QHBoxLayout()
        excel_row.addWidget(QLabel("Archivo Excel (opcional):"))
        self._txt_excel_file = QLineEdit()
        self._txt_excel_file.setPlaceholderText(
            "Seleccione un archivo Excel con datos de artículos..."
        )
        self._txt_excel_file.setReadOnly(True)
        excel_row.addWidget(self._txt_excel_file, 1)
        self._btn_browse_excel = QPushButton("Examinar")
        self._btn_browse_excel.clicked.connect(self._on_browse_excel)
        excel_row.addWidget(self._btn_browse_excel)
        layout.addLayout(excel_row)

        group.setLayout(layout)
        return group

    def _create_status_and_controls(self) -> QWidget:
        """Crea la sección de indicadores de estado y controles de publicación."""
        group = QGroupBox("Estado y opciones de publicación")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Fila 1: Indicadores de conexión
        conn_row = QHBoxLayout()

        conn_row.addWidget(QLabel("Servidor SQL:"))
        self._lbl_sql_status = QLabel("● Desconectado")
        self._lbl_sql_status.setStyleSheet(INDICATOR_DISCONNECTED)
        conn_row.addWidget(self._lbl_sql_status)

        conn_row.addSpacing(30)

        conn_row.addWidget(QLabel("Servidor FTP:"))
        self._lbl_ftp_status = QLabel("● Desconectado")
        self._lbl_ftp_status.setStyleSheet(INDICATOR_DISCONNECTED)
        conn_row.addWidget(self._lbl_ftp_status)

        conn_row.addStretch()
        layout.addLayout(conn_row)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Fila 2: Simulación + Lote + Conflicto FTP
        controls_row = QHBoxLayout()

        # Checkbox simulación
        self._chk_simulation = QCheckBox("Modo Simulación")
        self._chk_simulation.setToolTip(
            "En modo simulación: no sube FTP, no ejecuta SQL.\n"
            "Solo valida artículos, imágenes y conexiones."
        )
        self._chk_simulation.setStyleSheet(
            f"QCheckBox {{ font-weight: bold; color: {COLOR_SIMULATION_BORDER}; }}"
        )
        controls_row.addWidget(self._chk_simulation)

        controls_row.addSpacing(20)

        # Combo de lote
        controls_row.addWidget(QLabel("Lote:"))
        self._cmb_batch = QComboBox()
        for label, _ in BATCH_OPTIONS:
            self._cmb_batch.addItem(label)
        self._cmb_batch.setCurrentIndex(0)
        self._cmb_batch.setToolTip("Cantidad de artículos a publicar por lote")
        self._cmb_batch.setFixedWidth(100)
        controls_row.addWidget(self._cmb_batch)

        controls_row.addSpacing(20)

        # Radio buttons conflicto FTP
        controls_row.addWidget(QLabel("Conflicto FTP:"))
        self._radio_overwrite = QRadioButton("Sobrescribir")
        self._radio_skip = QRadioButton("Omitir")
        self._radio_ask = QRadioButton("Preguntar")
        self._radio_overwrite.setChecked(True)

        self._ftp_conflict_group = QButtonGroup(self)
        self._ftp_conflict_group.addButton(self._radio_overwrite, 0)
        self._ftp_conflict_group.addButton(self._radio_skip, 1)
        self._ftp_conflict_group.addButton(self._radio_ask, 2)

        controls_row.addWidget(self._radio_overwrite)
        controls_row.addWidget(self._radio_skip)
        controls_row.addWidget(self._radio_ask)

        controls_row.addStretch()
        layout.addLayout(controls_row)

        group.setLayout(layout)
        return group

    def _create_table(self) -> QTableWidget:
        """Crea la tabla de artículos."""
        table = QTableWidget()
        table.setColumnCount(len(TABLE_COLUMNS))
        table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)

        # Ajustar anchos de columna
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        return table

    def _create_log_panel(self) -> QWidget:
        """Crea el panel de log en tiempo real."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel("Log en tiempo real")
        lbl.setProperty("subheading", True)
        layout.addWidget(lbl)

        self._txt_log = QTextEdit()
        self._txt_log.setReadOnly(True)
        self._txt_log.setPlaceholderText("Los mensajes de publicación aparecerán aquí...")
        layout.addWidget(self._txt_log)

        return container

    def _create_action_buttons(self) -> QWidget:
        """Crea la barra de botones de acción."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        self._btn_connect = QPushButton("🔌  Conectar")
        self._btn_connect.setProperty("primary", True)
        self._btn_connect.setToolTip("Conectar a SQL Server y FTP")
        self._btn_connect.clicked.connect(self._on_connect)
        layout.addWidget(self._btn_connect)

        self._btn_scan = QPushButton("🔍  Escanear")
        self._btn_scan.setToolTip("Escanear carpeta de imágenes")
        self._btn_scan.clicked.connect(self._on_scan)
        layout.addWidget(self._btn_scan)

        self._btn_publish = QPushButton("🚀  Publicar")
        self._btn_publish.setProperty("primary", True)
        self._btn_publish.setToolTip("Iniciar publicación de artículos")
        self._btn_publish.clicked.connect(self._on_publish)
        layout.addWidget(self._btn_publish)

        self._btn_cancel = QPushButton("⛔  Cancelar")
        self._btn_cancel.setProperty("danger", True)
        self._btn_cancel.setToolTip("Cancelar publicación en curso")
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_cancel.setEnabled(False)
        layout.addWidget(self._btn_cancel)

        layout.addStretch()

        self._btn_settings = QPushButton("⚙  Configuración")
        self._btn_settings.setToolTip("Abrir configuración de la aplicación")
        self._btn_settings.clicked.connect(self._on_settings)
        layout.addWidget(self._btn_settings)

        return container

    # ================================================================
    # Carga de configuración
    # ================================================================

    def _load_config(self) -> None:
        """Carga la configuración desde config.ini."""
        try:
            self._config.read(str(self._config_path), encoding="utf-8")

            # Cargar ruta de imágenes en el campo de texto
            image_folder = self._config.get(
                "General", "image_folder", fallback=""
            )
            if image_folder:
                self._txt_image_folder.setText(image_folder)

            logger.debug("Configuración cargada en ventana principal.")

        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")

    def _reload_config(self) -> None:
        """Recarga la configuración desde disco."""
        self._config = configparser.ConfigParser(interpolation=None)
        self._load_config()

    # ================================================================
    # Acciones de la GUI
    # ================================================================

    def _on_browse_folder(self) -> None:
        """Abre diálogo para seleccionar carpeta de imágenes."""
        current = self._txt_image_folder.text().strip()
        folder = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta de imágenes",
            current if current else str(Path.home()),
        )
        if folder:
            self._txt_image_folder.setText(folder)
            self._log(f"Carpeta de imágenes seleccionada: {folder}")

    def _on_browse_excel(self) -> None:
        """Abre diálogo para seleccionar archivo Excel."""
        current_dir = self._txt_image_folder.text().strip() or str(Path.home())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo Excel",
            current_dir,
            "Archivos Excel (*.xlsx *.xls)",
        )
        if file_path:
            self._txt_excel_file.setText(file_path)
            self._log(f"Archivo Excel seleccionado: {file_path}")

    def _on_connect(self) -> None:
        """Establece conexiones con SQL Server y FTP."""
        self._reload_config()
        self._log("Iniciando conexiones...")

        # --- Conectar SQL ---
        try:
            self._sql_service = SqlService(
                server=self._config.get("SQL", "server", fallback=""),
                database=self._config.get("SQL", "database", fallback=""),
                username=self._config.get("SQL", "username", fallback=""),
                password=self._config.get("SQL", "password", fallback=""),
            )
            self._sql_service.connect()
            self._lbl_sql_status.setText("● Conectado")
            self._lbl_sql_status.setStyleSheet(INDICATOR_CONNECTED)
            self._log("✓ Conexión SQL Server establecida.")

            # Crear repositorio
            self._ecommerce_repo = EcommerceRepository(self._sql_service)

            # Actualizar SqlService en la pestaña de sincronización
            if hasattr(self, "_sync_tab") and self._sync_tab:
                self._sync_tab.update_sql_service(self._sql_service)

        except SqlConnectionError as e:
            self._lbl_sql_status.setText("● Error")
            self._lbl_sql_status.setStyleSheet(INDICATOR_DISCONNECTED)
            self._log(f"✗ Error SQL: {e}")
            QMessageBox.warning(
                self, "Error SQL", f"No se pudo conectar a SQL Server:\n\n{e}"
            )

        # --- Conectar FTP ---
        try:
            self._ftp_service = FtpService(
                host=self._config.get("FTP", "host", fallback=""),
                port=self._config.getint("FTP", "port", fallback=21),
                username=self._config.get("FTP", "username", fallback=""),
                password=self._config.get("FTP", "password", fallback=""),
                remote_path=self._config.get("FTP", "remote_path", fallback="/"),
                timeout=self._config.getint("General", "timeout", fallback=30),
                max_retries=self._config.getint("General", "max_retries", fallback=3),
            )
            self._ftp_service.connect()
            self._lbl_ftp_status.setText("● Conectado")
            self._lbl_ftp_status.setStyleSheet(INDICATOR_CONNECTED)
            self._log("✓ Conexión FTP establecida.")

        except FtpConnectionError as e:
            self._lbl_ftp_status.setText("● Error")
            self._lbl_ftp_status.setStyleSheet(INDICATOR_DISCONNECTED)
            self._log(f"✗ Error FTP: {e}")
            QMessageBox.warning(
                self, "Error FTP", f"No se pudo conectar al FTP:\n\n{e}"
            )

        # Crear PublishService si ambos están conectados
        if self._ecommerce_repo and self._ftp_service:
            self._publish_service = PublishService(
                self._ecommerce_repo, self._ftp_service
            )

        # Actualizar conexiones en la pestaña de auditoría
        if hasattr(self, "_audit_tab") and self._audit_tab:
            self._audit_tab.update_connections(self._sql_service, self._ftp_service)

        self._update_button_states()

    def _on_scan(self) -> None:
        """Escanea la carpeta de imágenes y carga la tabla."""
        folder_path = self._txt_image_folder.text().strip()

        if not folder_path:
            QMessageBox.warning(
                self,
                "Carpeta no seleccionada",
                "Seleccione una carpeta de imágenes antes de escanear.",
            )
            return

        folder = Path(folder_path)
        if not folder.exists():
            QMessageBox.warning(
                self,
                "Carpeta no encontrada",
                f"La carpeta no existe:\n{folder_path}",
            )
            return

        try:
            self._log(f"Escaneando carpeta: {folder_path}")

            # Crear servicio de imágenes
            self._image_service = ImageService(folder)

            # Convertir PNG si está configurado
            convert_png = self._config.getboolean(
                "General", "convert_png", fallback=True
            )
            if convert_png:
                converted = self._image_service.convert_all_png()
                if converted:
                    self._log(f"Convertidas {len(converted)} imágenes PNG a JPG.")

            # Detectar duplicados
            duplicates = self._image_service.detect_duplicates()
            if duplicates:
                self._log(
                    f"⚠ Imágenes duplicadas detectadas: {', '.join(duplicates)}"
                )

            # Escanear artículos
            self._articles = self._image_service.scan_articles()

            # Cargar Excel si está seleccionado
            excel_path_str = self._txt_excel_file.text().strip()
            if excel_path_str:
                excel_path = Path(excel_path_str)
                self._excel_service = ExcelService(excel_path)
                if self._excel_service.load():
                    self._excel_service.merge_with_scanned(self._articles)
                    self._log(
                        f"Excel cargado: {self._excel_service.article_count} artículos."
                    )
                else:
                    self._log("⚠ No se pudo cargar el archivo Excel.")

            # Actualizar tabla
            self._populate_table()

            self._log(
                f"✓ Escaneo completado: {len(self._articles)} artículos, "
                f"{sum(a.image_count for a in self._articles)} imágenes totales."
            )

        except ImageServiceError as e:
            self._log(f"✗ Error al escanear: {e}")
            QMessageBox.critical(self, "Error de escaneo", str(e))

        self._update_button_states()

    def _on_publish(self) -> None:
        """Inicia la publicación de artículos."""
        if not self._articles:
            QMessageBox.warning(
                self,
                "Sin artículos",
                "No hay artículos para publicar.\nEscanee una carpeta primero.",
            )
            return

        if not self._publish_service:
            QMessageBox.warning(
                self,
                "Sin conexión",
                "Debe conectarse a SQL Server y FTP antes de publicar.",
            )
            return

        # Verificar conexiones
        sql_ok = self._sql_service and self._sql_service.is_connected
        ftp_ok = self._ftp_service and self._ftp_service.is_connected

        if not sql_ok or not ftp_ok:
            missing = []
            if not sql_ok:
                missing.append("SQL Server")
            if not ftp_ok:
                missing.append("FTP")
            QMessageBox.warning(
                self,
                "Conexión perdida",
                f"Se perdió la conexión a: {', '.join(missing)}.\n"
                "Reconecte antes de publicar.",
            )
            return

        # Modo simulación
        is_simulation = self._chk_simulation.isChecked()
        mode_str = "SIMULACIÓN" if is_simulation else "PUBLICACIÓN REAL"

        # Obtener batch size
        batch_idx = self._cmb_batch.currentIndex()
        _, batch_size = BATCH_OPTIONS[batch_idx]
        batch_str = f" (lote: {batch_size})" if batch_size > 0 else ""

        # Confirmación
        article_count = min(
            len(self._articles),
            batch_size if batch_size > 0 else len(self._articles),
        )
        reply = QMessageBox.question(
            self,
            f"Confirmar {mode_str}",
            f"Se procesarán {article_count} artículos en modo {mode_str}{batch_str}.\n\n"
            f"¿Desea continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Obtener política de conflicto FTP
        conflict_policy = self._get_ftp_conflict_policy()

        # Resetear artículos
        for article in self._articles:
            article.reset()
        self._populate_table()

        # Configurar progreso
        self._progress_widget.set_total(article_count)

        # Crear y lanzar worker
        self._worker = PublishWorker(
            articles=self._articles,
            publish_service=self._publish_service,
            simulation=is_simulation,
            ftp_conflict_policy=conflict_policy,
            batch_size=batch_size,
        )

        # Conectar señales
        self._worker.article_started.connect(self._on_article_started)
        self._worker.article_completed.connect(self._on_article_completed)
        self._worker.article_error.connect(self._on_article_error)
        self._worker.progress_updated.connect(self._on_progress_updated)
        self._worker.log_message.connect(self._on_log_message)
        self._worker.all_completed.connect(self._on_all_completed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.ftp_conflict_found.connect(self._on_ftp_conflict)

        # Actualizar botones
        self._set_publishing_state(True)

        # Iniciar
        self._log(f"═══ Iniciando {mode_str}{batch_str} ═══")
        self._worker.start()

    def _on_cancel(self) -> None:
        """Cancela la publicación en curso."""
        if self._worker and self._worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Cancelar publicación",
                "¿Está seguro de que desea cancelar la publicación?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._worker.request_cancel()
                self._log("⚠ Cancelación solicitada... esperando finalización.")

    def _on_settings(self) -> None:
        """Abre el diálogo de configuración."""
        dialog = SettingsDialog(self._config_path, self)
        if dialog.exec():
            self._reload_config()
            # Actualizar campo de imagen si cambió
            img_folder = self._config.get("General", "image_folder", fallback="")
            if img_folder:
                self._txt_image_folder.setText(img_folder)
            self._log("Configuración actualizada.")

    # ================================================================
    # Slots de señales del Worker
    # ================================================================

    def _on_article_started(self, code: str) -> None:
        """Slot: artículo iniciado."""
        self._update_table_row_status(code, ArticleStatus.IN_PROGRESS)
        self._progress_widget.update_progress(
            self._get_article_index(code) + 1, code
        )

    def _on_article_completed(self, code: str, success: bool) -> None:
        """Slot: artículo completado."""
        if success:
            self._update_table_row_status(code, ArticleStatus.SUCCESS)
            self._progress_widget.increment_success()
        else:
            self._update_table_row_status(code, ArticleStatus.ERROR)
            self._progress_widget.increment_error()

    def _on_article_error(self, code: str, error_message: str) -> None:
        """Slot: error en artículo."""
        self._update_table_row_error(code, error_message)

    def _on_progress_updated(self, current: int, total: int) -> None:
        """Slot: progreso actualizado."""
        self._progress_widget.update_progress(current)

    def _on_log_message(self, message: str) -> None:
        """Slot: mensaje de log desde el worker."""
        self._txt_log.append(message)
        # Auto-scroll al final
        scrollbar = self._txt_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_all_completed(self, successful: int, failed: int) -> None:
        """Slot: publicación finalizada."""
        self._set_publishing_state(False)
        self._progress_widget.set_completed(successful, failed)
        self._populate_table()  # Refrescar toda la tabla

        # Generar reporte
        try:
            report_path = self._report_service.generate_report(self._articles)
            self._log(f"📊 Reporte generado: {report_path}")
        except Exception as e:
            self._log(f"⚠ Error al generar reporte: {e}")

        # Mensaje final
        total = successful + failed
        mode = "simulación" if self._chk_simulation.isChecked() else "publicación"
        QMessageBox.information(
            self,
            f"Resultado de {mode}",
            f"Procesados: {total} artículos\n"
            f"Exitosos: {successful}\n"
            f"Fallidos: {failed}",
        )

    def _on_cancelled(self) -> None:
        """Slot: publicación cancelada."""
        self._set_publishing_state(False)
        self._progress_widget.set_cancelled()
        self._populate_table()

        # Generar reporte parcial
        try:
            report_path = self._report_service.generate_report(self._articles)
            self._log(f"📊 Reporte parcial generado: {report_path}")
        except Exception as e:
            self._log(f"⚠ Error al generar reporte: {e}")

    def _on_ftp_conflict(self, code: str, remote_name: str) -> None:
        """Slot: conflicto FTP detectado, mostrar diálogo al usuario."""
        reply = QMessageBox.question(
            self,
            "Imagen ya existe en FTP",
            f"La imagen '{remote_name}' del artículo '{code}' "
            f"ya existe en el servidor FTP.\n\n"
            f"¿Desea sobrescribirla?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        overwrite = reply == QMessageBox.StandardButton.Yes
        if self._worker:
            self._worker.resolve_conflict(overwrite)

    # ================================================================
    # Gestión de la tabla
    # ================================================================

    def _populate_table(self) -> None:
        """Llena la tabla con los artículos actuales."""
        self._table.setRowCount(0)
        self._table.setRowCount(len(self._articles))

        for row, article in enumerate(self._articles):
            # Código
            self._table.setItem(row, 0, QTableWidgetItem(article.code))

            # Imagen principal
            self._table.setItem(
                row, 1, QTableWidgetItem(article.main_image_name)
            )

            # Cantidad de imágenes
            qty_item = QTableWidgetItem(str(article.image_count))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, qty_item)

            # Estado
            status_item = QTableWidgetItem(str(article.status))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, status_item)

            # Fecha
            time_str = ""
            if article.start_time:
                time_str = article.start_time.strftime("%H:%M:%S")
            self._table.setItem(row, 4, QTableWidgetItem(time_str))

            # Error
            self._table.setItem(
                row, 5, QTableWidgetItem(article.error_message)
            )

            # Colorear fila según estado
            self._color_table_row(row, article.status)

    def _update_table_row_status(self, code: str, status: ArticleStatus) -> None:
        """Actualiza el estado de un artículo en la tabla."""
        row = self._find_table_row(code)
        if row < 0:
            return

        article = self._articles[row]
        status_item = QTableWidgetItem(str(article.status))
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 3, status_item)

        # Fecha
        if article.start_time:
            self._table.setItem(
                row, 4,
                QTableWidgetItem(article.start_time.strftime("%H:%M:%S")),
            )

        self._color_table_row(row, article.status)

    def _update_table_row_error(self, code: str, error_message: str) -> None:
        """Actualiza el mensaje de error de un artículo en la tabla."""
        row = self._find_table_row(code)
        if row < 0:
            return
        self._table.setItem(row, 5, QTableWidgetItem(error_message))

    def _color_table_row(self, row: int, status: ArticleStatus) -> None:
        """
        Colorea una fila de la tabla según el estado del artículo.

        Verde: Correcto / Rojo: Error / Amarillo: Pendiente/En proceso.
        """
        status_str = str(status)
        fg_color = QColor(get_status_color(status_str))
        bg_color = QColor(get_status_bg_color(status_str))

        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            if item:
                item.setForeground(fg_color)
                item.setBackground(bg_color)

    def _find_table_row(self, code: str) -> int:
        """Busca la fila de un artículo por código."""
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.text() == code:
                return row
        return -1

    def _get_article_index(self, code: str) -> int:
        """Obtiene el índice de un artículo en la lista."""
        for i, article in enumerate(self._articles):
            if article.code == code:
                return i
        return 0

    # ================================================================
    # Estado de la GUI
    # ================================================================

    def _set_publishing_state(self, publishing: bool) -> None:
        """
        Configura la GUI según si se está publicando o no.

        Args:
            publishing: True si hay publicación en curso.
        """
        self._btn_connect.setEnabled(not publishing)
        self._btn_scan.setEnabled(not publishing)
        self._btn_publish.setEnabled(not publishing)
        self._btn_cancel.setEnabled(publishing)
        self._btn_settings.setEnabled(not publishing)
        self._btn_browse_folder.setEnabled(not publishing)
        self._btn_browse_excel.setEnabled(not publishing)
        self._chk_simulation.setEnabled(not publishing)
        self._cmb_batch.setEnabled(not publishing)
        self._radio_overwrite.setEnabled(not publishing)
        self._radio_skip.setEnabled(not publishing)
        self._radio_ask.setEnabled(not publishing)

    def _update_button_states(self) -> None:
        """Actualiza habilitación de botones según estado actual."""
        has_articles = len(self._articles) > 0
        has_services = self._publish_service is not None
        is_publishing = self._worker is not None and self._worker.isRunning()

        self._btn_scan.setEnabled(not is_publishing)
        self._btn_publish.setEnabled(
            has_articles and has_services and not is_publishing
        )
        self._btn_cancel.setEnabled(is_publishing)

    def _get_ftp_conflict_policy(self) -> FtpConflictPolicy:
        """Obtiene la política de conflicto FTP seleccionada."""
        checked_id = self._ftp_conflict_group.checkedId()
        policies = {
            0: FtpConflictPolicy.OVERWRITE,
            1: FtpConflictPolicy.SKIP,
            2: FtpConflictPolicy.ASK,
        }
        return policies.get(checked_id, FtpConflictPolicy.OVERWRITE)

    # ================================================================
    # Log
    # ================================================================

    def _log(self, message: str) -> None:
        """
        Agrega un mensaje al panel de log con timestamp.

        Args:
            message: Mensaje a mostrar.
        """
        timestamp = time.strftime("%H:%M:%S")
        self._txt_log.append(f"{timestamp} — {message}")
        # Auto-scroll
        scrollbar = self._txt_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ================================================================
    # Cleanup
    # ================================================================

    def closeEvent(self, event) -> None:
        """Limpia recursos al cerrar la ventana."""
        # Cancelar worker si está corriendo
        if self._worker and self._worker.isRunning():
            self._worker.request_cancel()
            self._worker.wait(5000)

        # Desconectar servicios
        if self._sql_service:
            try:
                self._sql_service.disconnect()
            except Exception:
                pass

        if self._ftp_service:
            try:
                self._ftp_service.disconnect()
            except Exception:
                pass

        logger.info("Ventana principal cerrada.")
        event.accept()
