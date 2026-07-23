"""
Pestaña de Auditoría de Artículos e Imágenes.

Permite auditar la consistencia entre SQL Server y el servidor FTP,
detectando discrepancias de publicación, imágenes faltantes y archivos huérfanos.
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QTextEdit,
    QFileDialog,
    QGroupBox,
    QMessageBox,
    QMenu,
)

from services.audit_service import AuditService
from services.sql_service import SqlService
from services.ftp_service import FtpService
from workers.audit_worker import AuditWorker
from ui.styles import (
    COLOR_SUCCESS,
    COLOR_SUCCESS_BG,
    COLOR_ERROR,
    COLOR_ERROR_BG,
    COLOR_WARNING,
    COLOR_WARNING_BG,
    COLOR_BG_SECONDARY,
    COLOR_BG_TERTIARY,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_ACCENT,
    COLOR_BORDER,
)

logger = logging.getLogger(__name__)


class AuditTab(QWidget):
    """
    Widget de pestaña para la auditoría de consistencia de datos y archivos.
    """

    def __init__(
        self,
        sql_service: Optional[SqlService],
        ftp_service: Optional[FtpService],
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        Inicializa la pestaña de auditoría.
        """
        super().__init__(parent)
        self._sql_service = sql_service
        self._ftp_service = ftp_service
        self._audit_service = AuditService(sql_service, ftp_service) if sql_service and ftp_service else AuditService(None, None)

        # Datos de la sesión
        self._all_audit_items: List[Dict[str, Any]] = []
        self._filtered_audit_items: List[Dict[str, Any]] = []

        # Worker
        self._worker: Optional[AuditWorker] = None

        # Filtro rápido actual
        self._current_filter = "Todos"

        self._setup_ui()

    def update_connections(self, sql_service: SqlService, ftp_service: FtpService) -> None:
        """Actualiza las conexiones activas en el servicio."""
        self._sql_service = sql_service
        self._ftp_service = ftp_service
        self._audit_service._sql_service = sql_service
        self._audit_service._ftp_service = ftp_service
        self._log("Conexiones SQL y FTP actualizadas en módulo de auditoría.")

    def _setup_ui(self) -> None:
        """Construye y organiza los elementos visuales de la pestaña."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(16, 12, 16, 12)

        # ----------------- PANEL SUPERIOR (Botones de acción) -----------------
        group_actions = QGroupBox("Panel de Control de Auditoría")
        layout_actions = QHBoxLayout(group_actions)
        layout_actions.setSpacing(12)

        self._btn_audit_sql = QPushButton("Auditar Solo BD (SQL)")
        self._btn_audit_sql.setToolTip("Analizar artículos en SQL Server sin verificar archivos en FTP.")
        self._btn_audit_sql.clicked.connect(lambda: self._start_audit("sql"))
        layout_actions.addWidget(self._btn_audit_sql)

        self._btn_audit_all = QPushButton("Auditar BD + FTP")
        self._btn_audit_all.setProperty("primary", True)
        self._btn_audit_all.setToolTip("Analizar artículos en SQL Server y verificar la existencia de sus imágenes en FTP.")
        self._btn_audit_all.clicked.connect(lambda: self._start_audit("all"))
        layout_actions.addWidget(self._btn_audit_all)

        layout_actions.addSpacing(20)

        self._btn_export = QPushButton("Exportar Resultado")
        self._btn_export.setToolTip("Exportar listado actual a Auditoria.xlsx.")
        self._btn_export.clicked.connect(self._on_export_excel)
        layout_actions.addWidget(self._btn_export)

        self._btn_cancel = QPushButton("Cancelar")
        self._btn_cancel.setProperty("danger", True)
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.clicked.connect(self._on_cancel)
        layout_actions.addWidget(self._btn_cancel)

        layout_actions.addStretch()
        main_layout.addWidget(group_actions)

        # ----------------- PANEL DE BUSCADOR Y FILTROS RÁPIDOS -----------------
        layout_filters = QHBoxLayout()
        layout_filters.setSpacing(10)

        layout_filters.addWidget(QLabel("Buscar:"))
        self._txt_search = QLineEdit()
        self._txt_search.setPlaceholderText("Buscar por código o descripción...")
        self._txt_search.textChanged.connect(self._on_search_changed)
        layout_filters.addWidget(self._txt_search, 1)

        layout_filters.addWidget(QLabel("Filtro:"))
        self._btn_filter_dropdown = QPushButton("Todos ▼")
        self._btn_filter_dropdown.setFixedWidth(160)

        self._menu_filters = QMenu(self)
        filter_options = [
            "Todos",
            "Correctos",
            "Pendientes",
            "Sin Imagen Principal",
            "Imagen FTP Faltante",
            "Advertencias",
        ]
        for opt in filter_options:
            action = self._menu_filters.addAction(opt)
            action.triggered.connect(lambda checked, o=opt: self._on_filter_selected(o))
        self._btn_filter_dropdown.setMenu(self._menu_filters)
        layout_filters.addWidget(self._btn_filter_dropdown)

        main_layout.addLayout(layout_filters)

        # ----------------- TABLA DE RESULTADOS -----------------
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "Código",
            "Descripción",
            "Publicado",
            "Estado",
            "Observaciones",
        ])
        self._table.setAlternatingRowColors(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        main_layout.addWidget(self._table, 3)

        # ----------------- PANEL DE RESUMEN Y ESTADÍSTICAS -----------------
        self._group_summary = QGroupBox("Resumen y Estadísticas")
        grid_summary = QGridLayout(self._group_summary)
        grid_summary.setSpacing(10)

        self._lbl_total = QLabel("Total artículos: 0")
        self._lbl_correctos = QLabel("Correctos: 0")
        self._lbl_pendientes = QLabel("Pendientes: 0")
        self._lbl_errores = QLabel("Errores: 0")
        self._lbl_advertencias = QLabel("Advertencias: 0")

        grid_summary.addWidget(self._lbl_total, 0, 0)
        grid_summary.addWidget(self._lbl_correctos, 0, 1)
        grid_summary.addWidget(self._lbl_pendientes, 0, 2)
        grid_summary.addWidget(self._lbl_errores, 0, 3)
        grid_summary.addWidget(self._lbl_advertencias, 0, 4)

        main_layout.addWidget(self._group_summary)

        # ----------------- BARRA DE PROGRESO -----------------
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        main_layout.addWidget(self._progress_bar)

        # ----------------- PANEL DE LOGS -----------------
        self.lbl_log = QLabel("Registro de Operaciones (Logs)")
        self.lbl_log.hide()
        self._txt_log = QTextEdit()
        self._txt_log.hide()
        self._txt_log.setReadOnly(True)
        self._txt_log.setPlaceholderText("Las operaciones de auditoría aparecerán aquí...")
        self._txt_log.setMaximumHeight(120)
        main_layout.addWidget(self.lbl_log)
        main_layout.addWidget(self._txt_log)

    # ================================================================
    # Eventos de UI e Interacción
    # ================================================================

    def _log(self, message: str) -> None:
        """Registra un mensaje con marca de tiempo en la consola local."""
        logger.info(message)
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._txt_log.append(f"[{timestamp}] {message}")

    def _on_search_changed(self) -> None:
        """Filtra en tiempo real de forma asincrónica."""
        self._apply_filters()

    def _on_filter_selected(self, filter_name: str) -> None:
        """Aplica el filtro seleccionado desde el menú contextual."""
        self._current_filter = filter_name
        self._btn_filter_dropdown.setText(f"{filter_name} ▼")
        self._log(f"Filtro aplicado: {filter_name}")
        self._apply_filters()

    def _on_cancel(self) -> None:
        """Detiene el hilo de auditoría."""
        if self._worker:
            self._btn_cancel.setEnabled(False)
            self._worker.cancel()

    def _start_audit(self, mode: str) -> None:
        """Inicia el proceso de auditoría en segundo plano."""
        # Validar conexión de base de datos para análisis SQL / ALL
        if mode in ("sql", "all") and (not self._sql_service or not self._sql_service.is_connected):
            QMessageBox.warning(self, "Sin Conexión SQL", "Se requiere conexión activa a SQL Server para este análisis. Conéctese en la pestaña principal.")
            return

    def _start_audit(self, mode: str) -> None:
        """Inicia el proceso de auditoría en segundo plano."""
        # Validar conexión de base de datos para análisis SQL / ALL
        if mode in ("sql", "all") and (not self._sql_service or not self._sql_service.is_connected):
            QMessageBox.warning(self, "Sin Conexión SQL", "Se requiere conexión activa a SQL Server para este análisis. Conéctese en la pestaña principal.")
            return

        # Validar conexión de FTP para análisis BD + FTP
        if mode == "all" and (not self._ftp_service or not self._ftp_service.is_connected):
            QMessageBox.warning(self, "Sin Conexión FTP", "Se requiere conexión activa al servidor FTP para este análisis. Conéctese en la pestaña principal.")
            return

        self._all_audit_items.clear()
        self._table.setRowCount(0)
        self._update_summary_ui({"total": 0, "correctos": 0, "pendientes": 0, "errores": 0, "advertencias": 0})

        self._btn_audit_sql.setEnabled(False)
        self._btn_audit_all.setEnabled(False)
        self._btn_export.setEnabled(False)
        self._btn_cancel.setEnabled(True)

        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

        # Iniciar worker
        self._worker = AuditWorker(self._audit_service, mode, self)
        self._worker.log_message.connect(self._log)
        self._worker.progress_updated.connect(self._on_worker_progress)
        self._worker.finished_audit.connect(self._on_worker_finished)
        self._worker.error_occurred.connect(self._on_worker_error)
        self._worker.cancelled.connect(self._on_worker_cancelled)

        self._worker.start()

    def _on_worker_progress(self, actual: int, total: int) -> None:
        """Actualiza la barra de progreso."""
        if total > 0:
            pct = int((actual / total) * 100)
            self._progress_bar.setValue(pct)
            self._progress_bar.setFormat(f"Auditando: {actual}/{total} ({pct}%)")

    def _on_worker_finished(self, results: list, stats: dict) -> None:
        """Llamado cuando finaliza la auditoría."""
        self._all_audit_items = results
        self._update_summary_ui(stats)
        self._apply_filters()
        self._cleanup_worker()

    def _on_worker_error(self, error_msg: str) -> None:
        """Llamado cuando el worker encuentra un error fatal."""
        QMessageBox.critical(self, "Error de Auditoría", f"Ocurrió un error al ejecutar la auditoría:\n\n{error_msg}")
        self._cleanup_worker()

    def _on_worker_cancelled(self) -> None:
        """Llamado al cancelarse el worker."""
        self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        """Restaura los botones e inactiva el worker."""
        self._btn_audit_sql.setEnabled(True)
        self._btn_audit_all.setEnabled(True)
        self._btn_export.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self._progress_bar.setVisible(False)
        
        if self._worker:
            self._worker.quit()
            self._worker.wait()
            self._worker = None

    def _on_export_excel(self) -> None:
        """Exporta los artículos visibles a Auditoria.xlsx."""
        if not self._filtered_audit_items:
            QMessageBox.information(self, "Sin datos", "No hay datos que exportar.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Auditoría",
            str(Path.home() / "Auditoria.xlsx"),
            "Archivos Excel (*.xlsx)",
        )
        if file_path:
            try:
                self._audit_service.export_to_excel(Path(file_path), self._filtered_audit_items, self._current_filter)
                self._log(f"Auditoría exportada a: {Path(file_path).name}")
                QMessageBox.information(self, "Exportación exitosa", "La auditoría fue guardada correctamente.")
            except Exception as e:
                self._log(f"Error exportando auditoría: {e}")
                QMessageBox.critical(self, "Error al exportar", f"No se pudo guardar la auditoría:\n{e}")

    # ================================================================
    # Filtrado y llenado de tabla
    # ================================================================

    def _apply_filters(self) -> None:
        """Filtra y actualiza la tabla de resultados."""
        search_text = self._txt_search.text().strip().upper()
        filtered: List[Dict[str, Any]] = []

        for item in self._all_audit_items:
            state = item.get("estado", "")
            code = item.get("codigo", "").upper()
            desc = item.get("descripcion", "").upper()

            # 1. Validar filtro rápido
            if self._current_filter == "Correctos" and state != "CORRECTO":
                continue
            elif self._current_filter == "Pendientes" and state != "PENDIENTE":
                continue
            elif self._current_filter == "Sin Imagen Principal" and item.get("imagen_principal", "") != "":
                continue
            elif self._current_filter == "Imagen FTP Faltante" and not (state == "ERROR" and item.get("existe_ftp") == "No"):
                continue
            elif self._current_filter == "Advertencias" and state != "ADVERTENCIA":
                continue

            # 2. Validar buscador
            if search_text and (search_text not in code and search_text not in desc):
                continue

            filtered.append(item)

        self._filtered_audit_items = filtered
        self._populate_table()

    def _populate_table(self) -> None:
        """Llena la tabla QTableWidget."""
        self._table.setRowCount(0)
        self._table.setRowCount(len(self._filtered_audit_items))

        status_colors = {
            "CORRECTO": (QColor(COLOR_SUCCESS), QColor(COLOR_SUCCESS_BG)),
            "ERROR": (QColor(COLOR_ERROR), QColor(COLOR_ERROR_BG)),
            "ADVERTENCIA": (QColor(COLOR_WARNING), QColor(COLOR_WARNING_BG)),
            "PENDIENTE": (QColor(COLOR_TEXT_MUTED), QColor(COLOR_BG_SECONDARY)),
        }

        for row_idx, item in enumerate(self._filtered_audit_items):
            state = item.get("estado", "PENDIENTE")
            txt_color, bg_color = status_colors.get(state, (QColor(COLOR_TEXT_PRIMARY), QColor(COLOR_BG_SECONDARY)))

            # Items
            item_code = QTableWidgetItem(item.get("codigo", ""))
            item_desc = QTableWidgetItem(item.get("descripcion", ""))
            item_pub = QTableWidgetItem("Sí" if item.get("publicado") == "S" else "No" if item.get("publicado") == "N" else "")
            item_state = QTableWidgetItem(state)
            item_obs = QTableWidgetItem(item.get("observaciones", ""))

            # Alineaciones
            item_pub.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_state.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Estilo
            font_bold = QFont("Segoe UI", 9, QFont.Weight.Bold)
            item_state.setFont(font_bold)

            row_items = [item_code, item_desc, item_pub, item_state, item_obs]
            for col_idx, it in enumerate(row_items):
                it.setForeground(txt_color)
                it.setBackground(bg_color)
                self._table.setItem(row_idx, col_idx, it)

    def _update_summary_ui(self, stats: Dict[str, Any]) -> None:
        """Actualiza los contadores de la sección de estadísticas."""
        self._lbl_total.setText(f"Total artículos: {stats.get('total', 0)}")
        
        correctos = stats.get("correctos", 0)
        self._lbl_correctos.setText(f"Correctos: {correctos}")
        self._lbl_correctos.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;" if correctos else "")

        pendientes = stats.get("pendientes", 0)
        self._lbl_pendientes.setText(f"Pendientes: {pendientes}")
        self._lbl_pendientes.setStyleSheet(f"color: {COLOR_TEXT_MUTED};" if pendientes else "")

        errores = stats.get("errores", 0)
        self._lbl_errores.setText(f"Errores: {errores}")
        self._lbl_errores.setStyleSheet(f"color: {COLOR_ERROR}; font-weight: bold;" if errores else "")

        advertencias = stats.get("advertencias", 0)
        self._lbl_advertencias.setText(f"Advertencias: {advertencias}")
        self._lbl_advertencias.setStyleSheet(f"color: {COLOR_WARNING}; font-weight: bold;" if advertencias else "")
