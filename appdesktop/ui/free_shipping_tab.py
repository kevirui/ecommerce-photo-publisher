import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QMessageBox,
    QCheckBox,
)

from services.sql_service import SqlService
from services.ftp_service import FtpService
from workers.free_shipping_worker import FreeShippingWorker
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
    COLOR_ACCENT,
    COLOR_BORDER,
)

logger = logging.getLogger(__name__)

# Buscar stamp.png en Backend/assets/ relative to ui directory
STAMP_PATH = Path(__file__).parent.parent.parent / "Backend" / "assets" / "stamp.png"


class FreeShippingTab(QWidget):
    """
    Widget de pestaña para seleccionar productos y estamparles el sello de "Envío Gratis".
    """

    def __init__(
        self,
        sql_service: Optional[SqlService],
        ftp_service: Optional[FtpService],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._sql_service = sql_service
        self._ftp_service = ftp_service

        # Datos
        self._all_articles: List[Dict[str, Any]] = []
        self._filtered_articles: List[Dict[str, Any]] = []

        # Worker
        self._worker: Optional[FreeShippingWorker] = None

        self._setup_ui()

    def update_connections(self, sql_service: SqlService, ftp_service: FtpService) -> None:
        """Actualiza las conexiones de servicios desde la ventana principal."""
        self._sql_service = sql_service
        self._ftp_service = ftp_service
        self._log("Conexiones SQL y FTP actualizadas en pestaña de Envío Gratis.")

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(16, 12, 16, 12)

        # ----------------- PANEL SUPERIOR (Botones de acción) -----------------
        group_actions = QGroupBox("Panel de Control - Envío Gratis")
        layout_actions = QHBoxLayout(group_actions)
        layout_actions.setSpacing(12)

        self._btn_load = QPushButton("Cargar Productos")
        self._btn_load.setToolTip("Carga los productos desde la base de datos que tienen imagen principal.")
        self._btn_load.clicked.connect(self._on_load_clicked)
        layout_actions.addWidget(self._btn_load)

        self._btn_apply = QPushButton("Aplicar Envío Gratis")
        self._btn_apply.setProperty("primary", True)
        self._btn_apply.setToolTip("Descarga, estampa el sello de Envío Gratis y sube las imágenes principales de los seleccionados.")
        self._btn_apply.clicked.connect(self._on_apply_clicked)
        self._btn_apply.setEnabled(False)
        layout_actions.addWidget(self._btn_apply)

        self._btn_remove = QPushButton("Quitar Envío Gratis")
        self._btn_remove.setToolTip("Quita el sello de Envío Gratis y restaura la imagen original para los seleccionados.")
        self._btn_remove.clicked.connect(self._on_remove_clicked)
        self._btn_remove.setEnabled(False)
        layout_actions.addWidget(self._btn_remove)

        self._btn_cancel = QPushButton("Cancelar")
        self._btn_cancel.setProperty("danger", True)
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.clicked.connect(self._on_cancel_clicked)
        layout_actions.addWidget(self._btn_cancel)

        layout_actions.addStretch()
        main_layout.addWidget(group_actions)

        # ----------------- FILTROS Y CONTROLES DE TABLA -----------------
        layout_filters = QHBoxLayout()
        layout_filters.setSpacing(10)

        layout_filters.addWidget(QLabel("Buscar:"))
        self._txt_search = QLineEdit()
        self._txt_search.setPlaceholderText("Buscar por código o descripción...")
        self._txt_search.textChanged.connect(self._on_search_changed)
        layout_filters.addWidget(self._txt_search, 1)

        self._chk_select_all = QCheckBox("Seleccionar Todos")
        self._chk_select_all.clicked.connect(self._on_select_all_clicked)
        layout_filters.addWidget(self._chk_select_all)

        main_layout.addLayout(layout_filters)

        # ----------------- TABLA DE PRODUCTOS -----------------
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Seleccionar",
            "Código",
            "Descripción",
            "Imagen Principal",
            "Envío Gratis",
            "Publicado Web",
        ])
        self._table.setAlternatingRowColors(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        # Conectar el cambio de estado de checkbox en la tabla
        self._table.itemChanged.connect(self._on_table_item_changed)

        main_layout.addWidget(self._table, 3)

        # ----------------- PROGRESO -----------------
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setVisible(False)
        main_layout.addWidget(self._progress)

        # ----------------- PANEL DE CONSOLA / LOGS -----------------
        group_log = QGroupBox("Consola de Progreso")
        group_log.hide()
        layout_log = QVBoxLayout(group_log)
        self._txt_log = QTextEdit()
        self._txt_log.setReadOnly(True)
        self._txt_log.setFont(QFont("Consolas", 9))
        self._txt_log.setStyleSheet(
            f"background-color: {COLOR_BG_SECONDARY};"
            f"color: {COLOR_TEXT_PRIMARY};"
            f"border: 1px solid {COLOR_BORDER};"
        )
        layout_log.addWidget(self._txt_log)
        main_layout.addWidget(group_log, 1)

    def _log(self, text: str) -> None:
        """Añade un texto a la consola de logs."""
        logger.info(text)
        self._txt_log.append(text)
        # Auto-scroll
        self._txt_log.moveCursor(self._txt_log.textCursor().MoveOperation.End)

    def _on_load_clicked(self) -> None:
        """Carga los productos con imagen principal desde la base de datos."""
        if not self._sql_service:
            QMessageBox.warning(self, "Error", "No hay conexión activa a la base de datos SQL.")
            return

        self._btn_load.setEnabled(False)
        self._log("Consultando base de datos...")
        self._all_articles.clear()

        query = """
        SELECT A.COD_ARTICULO, A.DESCRIP_ARTI, A.WEB_PUBLI, A.WEB_IMAGEN_PROVE
        FROM ARTICULOS A
        WHERE A.WEB_PUBLI = 'S' AND A.WEB_IMAGEN_PROVE IS NOT NULL AND A.WEB_IMAGEN_PROVE <> ''
        ORDER BY A.COD_ARTICULO
        """

        try:
            results = self._sql_service.execute(query)
            for row in results:
                self._all_articles.append({
                    "codigo": str(row.get("COD_ARTICULO", "")).strip(),
                    "descripcion": str(row.get("DESCRIP_ARTI", "")).strip(),
                    "imagen": str(row.get("WEB_IMAGEN_PROVE", "")).strip(),
                    "publicado": str(row.get("WEB_PUBLI", "")).strip(),
                    "checked": False
                })

            self._log(f"Cargados {len(self._all_articles)} productos con imagen principal.")
            self._on_search_changed()

        except Exception as e:
            self._log(f"✗ Error al consultar base de datos: {e}")
            QMessageBox.critical(self, "Error de base de datos", f"No se pudieron cargar los artículos: {e}")
        finally:
            self._btn_load.setEnabled(True)
            self._update_action_states()

    def _on_search_changed(self) -> None:
        """Filtra la lista de artículos según el término de búsqueda."""
        search_text = self._txt_search.text().strip().lower()

        # Bloquear señales para no disparar _on_table_item_changed al redibujar
        self._table.blockSignals(True)

        if not search_text:
            self._filtered_articles = list(self._all_articles)
        else:
            self._filtered_articles = [
                art for art in self._all_articles
                if search_text in art["codigo"].lower() or search_text in art["descripcion"].lower()
            ]

        self._table.setRowCount(len(self._filtered_articles))

        for row, art in enumerate(self._filtered_articles):
            # Checkbox de selección
            chk_item = QTableWidgetItem()
            chk_item.setCheckState(Qt.CheckState.Checked if art["checked"] else Qt.CheckState.Unchecked)
            # Guardamos el índice original para poder modificar el estado en _all_articles
            chk_item.setData(Qt.ItemDataRole.UserRole, art["codigo"])
            self._table.setItem(row, 0, chk_item)

            # Código
            code_item = QTableWidgetItem(art["codigo"])
            self._table.setItem(row, 1, code_item)

            # Descripción
            desc_item = QTableWidgetItem(art["descripcion"])
            self._table.setItem(row, 2, desc_item)

            # Imagen Principal
            img_item = QTableWidgetItem(art["imagen"])
            self._table.setItem(row, 3, img_item)

            # Envío Gratis
            backend_backup_dir = Path(__file__).parent.parent.parent / "Backend" / "Respaldo_Imagenes"
            local_backup_dir = Path(__file__).parent.parent / "backups"
            img_name = art["imagen"]
            has_free_shipping = False
            if img_name:
                has_free_shipping = (backend_backup_dir / img_name).exists() or (local_backup_dir / img_name).exists()

            envio_item = QTableWidgetItem("Sí" if has_free_shipping else "No")
            envio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if has_free_shipping:
                envio_item.setForeground(QColor(COLOR_SUCCESS))
            self._table.setItem(row, 4, envio_item)

            # Publicado
            pub_item = QTableWidgetItem("Sí" if art["publicado"] == "S" else "No")
            pub_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 5, pub_item)

        self._table.blockSignals(False)
        self._update_action_states()

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        """Actualiza el estado de selección de un artículo."""
        if item.column() == 0:
            code = item.data(Qt.ItemDataRole.UserRole)
            is_checked = item.checkState() == Qt.CheckState.Checked

            # Sincronizar con la lista principal
            for art in self._all_articles:
                if art["codigo"] == code:
                    art["checked"] = is_checked
                    break

            self._update_action_states()

    def _on_select_all_clicked(self) -> None:
        """Selecciona o deselecciona todos los artículos visibles actualmente."""
        checked = self._chk_select_all.isChecked()

        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            chk_item = self._table.item(row, 0)
            if chk_item:
                chk_item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                code = chk_item.data(Qt.ItemDataRole.UserRole)
                # Actualizar lista principal
                for art in self._all_articles:
                    if art["codigo"] == code:
                        art["checked"] = checked
                        break
        self._table.blockSignals(False)
        self._update_action_states()

    def _update_action_states(self) -> None:
        """Habilita o deshabilita botones de acción."""
        checked_count = sum(1 for art in self._all_articles if art["checked"])
        is_running = self._worker is not None and self._worker.isRunning()

        self._btn_apply.setEnabled(checked_count > 0 and not is_running)
        self._btn_remove.setEnabled(checked_count > 0 and not is_running)
        self._btn_load.setEnabled(not is_running)
        self._btn_cancel.setEnabled(is_running)

        if checked_count > 0:
            self._btn_apply.setText(f"Aplicar Envío Gratis ({checked_count})")
            self._btn_remove.setText(f"Quitar Envío Gratis ({checked_count})")
        else:
            self._btn_apply.setText("Aplicar Envío Gratis")
            self._btn_remove.setText("Quitar Envío Gratis")

    def _on_apply_clicked(self) -> None:
        """Inicia el proceso de estampar las imágenes de los artículos seleccionados."""
        if not self._ftp_service:
            QMessageBox.warning(self, "Error", "No hay conexión activa FTP configurada.")
            return

        # Obtener seleccionados
        selected = [art for art in self._all_articles if art["checked"]]
        if not selected:
            return

        confirm = QMessageBox.question(
            self,
            "Confirmación",
            f"¿Está seguro de que desea estampar el sello de Envío Gratis en las imágenes de {len(selected)} artículos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._txt_log.clear()

        # Iniciar worker
        self._worker = FreeShippingWorker(
            ftp_service=self._ftp_service,
            articles=selected,
            stamp_path=STAMP_PATH,
            action="apply",
            parent=self
        )

        self._worker.progress_updated.connect(self._on_worker_progress)
        self._worker.log_message.connect(self._log)
        self._worker.finished_stamping.connect(self._on_worker_finished)
        self._worker.error_occurred.connect(self._on_worker_error)
        self._worker.cancelled.connect(self._on_worker_cancelled)

        self._worker.start()
        self._update_action_states()

    def _on_remove_clicked(self) -> None:
        """Inicia el proceso de restaurar las imágenes originales sin el sello."""
        if not self._ftp_service:
            QMessageBox.warning(self, "Error", "No hay conexión activa FTP configurada.")
            return

        # Obtener seleccionados
        selected = [art for art in self._all_articles if art["checked"]]
        if not selected:
            return

        confirm = QMessageBox.question(
            self,
            "Confirmación",
            f"¿Está seguro de que desea quitar el sello de Envío Gratis y restaurar la imagen original de {len(selected)} artículos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._txt_log.clear()

        # Iniciar worker
        self._worker = FreeShippingWorker(
            ftp_service=self._ftp_service,
            articles=selected,
            stamp_path=STAMP_PATH,
            action="remove",
            parent=self
        )

        self._worker.progress_updated.connect(self._on_worker_progress)
        self._worker.log_message.connect(self._log)
        self._worker.finished_stamping.connect(self._on_worker_finished)
        self._worker.error_occurred.connect(self._on_worker_error)
        self._worker.cancelled.connect(self._on_worker_cancelled)

        self._worker.start()
        self._update_action_states()

    def _on_cancel_clicked(self) -> None:
        """Solicita la cancelación del worker."""
        if self._worker:
            self._worker.cancel()
            self._btn_cancel.setEnabled(False)
            self._log("Cancelación solicitada, esperando a que termine el artículo actual...")

    def _on_worker_progress(self, actual: int, total: int) -> None:
        self._progress.setMaximum(total)
        self._progress.setValue(actual)

    def _on_worker_finished(self, exitos: int, errores: int) -> None:
        self._progress.setVisible(False)
        self._worker = None
        self._update_action_states()

        # Desmarcar los artículos que fueron procesados con éxito
        # (Para que el usuario vea claramente qué le queda o si desea hacer otra tanda)
        # Como no sabemos cuáles fallaron específicamente en la lista principal sin más detalle,
        # podríamos simplemente limpiar la selección de todos.
        for art in self._all_articles:
            art["checked"] = False
        self._chk_select_all.setChecked(False)
        self._on_search_changed()

        QMessageBox.information(
            self,
            "Proceso Completado",
            f"Proceso finalizado.\n\nÉxitos: {exitos}\nErrores: {errores}"
        )

    def _on_worker_error(self, message: str) -> None:
        self._progress.setVisible(False)
        self._worker = None
        self._update_action_states()
        QMessageBox.critical(self, "Error fatal", message)

    def _on_worker_cancelled(self) -> None:
        self._progress.setVisible(False)
        self._worker = None
        self._update_action_states()
        QMessageBox.warning(self, "Cancelado", "El proceso fue cancelado por el usuario.")
