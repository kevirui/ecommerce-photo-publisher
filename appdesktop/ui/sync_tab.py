"""
Pestaña de Sincronización de Artículos.

Implementa la interfaz de usuario completa para comparar artículos entre
SQL Server y un archivo Excel (Modo Excel) o directamente desde la base de datos (Modo SQL).
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QTextEdit,
    QFileDialog,
    QGroupBox,
    QMessageBox,
    QFrame,
    QDialog,
    QFormLayout,
)

from services.sync_service import SyncService
from services.sql_service import SqlService
from workers.sync_worker import SyncWorker
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


class ArticleDetailDialog(QDialog):
    """
    Diálogo para mostrar la información detallada de un artículo al hacer doble click.
    """

    def __init__(self, article_data: Dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Detalle de Artículo — {article_data.get('codigo', '')}")
        self.setMinimumWidth(500)
        self.resize(550, 400)
        self._setup_ui(article_data)

    def _setup_ui(self, data: Dict[str, Any]) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Encabezado
        title = QLabel(f"Artículo: {data.get('codigo', '')}")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLOR_ACCENT};")
        layout.addWidget(title)

        # Formulario de datos
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Campos
        fields = [
            ("Código:", data.get("codigo", "")),
            ("Descripción:", data.get("descripcion", "")),
            ("Estado:", data.get("estado", "")),
            ("Cantidad imágenes:", str(data.get("cant_imagenes", 0))),
            ("WEB_LINK:", data.get("web_link", "")),
            ("WEB_IMAGEN_PROVE:", data.get("imagen_principal", "")),
        ]

        for label_text, value_text in fields:
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY};")
            
            val = QLineEdit(value_text)
            val.setReadOnly(True)
            val.setStyleSheet(f"background-color: {COLOR_BG_TERTIARY}; border: 1px solid {COLOR_BORDER}; color: {COLOR_TEXT_PRIMARY}; padding: 6px;")
            form.addRow(lbl, val)

        layout.addLayout(form)

        # Botón Cerrar
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_close.setFixedWidth(100)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)


class SyncTab(QWidget):
    """
    Widget de pestaña para la Sincronización y comparación de artículos.
    """

    def __init__(self, sql_service: Optional[SqlService], config_path: Path, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._sql_service = sql_service
        self._config_path = config_path
        self._sync_service = SyncService(sql_service) if sql_service else SyncService(None)
        
        # Datos en sesión
        self._all_articles: List[Dict[str, Any]] = []
        self._filtered_articles: List[Dict[str, Any]] = []
        
        # Worker activo
        self._worker: Optional[SyncWorker] = None
        
        # Filtro rápido actual
        self._current_fast_filter = "Todos"

        self._setup_ui()

    def update_sql_service(self, sql_service: SqlService) -> None:
        """Actualiza la instancia de SQL Service para las consultas."""
        self._sql_service = sql_service
        self._sync_service._sql_service = sql_service
        self._log("Conexión SQL Server actualizada en módulo de sincronización.")

    def _setup_ui(self) -> None:
        """Crea y organiza los elementos de la interfaz."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(16, 12, 16, 12)

        # ----------------- PANEL SUPERIOR (Opciones e inputs) -----------------
        top_layout = QHBoxLayout()
        top_layout.setSpacing(16)

        # Grupo 1: Archivo Excel e opciones de comparación
        group_options = QGroupBox("Opciones de Entrada y Comparación")
        grid_options = QGridLayout(group_options)
        grid_options.setSpacing(8)

        # Selector de archivo Excel
        grid_options.addWidget(QLabel("Archivo Excel:"), 0, 0)
        self._txt_excel_file = QLineEdit()
        self._txt_excel_file.setPlaceholderText("Seleccione archivo Excel para comparar...")
        self._txt_excel_file.setReadOnly(True)
        grid_options.addWidget(self._txt_excel_file, 0, 1)

        self._btn_browse = QPushButton("Examinar")
        self._btn_browse.clicked.connect(self._on_browse_excel)
        grid_options.addWidget(self._btn_browse, 0, 2)

        # Checkboxes de comparación
        self._chk_compare_sql = QCheckBox("Comparar contra SQL")
        self._chk_compare_sql.setChecked(True)
        grid_options.addWidget(self._chk_compare_sql, 1, 0, 1, 3)

        self._chk_ignore_inexistent = QCheckBox("Ignorar artículos inexistentes")
        grid_options.addWidget(self._chk_ignore_inexistent, 2, 0, 1, 3)

        self._chk_export_pending = QCheckBox("Exportar pendientes")
        self._chk_export_pending.setToolTip("Genera automáticamente 'Pendientes.xlsx' al finalizar el análisis Excel.")
        grid_options.addWidget(self._chk_export_pending, 3, 0, 1, 3)

        # Checkboxes de visualización
        self._chk_show_published = QCheckBox("Mostrar publicados")
        self._chk_show_published.setChecked(True)
        self._chk_show_published.stateChanged.connect(self._on_visualization_checkbox_changed)
        grid_options.addWidget(self._chk_show_published, 4, 0)

        self._chk_show_pending = QCheckBox("Mostrar pendientes")
        self._chk_show_pending.setChecked(True)
        self._chk_show_pending.stateChanged.connect(self._on_visualization_checkbox_changed)
        grid_options.addWidget(self._chk_show_pending, 4, 1)

        self._chk_show_incomplete = QCheckBox("Mostrar incompletos")
        self._chk_show_incomplete.setChecked(True)
        self._chk_show_incomplete.stateChanged.connect(self._on_visualization_checkbox_changed)
        grid_options.addWidget(self._chk_show_incomplete, 4, 2)

        # Bonus Checkbox
        self._chk_pending_photo = QCheckBox("Obtener únicamente artículos pendientes de fotografiar")
        self._chk_pending_photo.setToolTip("Filtra en BD artículos no publicados, o sin imagen principal.")
        grid_options.addWidget(self._chk_pending_photo, 5, 0, 1, 3)

        top_layout.addWidget(group_options, 3)

        # Grupo 2: Botones de Acción
        group_actions = QGroupBox("Acciones")
        vbox_actions = QVBoxLayout(group_actions)
        vbox_actions.setSpacing(10)
        vbox_actions.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._btn_analyze_excel = QPushButton("Analizar Excel")
        self._btn_analyze_excel.setProperty("primary", True)
        self._btn_analyze_excel.clicked.connect(self._on_analyze_excel)
        vbox_actions.addWidget(self._btn_analyze_excel)

        self._btn_consult_sql = QPushButton("Consultar SQL")
        self._btn_consult_sql.clicked.connect(self._on_consult_sql)
        vbox_actions.addWidget(self._btn_consult_sql)

        self._btn_export_excel = QPushButton("Exportar Excel")
        self._btn_export_excel.clicked.connect(self._on_export_excel)
        vbox_actions.addWidget(self._btn_export_excel)

        self._btn_update = QPushButton("Actualizar")
        self._btn_update.clicked.connect(self._on_update)
        vbox_actions.addWidget(self._btn_update)

        self._btn_cancel = QPushButton("Cancelar")
        self._btn_cancel.setProperty("danger", True)
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.clicked.connect(self._on_cancel)
        vbox_actions.addWidget(self._btn_cancel)

        top_layout.addWidget(group_actions, 1)
        main_layout.addLayout(top_layout)

        # ----------------- PANEL INTERMEDIO (Buscador y Filtros rápidos) -----------------
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        # Buscador en tiempo real
        filter_layout.addWidget(QLabel("Buscar:"))
        self._txt_search = QLineEdit()
        self._txt_search.setPlaceholderText("Buscar por código o descripción...")
        self._txt_search.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self._txt_search, 1)

        # Filtros rápidos
        filter_layout.addWidget(QLabel("Filtro rápido:"))
        self._cmb_fast_filters = QPushButton("Todos ▼")
        self._cmb_fast_filters.setFixedWidth(150)
        
        # Menú contextual de filtros rápidos
        from PyQt6.QtWidgets import QMenu
        self._menu_filters = QMenu(self)
        self._filter_options = [
            "Todos",
            "Publicados",
            "Pendientes",
            "Incompletos",
            "Sin imagen",
            "Sin imágenes adicionales",
            "Con imágenes adicionales"
        ]
        for opt in self._filter_options:
            action = self._menu_filters.addAction(opt)
            action.triggered.connect(lambda checked, o=opt: self._on_fast_filter_selected(o))
        self._cmb_fast_filters.setMenu(self._menu_filters)
        filter_layout.addWidget(self._cmb_fast_filters)

        main_layout.addLayout(filter_layout)

        # ----------------- TABLA DE RESULTADOS -----------------
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Código",
            "Descripción",
            "Publicado",
            "Imagen Principal",
            "Cantidad Imágenes",
            "Estado",
            "Observaciones"
        ])
        self._table.setAlternatingRowColors(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_row_double_clicked)

        # Ajustar anchos
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        main_layout.addWidget(self._table, 3)

        # ----------------- PANEL DE RESUMEN Y ESTADÍSTICAS -----------------
        self._group_summary = QGroupBox("Resumen y Estadísticas")
        grid_summary = QGridLayout(self._group_summary)
        grid_summary.setSpacing(10)

        self._lbl_stat_total = QLabel("Total artículos: 0")
        self._lbl_stat_pub = QLabel("Publicados: 0 (0.0%)")
        self._lbl_stat_pend = QLabel("Pendientes: 0 (0.0%)")
        self._lbl_stat_inc = QLabel("Incompletos: 0")
        self._lbl_stat_inex = QLabel("Inexistentes: 0")

        grid_summary.addWidget(self._lbl_stat_total, 0, 0)
        grid_summary.addWidget(self._lbl_stat_pub, 0, 1)
        grid_summary.addWidget(self._lbl_stat_pend, 0, 2)
        grid_summary.addWidget(self._lbl_stat_inc, 0, 3)
        grid_summary.addWidget(self._lbl_stat_inex, 0, 4)

        main_layout.addWidget(self._group_summary)

        # ----------------- BARRA DE PROGRESO -----------------
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        main_layout.addWidget(self._progress_bar)

        # ----------------- PANEL DE LOG -----------------
        self.lbl_log = QLabel("Registro de Operaciones (Log)")
        self.lbl_log.hide()
        self._txt_log = QTextEdit()
        self._txt_log.hide()
        self._txt_log.setReadOnly(True)
        self._txt_log.setPlaceholderText("Las operaciones y eventos aparecerán aquí...")
        self._txt_log.setMaximumHeight(120)
        main_layout.addWidget(self.lbl_log)
        main_layout.addWidget(self._txt_log)

    # ================================================================
    # Métodos de Interfaz y Lógica
    # ================================================================

    def _log(self, message: str) -> None:
        """Agrega un mensaje con timestamp al log de la pestaña."""
        logger.info(message)
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._txt_log.append(f"[{timestamp}] {message}")

    def _on_browse_excel(self) -> None:
        """Abre diálogo para seleccionar el archivo Excel."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo Excel",
            str(Path.home()),
            "Archivos Excel (*.xlsx *.xls)",
        )
        if file_path:
            self._txt_excel_file.setText(file_path)
            self._log(f"Excel seleccionado: {file_path}")

    def _on_visualization_checkbox_changed(self) -> None:
        """Se activa al cambiar los checkboxes de visualización."""
        self._apply_filters_and_search()

    def _on_fast_filter_selected(self, filter_name: str) -> None:
        """Se activa al seleccionar una opción del filtro rápido."""
        self._current_fast_filter = filter_name
        self._cmb_fast_filters.setText(f"{filter_name} ▼")
        self._log(f"Filtro rápido aplicado: {filter_name}")
        self._apply_filters_and_search()

    def _on_search_changed(self) -> None:
        """Buscador asincrónico por texto."""
        self._apply_filters_and_search()

    def _on_cancel(self) -> None:
        """Detiene la ejecución del worker actual."""
        if self._worker:
            self._btn_cancel.setEnabled(False)
            self._worker.cancel()

    def _on_analyze_excel(self) -> None:
        """Inicia el análisis de Excel."""
        excel_path_str = self._txt_excel_file.text().strip()
        if not excel_path_str:
            QMessageBox.warning(self, "Archivo no seleccionado", "Seleccione un archivo Excel primero.")
            return

        # Limpiar tabla y estados
        self._all_articles.clear()
        self._table.setRowCount(0)
        self._update_stats_ui({"total": 0, "published": 0, "pending": 0, "incomplete": 0, "inexistent": 0, "pct_published": 0, "pct_pending": 0})

        # Configurar worker
        self._start_worker(
            mode="excel",
            excel_path=Path(excel_path_str),
            pending_only=self._chk_pending_photo.isChecked(),
            ignore_inexistent=self._chk_ignore_inexistent.isChecked(),
            auto_export_pending=self._chk_export_pending.isChecked(),
            output_dir=Path(excel_path_str).parent
        )

    def _on_consult_sql(self) -> None:
        """Consulta la base de datos directamente."""
        # Limpiar tabla y estados
        self._all_articles.clear()
        self._table.setRowCount(0)

        # Configurar worker
        self._start_worker(
            mode="sql",
            excel_path=None,
            pending_only=self._chk_pending_photo.isChecked(),
            ignore_inexistent=False,
            auto_export_pending=False,
            output_dir=None
        )

    def _on_update(self) -> None:
        """Vuelve a realizar la última consulta o refresca desde la BD."""
        excel_path_str = self._txt_excel_file.text().strip()
        if excel_path_str:
            self._on_analyze_excel()
        else:
            self._on_consult_sql()

    def _on_export_excel(self) -> None:
        """Exporta el contenido actual visible de la tabla a un archivo Excel."""
        if not self._filtered_articles:
            QMessageBox.information(self, "Sin datos", "No hay datos en la tabla para exportar.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar reporte Excel",
            str(Path.home() / f"Reporte_Sincronizacion_{self._current_fast_filter}.xlsx"),
            "Archivos Excel (*.xlsx)",
        )
        if file_path:
            try:
                self._sync_service.export_to_excel(Path(file_path), self._filtered_articles, self._current_fast_filter)
                self._log(f"Archivo exportado: {Path(file_path).name}")
                QMessageBox.information(self, "Exportación exitosa", "El archivo fue exportado correctamente.")
            except Exception as e:
                self._log(f"Error al exportar a Excel: {e}")
                QMessageBox.critical(self, "Error de exportación", f"No se pudo guardar el archivo:\n{e}")

    def _on_row_double_clicked(self, index) -> None:
        """Abre el diálogo de detalle al hacer doble click en una fila."""
        row_idx = index.row()
        if row_idx < 0 or row_idx >= len(self._filtered_articles):
            return

        article = self._filtered_articles[row_idx]
        code = article.get("codigo", "")

        # Realizar query rápida para obtener WEB_LINK y actualizar WEB_IMAGEN_PROVE
        self._log(f"Obteniendo detalles completos del artículo: {code}...")
        details = self._sync_service.query_detailed_article(code)
        
        # Combinar datos
        detailed_data = dict(article)
        detailed_data.update(details)

        # Mostrar Diálogo modal
        dialog = ArticleDetailDialog(detailed_data, self)
        dialog.exec()

    # ================================================================
    # Control de Worker de Segundo Plano
    # ================================================================

    def _start_worker(
        self,
        mode: str,
        excel_path: Optional[Path],
        pending_only: bool,
        ignore_inexistent: bool,
        auto_export_pending: bool,
        output_dir: Optional[Path]
    ) -> None:
        """Inicializa y arranca el SyncWorker."""
        if not self._sql_service or not self._sql_service.is_connected:
            self._log("✗ Error SQL: No hay conexión activa a SQL Server. Conéctese en la pestaña principal.")
            QMessageBox.warning(self, "Sin conexión SQL", "Debe establecer la conexión a SQL Server en la pestaña principal primero.")
            return

        self._btn_analyze_excel.setEnabled(False)
        self._btn_consult_sql.setEnabled(False)
        self._btn_update.setEnabled(False)
        self._btn_export_excel.setEnabled(False)
        self._btn_cancel.setEnabled(True)

        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

        # Crear y arrancar worker
        self._worker = SyncWorker(
            sync_service=self._sync_service,
            mode=mode,
            excel_path=excel_path,
            pending_only=pending_only,
            ignore_inexistent=ignore_inexistent,
            auto_export_pending=auto_export_pending,
            output_dir=output_dir,
            parent=self
        )

        # Conectar señales
        self._worker.log_message.connect(self._log)
        self._worker.progress_updated.connect(self._on_worker_progress)
        self._worker.article_processed.connect(self._on_worker_article_processed)
        self._worker.finished_sync.connect(self._on_worker_finished)
        self._worker.error_occurred.connect(self._on_worker_error)
        self._worker.cancelled.connect(self._on_worker_cancelled)

        self._worker.start()

    def _on_worker_progress(self, actual: int, total: int) -> None:
        """Actualiza la barra de progreso."""
        if total > 0:
            percentage = int((actual / total) * 100)
            self._progress_bar.setValue(percentage)
            self._progress_bar.setFormat(f"Procesando: {actual}/{total} ({percentage}%)")

    def _on_worker_article_processed(self, article: Dict[str, Any]) -> None:
        """Agrega un artículo procesado a la lista en memoria."""
        self._all_articles.append(article)

    def _on_worker_finished(self, results: list, stats: dict) -> None:
        """Llamado cuando el worker finaliza exitosamente."""
        self._log("Búsqueda y análisis finalizado.")
        self._update_stats_ui(stats)
        self._apply_filters_and_search()
        self._cleanup_worker()

    def _on_worker_error(self, error_msg: str) -> None:
        """Llamado cuando el worker falla."""
        QMessageBox.critical(self, "Error de Sincronización", f"Ocurrió un error durante el proceso:\n\n{error_msg}")
        self._cleanup_worker()

    def _on_worker_cancelled(self) -> None:
        """Llamado al cancelarse el worker."""
        self._log("Proceso cancelado por el usuario.")
        self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        """Restaura los botones y limpia el worker."""
        self._btn_analyze_excel.setEnabled(True)
        self._btn_consult_sql.setEnabled(True)
        self._btn_update.setEnabled(True)
        self._btn_export_excel.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self._progress_bar.setVisible(False)
        
        if self._worker:
            self._worker.quit()
            self._worker.wait()
            self._worker = None

    # ================================================================
    # Filtrado y Visualización en Tabla
    # ================================================================

    def _apply_filters_and_search(self) -> None:
        """Aplica todos los filtros (Checkboxes, Filtro rápido, Buscador) al conjunto de datos."""
        search_text = self._txt_search.text().strip().upper()
        
        # Filtros de visualización por checkboxes
        show_pub = self._chk_show_published.isChecked()
        show_pend = self._chk_show_pending.isChecked()
        show_inc = self._chk_show_incomplete.isChecked()

        filtered: List[Dict[str, Any]] = []

        for art in self._all_articles:
            state = art.get("estado", "")
            
            # 1. Validar Checkboxes de visualización
            if state == "PUBLICADO" and not show_pub:
                continue
            if state == "PENDIENTE" and not show_pend:
                continue
            if state == "INCOMPLETO" and not show_inc:
                continue
            
            # 2. Validar Filtro rápido
            if self._current_fast_filter == "Publicados" and state != "PUBLICADO":
                continue
            elif self._current_fast_filter == "Pendientes" and state != "PENDIENTE":
                continue
            elif self._current_fast_filter == "Incompletos" and state != "INCOMPLETO":
                continue
            elif self._current_fast_filter == "Sin imagen" and art.get("imagen_principal", "") != "":
                continue
            elif self._current_fast_filter == "Sin imágenes adicionales" and art.get("cant_imagenes", 0) > 0:
                continue
            elif self._current_fast_filter == "Con imágenes adicionales" and art.get("cant_imagenes", 0) == 0:
                continue

            # 3. Validar Buscador en tiempo real (Código o Descripción)
            code = art.get("codigo", "").upper()
            desc = art.get("descripcion", "").upper()
            if search_text and (search_text not in code and search_text not in desc):
                continue

            filtered.append(art)

        self._filtered_articles = filtered
        self._populate_table()

    def _populate_table(self) -> None:
        """Llena la tabla QTableWidget con los artículos filtrados."""
        self._table.setRowCount(0)
        self._table.setRowCount(len(self._filtered_articles))

        # Colores para estados
        status_colors = {
            "PUBLICADO": (QColor(COLOR_SUCCESS), QColor(COLOR_SUCCESS_BG)),
            "PENDIENTE": (QColor(COLOR_ERROR), QColor(COLOR_ERROR_BG)),
            "INCOMPLETO": (QColor(COLOR_WARNING), QColor(COLOR_WARNING_BG)),
            "INEXISTENTE": (QColor(COLOR_TEXT_MUTED), QColor(COLOR_BG_SECONDARY)),
        }

        for row_idx, art in enumerate(self._filtered_articles):
            state = art.get("estado", "INEXISTENTE")
            txt_color, bg_color = status_colors.get(state, (QColor(COLOR_TEXT_PRIMARY), QColor(COLOR_BG_SECONDARY)))

            # Items
            item_code = QTableWidgetItem(art.get("codigo", ""))
            item_desc = QTableWidgetItem(art.get("descripcion", ""))
            item_pub = QTableWidgetItem("Sí" if art.get("publicado_db") == "S" else "No")
            item_main_img = QTableWidgetItem(art.get("imagen_principal", ""))
            item_qty_img = QTableWidgetItem(str(art.get("cant_imagenes", 0)))
            item_state = QTableWidgetItem(state)
            item_obs = QTableWidgetItem(art.get("observaciones", ""))

            # Centrar cantidad e publicado
            item_pub.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_qty_img.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_state.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Aplicar colores y fuentes
            row_items = [item_code, item_desc, item_pub, item_main_img, item_qty_img, item_state, item_obs]
            font_state = QFont("Segoe UI", 9, QFont.Weight.Bold)
            item_state.setFont(font_state)

            for item in row_items:
                item.setForeground(txt_color)
                item.setBackground(bg_color)
                self._table.setItem(row_idx, row_items.index(item), item)

    def _update_stats_ui(self, stats: Dict[str, Any]) -> None:
        """Actualiza las etiquetas del panel de resumen."""
        self._lbl_stat_total.setText(f"Total artículos: {stats.get('total', 0)}")
        
        pub_count = stats.get('published', 0)
        pub_pct = stats.get('pct_published', 0.0)
        self._lbl_stat_pub.setText(f"Publicados: {pub_count} ({pub_pct:.1f}%)")
        self._lbl_stat_pub.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")

        pend_count = stats.get('pending', 0)
        pend_pct = stats.get('pct_pending', 0.0)
        self._lbl_stat_pend.setText(f"Pendientes: {pend_count} ({pend_pct:.1f}%)")
        self._lbl_stat_pend.setStyleSheet(f"color: {COLOR_ERROR}; font-weight: bold;")

        self._lbl_stat_inc.setText(f"Incompletos: {stats.get('incomplete', 0)}")
        self._lbl_stat_inc.setStyleSheet(f"color: {COLOR_WARNING}; font-weight: bold;")

        self._lbl_stat_inex.setText(f"Inexistentes: {stats.get('inexistent', 0)}")
        self._lbl_stat_inex.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
