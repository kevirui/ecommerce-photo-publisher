"""
Pestaña de Editor, Renombrador y Reescalador de Fotos.

Permite cargar imágenes desde archivos o carpetas, previsualizarlas con
zoom/pan, recortarlas (libre o cuadrado 1:1), rotarlas, renombrarlas
y redimensionarlas a 800×800 por lotes con compresión inteligente.
"""

import io
import os

from PIL import Image, ImageOps, ImageDraw

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QCheckBox,
    QLineEdit,
    QProgressBar,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QTreeWidget,
    QTreeWidgetItem,
    QFormLayout,
    QSlider,
    QDialog,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import (
    QPixmap,
    QImage,
    QPainter,
    QPen,
    QKeySequence,
    QShortcut,
    QColor,
    QIcon,
)

from ui.styles import (
    COLOR_SUCCESS,
    COLOR_ERROR,
    COLOR_ACCENT,
    COLOR_BG_PRIMARY,
    COLOR_BG_SECONDARY,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_BTN_PRIMARY_BG,
    COLOR_BTN_PRIMARY_TEXT,
    COLOR_BTN_SECONDARY_BG,
    COLOR_BTN_DANGER_BG,
    COLOR_BTN_DANGER_TEXT,
    COLOR_WARNING,
)


# ============================================================
# Utilidades
# ============================================================


def pil_to_pixmap(pil_img: Image.Image) -> QPixmap:
    """Convierte una imagen PIL a QPixmap de manera segura."""
    if pil_img.mode == "RGB":
        data = pil_img.tobytes("raw", "RGB")
        bytes_per_line = pil_img.width * 3
        fmt = QImage.Format.Format_RGB888
    elif pil_img.mode == "RGBA":
        data = pil_img.tobytes("raw", "RGBA")
        bytes_per_line = pil_img.width * 4
        fmt = QImage.Format.Format_RGBA8888
    else:
        pil_img = pil_img.convert("RGBA")
        data = pil_img.tobytes("raw", "RGBA")
        bytes_per_line = pil_img.width * 4
        fmt = QImage.Format.Format_RGBA8888

    qim = QImage(data, pil_img.width, pil_img.height, bytes_per_line, fmt)
    return QPixmap.fromImage(qim.copy())


# ============================================================
# Diálogo de ajustes de reescalado
# ============================================================


class ResizeSettingsDialog(QDialog):
    """Diálogo modal para configurar el reescalado y optimización de imágenes (800x800)."""

    def __init__(
        self,
        parent,
        modo: str = "fit",
        fondo: str = "Blanco",
        rembg: bool = True,
        forzar_jpg: bool = True,
        optimizar: bool = True,
        eliminar_orig: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración de Reescalado 800x800")
        self.setMinimumWidth(360)

        layout = QFormLayout(self)

        mode_layout = QHBoxLayout()
        self.rb_fit = QRadioButton("Ajustar")
        self.rb_crop = QRadioButton("Recortar")
        self.rb_stretch = QRadioButton("Estirar")
        self.bg_mode = QButtonGroup(self)
        self.bg_mode.addButton(self.rb_fit)
        self.bg_mode.addButton(self.rb_crop)
        self.bg_mode.addButton(self.rb_stretch)

        if modo == "crop":
            self.rb_crop.setChecked(True)
        elif modo == "stretch":
            self.rb_stretch.setChecked(True)
        else:
            self.rb_fit.setChecked(True)

        mode_layout.addWidget(self.rb_fit)
        mode_layout.addWidget(self.rb_crop)
        mode_layout.addWidget(self.rb_stretch)
        layout.addRow("Método:", mode_layout)

        self.cb_color = QComboBox()
        self.cb_color.addItems(["Blanco", "Negro", "Gris", "Transparente"])
        self.cb_color.setCurrentText(fondo)
        layout.addRow("Fondo:", self.cb_color)

        self.chk_rembg = QCheckBox()
        self.chk_rembg.setChecked(rembg)
        layout.addRow("Remover Fondo (IA):", self.chk_rembg)

        self.chk_jpg = QCheckBox()
        self.chk_jpg.setChecked(forzar_jpg)
        layout.addRow("Forzar .JPG:", self.chk_jpg)

        self.chk_limit = QCheckBox()
        self.chk_limit.setChecked(optimizar)
        layout.addRow("Optimizar (<1MB):", self.chk_limit)

        self.chk_del = QCheckBox()
        self.chk_del.setChecked(eliminar_orig)
        layout.addRow("Eliminar orig.:", self.chk_del)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_settings(self) -> dict:
        """Devuelve un diccionario con las opciones configuradas."""
        modo = "fit"
        if self.rb_crop.isChecked():
            modo = "crop"
        elif self.rb_stretch.isChecked():
            modo = "stretch"

        return {
            "modo": modo,
            "fondo": self.cb_color.currentText(),
            "rembg": self.chk_rembg.isChecked(),
            "forzar_jpg": self.chk_jpg.isChecked(),
            "optimizar": self.chk_limit.isChecked(),
            "eliminar_orig": self.chk_del.isChecked(),
        }


ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons")


class ToleranceSlider(QSlider):
    """QSlider personalizado que responde a la rueda del mouse para cambiar la tolerancia de 1 en 1."""

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None) -> None:
        super().__init__(orientation, parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        step = 1
        if delta > 0:
            self.setValue(min(self.maximum(), self.value() + step))
        elif delta < 0:
            self.setValue(max(self.minimum(), self.value() - step))
        event.accept()


# ============================================================
# Canvas de visualización / recorte
# ============================================================


class PhotoEditorCanvas(QLabel):
    """
    Canvas personalizado para la vista previa de imágenes.

    Soporta zoom con rueda del mouse, paneo con arrastre,
    y selección de área de recorte con overlay visual.
    """

    def __init__(self, parent_tab: "PhotoEditorTab") -> None:
        super().__init__()
        self.parent_tab = parent_tab
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)
        self.setScaledContents(False)
        self.setMinimumSize(400, 300)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)

        if self.parent_tab.img_pil_actual is None:
            painter.setPen(QColor(COLOR_TEXT_PRIMARY))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Vista previa\n(Rueda del mouse para Zoom)\n"
                "(Flechitas teclado para pasar fotos)",
            )
            return

        if (
            self.parent_tab.modo_recorte
            and self.parent_tab.crop_start_x is not None
            and self.parent_tab.crop_end_x is not None
        ):
            x1 = self.parent_tab.crop_start_x
            y1 = self.parent_tab.crop_start_y
            x2 = self.parent_tab.crop_end_x
            y2 = self.parent_tab.crop_end_y

            self.parent_tab.coords_recorte_draw = (x1, y1, x2, y2)

            pen = QPen(QColor(COLOR_ERROR), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            from PyQt6.QtCore import QRect, QPoint

            painter.drawRect(
                QRect(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))
            )

    def wheelEvent(self, event) -> None:
        self.parent_tab.on_mouse_wheel(event)

    def mousePressEvent(self, event) -> None:
        self.parent_tab.on_click_izquierdo(event)

    def mouseMoveEvent(self, event) -> None:
        self.parent_tab.on_movimiento_izquierdo(event)

    def mouseReleaseEvent(self, event) -> None:
        self.parent_tab.on_soltar_izquierdo(event)


# ============================================================
# Pestaña: Editor de Fotos
# ============================================================


class PhotoEditorTab(QWidget):
    """
    Editor visual de fotos con funcionalidades de:
    - Carga desde archivos individuales o carpeta completa
    - Vista previa con zoom, pan y navegación por teclado
    - Recorte libre o cuadrado (1:1)
    - Rotación 90° izquierda/derecha
    - Renombrado individual (con modo secuencial)
    - Redimensionado a 800×800 con métodos: ajustar, recortar, estirar
    - Procesamiento por lotes con compresión inteligente (<1 MB)
    """

    def __init__(self) -> None:
        super().__init__()
        self.carpeta_actual = ""
        self.image_paths: list[str] = []
        self.indice_actual = -1
        self.img_pil_actual: Image.Image | None = None
        self.angulo_rotacion = 0

        # Zoom / Pan
        self.factor_zoom = 1.0
        self.zoom_min = 1.0
        self.zoom_max = 4.0
        self.pan_x = 0
        self.pan_y = 0
        self.start_x = 0
        self.start_y = 0
        self.is_panning = False

        # Recorte
        self.modo_recorte = False
        self.crop_start_x = None
        self.crop_start_y = None
        self.crop_end_x = None
        self.crop_end_y = None
        self.coords_recorte_draw = None
        self.coords_recorte_actual = None

        # Varita Mágica (Selección Difusa)
        self.modo_varita = False
        self.tolerance = 30
        self.historial_ediciones = []

        # Escala de renderizado (para mapear coords canvas → imagen real)
        self.img_escala_render_x = 1.0
        self.img_escala_render_y = 1.0
        self.img_offset_render_x = 0
        self.img_offset_render_y = 0

        self.output_dir = ""

        # Configuración de reescalado (800x800)
        self.resize_mode = "fit"
        self.resize_fill = "Blanco"
        self.resize_rembg = True
        self.resize_jpg = True
        self.resize_limit = True
        self.resize_del = False

        self._setup_ui()
        self._bind_shortcuts()

    # ----------------------------------------------------------------
    # Construcción de UI
    # ----------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Construye la interfaz completa de la pestaña."""
        main_layout = QVBoxLayout(self)

        # --- Panel superior: carga de archivos ---
        top_panel = QHBoxLayout()
        self.btn_folder = QPushButton("Seleccionar Carpeta")
        self.btn_folder.clicked.connect(self._load_folder)
        self.btn_clear = QPushButton("Limpiar Lista")
        self.btn_clear.clicked.connect(self._clear_list)

        self.lbl_contador = QLabel("Fotos encontradas: 0")

        top_panel.addWidget(self.btn_folder)
        top_panel.addWidget(self.btn_clear)
        top_panel.addWidget(self.lbl_contador)
        top_panel.addStretch()
        main_layout.addLayout(top_panel)

        # --- Splitter: árbol de archivos + editor visual ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: árbol de archivos
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Archivos (Usa Flechas ↑↓ o ←→):"))

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Nombre del Archivo", "Resolución Orig."])
        self.tree.itemSelectionChanged.connect(self._on_item_selected)
        left_layout.addWidget(self.tree)

        splitter.addWidget(left_widget)

        # Panel derecho: editor de imagen
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Iconos SVG de la barra de herramientas
        ic_rot_izq = QIcon(os.path.join(ICONS_DIR, "rotate_left.svg"))
        ic_rot_der = QIcon(os.path.join(ICONS_DIR, "rotate_right.svg"))
        ic_zoom_res = QIcon(os.path.join(ICONS_DIR, "zoom_reset.svg"))
        self.ic_crop = QIcon(os.path.join(ICONS_DIR, "crop.svg"))
        self.ic_crop_active = QIcon(os.path.join(ICONS_DIR, "crop_active.svg"))
        self.ic_wand = QIcon(os.path.join(ICONS_DIR, "wand.svg"))
        self.ic_wand_active = QIcon(os.path.join(ICONS_DIR, "wand_active.svg"))

        # Barra de herramientas
        controles_layout = QHBoxLayout()
        self.btn_rotar_izq = QPushButton()
        self.btn_rotar_izq.setIcon(ic_rot_izq)
        self.btn_rotar_izq.setIconSize(QSize(20, 20))
        self.btn_rotar_izq.setToolTip("Rotar 90° a la Izquierda")
        self.btn_rotar_izq.setFixedWidth(36)
        self.btn_rotar_izq.clicked.connect(lambda: self._rotar_imagen(-90))

        self.btn_rotar_der = QPushButton()
        self.btn_rotar_der.setIcon(ic_rot_der)
        self.btn_rotar_der.setIconSize(QSize(20, 20))
        self.btn_rotar_der.setToolTip("Rotar 90° a la Derecha")
        self.btn_rotar_der.setFixedWidth(36)
        self.btn_rotar_der.clicked.connect(lambda: self._rotar_imagen(90))

        self.btn_reset_zoom = QPushButton()
        self.btn_reset_zoom.setIcon(ic_zoom_res)
        self.btn_reset_zoom.setIconSize(QSize(20, 20))
        self.btn_reset_zoom.setToolTip("Restablecer Zoom")
        self.btn_reset_zoom.setFixedWidth(36)
        self.btn_reset_zoom.clicked.connect(self._reset_zoom)

        self.btn_recortar = QPushButton()
        self.btn_recortar.setIcon(self.ic_crop)
        self.btn_recortar.setIconSize(QSize(20, 20))
        self.btn_recortar.setToolTip("Modo Recorte")
        self.btn_recortar.setFixedWidth(36)
        self.btn_recortar.setStyleSheet(
            f"background-color: {COLOR_WARNING}; font-weight: bold;"
        )
        self.btn_recortar.clicked.connect(self._toggle_recorte)

        self.btn_varita = QPushButton()
        self.btn_varita.setIcon(self.ic_wand)
        self.btn_varita.setIconSize(QSize(20, 20))
        self.btn_varita.setToolTip("Varita Mágica")
        self.btn_varita.setFixedWidth(36)
        self.btn_varita.setStyleSheet(
            f"background-color: {COLOR_BTN_SECONDARY_BG};"
        )
        self.btn_varita.clicked.connect(self._toggle_varita)

        self.lbl_tolerance = QLabel("Tolerancia: 30")
        self.slider_tolerance = ToleranceSlider(Qt.Orientation.Horizontal)
        self.slider_tolerance.setRange(0, 150)
        self.slider_tolerance.setValue(30)
        self.slider_tolerance.setFixedWidth(100)
        self.slider_tolerance.valueChanged.connect(self._on_tolerance_changed)

        def _lbl_wheel(event):
            delta = event.angleDelta().y()
            step = 1
            val = self.slider_tolerance.value()
            if delta > 0:
                self.slider_tolerance.setValue(min(150, val + step))
            elif delta < 0:
                self.slider_tolerance.setValue(max(0, val - step))
            event.accept()

        self.lbl_tolerance.wheelEvent = _lbl_wheel

        self.btn_deshacer = QPushButton("Deshacer")
        self.btn_deshacer.setStyleSheet(
            f"background-color: {COLOR_BTN_SECONDARY_BG}; color: {COLOR_TEXT_PRIMARY};"
        )
        self.btn_deshacer.clicked.connect(self._undo)

        self.btn_confirmar_crop = QPushButton("Confirmar")
        self.btn_confirmar_crop.setStyleSheet(
            f"background-color: {COLOR_SUCCESS}; color: {COLOR_BG_PRIMARY}; font-weight: bold;"
        )
        self.btn_confirmar_crop.hide()
        self.btn_confirmar_crop.clicked.connect(self._confirmar_recorte)

        self.btn_cancelar_crop = QPushButton("Cancelar")
        self.btn_cancelar_crop.setStyleSheet(
            f"background-color: {COLOR_BTN_DANGER_BG}; color: {COLOR_BTN_DANGER_TEXT}; font-weight: bold;"
        )
        self.btn_cancelar_crop.hide()
        self.btn_cancelar_crop.clicked.connect(self._cancelar_recorte_dibujado)

        self.btn_eliminar = QPushButton("Eliminar (Supr)")
        self.btn_eliminar.setStyleSheet(
            f"background-color: {COLOR_BTN_DANGER_BG}; color: {COLOR_BTN_DANGER_TEXT}; font-weight: bold;"
        )
        self.btn_eliminar.clicked.connect(self._eliminar_foto)

        controles_layout.addWidget(self.btn_rotar_izq)
        controles_layout.addWidget(self.btn_rotar_der)
        controles_layout.addWidget(self.btn_reset_zoom)
        controles_layout.addWidget(self.btn_recortar)
        controles_layout.addWidget(self.btn_varita)
        controles_layout.addWidget(self.lbl_tolerance)
        controles_layout.addWidget(self.slider_tolerance)
        controles_layout.addWidget(self.btn_deshacer)
        controles_layout.addWidget(self.btn_confirmar_crop)
        controles_layout.addWidget(self.btn_cancelar_crop)
        controles_layout.addStretch()
        controles_layout.addWidget(self.btn_eliminar)
        right_layout.addLayout(controles_layout)

        # Canvas de visualización
        self.canvas_imagen = PhotoEditorCanvas(self)
        self.canvas_imagen.setStyleSheet(
            f"background-color: #11111b; border: 1px solid {COLOR_BORDER};"
        )
        self.canvas_imagen.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        right_layout.addWidget(self.canvas_imagen, stretch=1)

        splitter.addWidget(right_widget)
        splitter.setSizes([350, 700])

        main_layout.addWidget(splitter, stretch=1)

        # --- Salida y ejecución por lotes ---
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Carpeta de Salida:"))
        self.txt_out = QLineEdit()
        out_layout.addWidget(self.txt_out, stretch=1)
        self.btn_browse_out = QPushButton("Examinar...")
        self.btn_browse_out.clicked.connect(self._select_output_dir)
        out_layout.addWidget(self.btn_browse_out)
        main_layout.addLayout(out_layout)

        exec_layout = QHBoxLayout()
        self.progress = QProgressBar()
        exec_layout.addWidget(self.progress, stretch=1)

        self.btn_resize_settings = QPushButton("Configuración de Reescalado")
        self.btn_resize_settings.clicked.connect(self._abrir_ajustes_reescalado)
        exec_layout.addWidget(self.btn_resize_settings)

        self.btn_process = QPushButton(
            "REDIMENSIONAR Y OPTIMIZAR TODO POR LOTES"
        )
        self.btn_process.setStyleSheet(
            f"background-color: {COLOR_SUCCESS}; color: {COLOR_BG_PRIMARY}; font-weight: bold;"
        )
        self.btn_process.clicked.connect(self._process_images)
        exec_layout.addWidget(self.btn_process)
        main_layout.addLayout(exec_layout)

        self._habilitar_controles(False)

    def _bind_shortcuts(self) -> None:
        """Configura atajos de teclado."""
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self._navegar_lista(1))
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self._navegar_lista(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._eliminar_foto)
        QShortcut(QKeySequence("Ctrl+R"), self, lambda: self._rotar_imagen(90))
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)

    def _habilitar_controles(self, estado: bool) -> None:
        """Habilita o deshabilita controles de edición."""
        widgets = [
            self.btn_rotar_izq,
            self.btn_rotar_der,
            self.btn_reset_zoom,
            self.btn_recortar,
            self.btn_varita,
            self.slider_tolerance,
            self.btn_eliminar,
        ]
        for w in widgets:
            w.setEnabled(estado)
        self.btn_deshacer.setEnabled(estado and len(self.historial_ediciones) > 0)

    # ----------------------------------------------------------------
    # Navegación y carga
    # ----------------------------------------------------------------

    def _navegar_lista(self, direccion: int) -> None:
        """Navega a la foto anterior o siguiente en la lista."""
        if not self.image_paths or self.indice_actual == -1:
            return
        nuevo_idx = self.indice_actual + direccion
        if 0 <= nuevo_idx < len(self.image_paths):
            item = self.tree.topLevelItem(nuevo_idx)
            self.tree.setCurrentItem(item)

    def _abrir_ajustes_reescalado(self) -> None:
        """Abre la ventana modal de configuración de reescalado 800x800."""
        dlg = ResizeSettingsDialog(
            self,
            modo=self.resize_mode,
            fondo=self.resize_fill,
            rembg=self.resize_rembg,
            forzar_jpg=self.resize_jpg,
            optimizar=self.resize_limit,
            eliminar_orig=self.resize_del,
        )
        if dlg.exec():
            s = dlg.get_settings()
            self.resize_mode = s["modo"]
            self.resize_fill = s["fondo"]
            self.resize_rembg = s["rembg"]
            self.resize_jpg = s["forzar_jpg"]
            self.resize_limit = s["optimizar"]
            self.resize_del = s["eliminar_orig"]

    def _load_folder(self) -> None:
        """Abre diálogo para seleccionar una carpeta de imágenes."""
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if folder:
            valid_ext = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif")
            files = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith(valid_ext)
            ]
            if files:
                self._add_images_to_list(files)
            else:
                QMessageBox.warning(
                    self, "Sin imágenes", "No se encontraron imágenes compatibles."
                )

    def _add_images_to_list(self, file_paths: list[str]) -> None:
        """Agrega imágenes a la lista / árbol de archivos."""
        if not self.output_dir and file_paths:
            self.output_dir = os.path.join(
                os.path.dirname(file_paths[0]), "reescaladas_800x800"
            )
            self.txt_out.setText(self.output_dir)

        for path in file_paths:
            if path not in self.image_paths:
                self.image_paths.append(path)
                try:
                    with Image.open(path) as img:
                        size_str = f"{img.width} x {img.height}"
                except Exception:
                    size_str = "Error"
                item = QTreeWidgetItem([os.path.basename(path), size_str])
                self.tree.addTopLevelItem(item)

        self.lbl_contador.setText(f"Fotos encontradas: {len(self.image_paths)}")
        if self.image_paths and self.indice_actual == -1:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _clear_list(self) -> None:
        """Limpia la lista de archivos y el canvas."""
        self.image_paths.clear()
        self.tree.clear()
        self.indice_actual = -1
        self.img_pil_actual = None
        self.canvas_imagen.clear()
        self.lbl_contador.setText("Fotos encontradas: 0")
        self._habilitar_controles(False)

    def _select_output_dir(self) -> None:
        """Selecciona la carpeta de salida para el procesamiento por lotes."""
        folder = QFileDialog.getExistingDirectory(
            self, "Seleccionar Carpeta de Salida"
        )
        if folder:
            self.output_dir = folder
            self.txt_out.setText(folder)

    # ----------------------------------------------------------------
    # Selección y vista previa
    # ----------------------------------------------------------------

    def _on_item_selected(self) -> None:
        """Slot: se seleccionó un ítem en el árbol de archivos."""
        item = self.tree.currentItem()
        if not item:
            return
        row = self.tree.indexOfTopLevelItem(item)
        if row < 0 or row >= len(self.image_paths):
            return

        self.indice_actual = row
        ruta_completa = self.image_paths[self.indice_actual]
        self.carpeta_actual = os.path.dirname(ruta_completa)

        self.angulo_rotacion = 0
        self.factor_zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.is_panning = False
        self.canvas_imagen.unsetCursor()
        self.historial_ediciones.clear()
        self._desactivar_modo_recorte()
        self._desactivar_modo_varita()

        self.canvas_imagen.blockSignals(True)
        self._cargar_y_mostrar_imagen(ruta_completa)
        self.canvas_imagen.blockSignals(False)
        self._habilitar_controles(True)

    def _cargar_y_mostrar_imagen(self, ruta: str | None = None) -> None:
        """Carga y renderiza la imagen actual en el canvas."""
        if ruta:
            try:
                self.img_pil_actual = Image.open(ruta)
            except Exception:
                self.canvas_imagen.clear()
                self.img_pil_actual = None
                return

        if self.img_pil_actual:
            img_procesada = self.img_pil_actual.rotate(
                self.angulo_rotacion, expand=True
            )
            if img_procesada.mode == "RGBA":
                fondo_blanco = Image.new("RGB", img_procesada.size, (255, 255, 255))
                fondo_blanco.paste(img_procesada, mask=img_procesada.split()[3])
                img_procesada = fondo_blanco
            elif img_procesada.mode != "RGB":
                img_procesada = img_procesada.convert("RGB")

            ancho_max = max(100, self.canvas_imagen.width())
            alto_max = max(100, self.canvas_imagen.height())

            img_procesada.thumbnail((ancho_max, alto_max))
            ancho_thumbnail = img_procesada.width
            alto_thumbnail = img_procesada.height

            if self.factor_zoom > 1.0:
                nuevo_ancho = int(img_procesada.width * self.factor_zoom)
                nuevo_alto = int(img_procesada.height * self.factor_zoom)
                img_procesada = img_procesada.resize(
                    (nuevo_ancho, nuevo_alto), Image.Resampling.LANCZOS
                )

                lienzo = Image.new("RGB", (ancho_max, alto_max), (30, 30, 46))
                pos_x = (ancho_max - nuevo_ancho) // 2 + self.pan_x
                pos_y = (alto_max - nuevo_alto) // 2 + self.pan_y
                lienzo.paste(img_procesada, (pos_x, pos_y))

                rot_w = self.img_pil_actual.rotate(
                    self.angulo_rotacion, expand=True
                ).width
                rot_h = self.img_pil_actual.rotate(
                    self.angulo_rotacion, expand=True
                ).height
                self.img_escala_render_x = (rot_w / ancho_thumbnail) / self.factor_zoom
                self.img_escala_render_y = (rot_h / alto_thumbnail) / self.factor_zoom
                self.img_offset_render_x = pos_x
                self.img_offset_render_y = pos_y
                img_procesada = lienzo
            else:
                self.pan_x = 0
                self.pan_y = 0
                pos_x = (ancho_max - img_procesada.width) // 2
                pos_y = (alto_max - img_procesada.height) // 2

                rot_w = self.img_pil_actual.rotate(
                    self.angulo_rotacion, expand=True
                ).width
                rot_h = self.img_pil_actual.rotate(
                    self.angulo_rotacion, expand=True
                ).height
                self.img_escala_render_x = rot_w / img_procesada.width
                self.img_escala_render_y = rot_h / img_procesada.height
                self.img_offset_render_x = pos_x
                self.img_offset_render_y = pos_y

                lienzo = Image.new("RGB", (ancho_max, alto_max), (30, 30, 46))
                lienzo.paste(img_procesada, (pos_x, pos_y))
                img_procesada = lienzo

            self.canvas_imagen.setPixmap(pil_to_pixmap(img_procesada))
            self.canvas_imagen.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.img_pil_actual:
            self._cargar_y_mostrar_imagen()

    # ----------------------------------------------------------------
    # Recorte
    # ----------------------------------------------------------------

    def _toggle_recorte(self) -> None:
        """Alterna el modo recorte."""
        if not self.img_pil_actual:
            return
        if not self.modo_recorte:
            self._desactivar_modo_varita()
            self.modo_recorte = True
            self.btn_recortar.setToolTip("Salir de Recorte (Activo)")
            self.btn_recortar.setIcon(self.ic_crop_active)
            self.btn_recortar.setStyleSheet(
                f"background-color: {COLOR_BG_SECONDARY};"
            )
            self.canvas_imagen.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self._desactivar_modo_recorte()

    def _desactivar_modo_recorte(self) -> None:
        """Desactiva el modo recorte y restaura el cursor."""
        self.modo_recorte = False
        self.btn_recortar.setToolTip("Modo Recorte")
        self.btn_recortar.setIcon(self.ic_crop)
        self.btn_recortar.setStyleSheet(
            f"background-color: {COLOR_WARNING}; font-weight: bold;"
        )
        if self.factor_zoom > 1.0:
            self.canvas_imagen.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.canvas_imagen.unsetCursor()
        self._cancelar_recorte_dibujado()

    def _toggle_varita(self) -> None:
        """Alterna el modo varita mágica."""
        if not self.img_pil_actual:
            return
        if not self.modo_varita:
            self._desactivar_modo_recorte()
            self.modo_varita = True
            self.btn_varita.setToolTip("Salir de Varita Mágica (Activa)")
            self.btn_varita.setIcon(self.ic_wand_active)
            self.btn_varita.setStyleSheet(
                f"background-color: {COLOR_ACCENT}; font-weight: bold;"
            )
            self.canvas_imagen.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._desactivar_modo_varita()

    def _desactivar_modo_varita(self) -> None:
        """Desactiva el modo varita mágica y restaura el cursor."""
        self.modo_varita = False
        self.btn_varita.setToolTip("Varita Mágica")
        self.btn_varita.setIcon(self.ic_wand)
        self.btn_varita.setStyleSheet(
            f"background-color: {COLOR_BTN_SECONDARY_BG};"
        )
        if self.factor_zoom > 1.0:
            self.canvas_imagen.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.canvas_imagen.unsetCursor()

    def _on_tolerance_changed(self, value: int) -> None:
        """Slot: cambia la tolerancia del selector difuso."""
        self.tolerance = value
        self.lbl_tolerance.setText(f"Tolerancia: {value}")

    def _push_historial(self) -> None:
        """Guarda una copia de la imagen actual en el historial de deshacer."""
        if self.img_pil_actual:
            self.historial_ediciones.append(self.img_pil_actual.copy())
            if len(self.historial_ediciones) > 15:
                self.historial_ediciones.pop(0)
            self.btn_deshacer.setEnabled(True)

    def _undo(self) -> None:
        """Revierte el último cambio de la imagen."""
        if not self.historial_ediciones:
            return
        prev_img = self.historial_ediciones.pop()
        self.img_pil_actual = prev_img
        self.angulo_rotacion = 0
        self._cargar_y_mostrar_imagen()
        self._guardar_imagen_actual()
        self.btn_deshacer.setEnabled(len(self.historial_ediciones) > 0)

    def _guardar_imagen_actual(self) -> None:
        """Guarda la imagen actual en el disco y actualiza su resolución."""
        if not self.img_pil_actual or self.indice_actual == -1:
            return
        ruta_foto = self.image_paths[self.indice_actual]
        try:
            self.img_pil_actual.save(ruta_foto)
            if self.tree.currentItem():
                self.tree.currentItem().setText(
                    1,
                    f"{self.img_pil_actual.width} x {self.img_pil_actual.height}",
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error al guardar", f"No se pudo guardar la imagen: {e}"
            )

    def _cancelar_recorte_dibujado(self) -> None:
        """Cancela el recorte actual y limpia la selección visual."""
        self.coords_recorte_actual = None
        self.coords_recorte_draw = None
        self.crop_start_x = None
        self.crop_start_y = None
        self.crop_end_x = None
        self.crop_end_y = None
        self.btn_confirmar_crop.hide()
        self.btn_cancelar_crop.hide()
        self.canvas_imagen.update()

    def _confirmar_recorte(self) -> None:
        """Aplica el recorte seleccionado y guarda la imagen."""
        if not self.coords_recorte_actual or not self.img_pil_actual:
            return
        lc, tc, rc, bc = self.coords_recorte_actual
        try:
            self._push_historial()
            img_rotada = self.img_pil_actual.rotate(
                self.angulo_rotacion, expand=True
            )
            real_left = int((lc - self.img_offset_render_x) * self.img_escala_render_x)
            real_top = int((tc - self.img_offset_render_y) * self.img_escala_render_y)
            real_right = int(
                (rc - self.img_offset_render_x) * self.img_escala_render_x
            )
            real_bottom = int(
                (bc - self.img_offset_render_y) * self.img_escala_render_y
            )

            real_left = max(0, min(img_rotada.width, real_left))
            real_top = max(0, min(img_rotada.height, real_top))
            real_right = max(0, min(img_rotada.width, real_right))
            real_bottom = max(0, min(img_rotada.height, real_bottom))

            if real_right <= real_left or real_bottom <= real_top:
                return
            self.img_pil_actual = img_rotada.crop(
                (real_left, real_top, real_right, real_bottom)
            )
            self.angulo_rotacion = 0
            self._cancelar_recorte_dibujado()
            self._cargar_y_mostrar_imagen()
            self._guardar_imagen_actual()
        except Exception as e:
            QMessageBox.critical(
                self, "Error al recortar", f"Problema al aplicar corte: {e}"
            )

    # ----------------------------------------------------------------
    # Zoom / Pan / Eventos de mouse
    # ----------------------------------------------------------------

    def on_mouse_wheel(self, event) -> None:
        """Maneja el zoom con la rueda del mouse."""
        if not self.img_pil_actual or self.modo_recorte:
            return
        delta = event.angleDelta().y()
        if delta > 0:
            self.factor_zoom += 0.2
        else:
            self.factor_zoom -= 0.2
        self.factor_zoom = max(self.zoom_min, min(self.zoom_max, self.factor_zoom))
        if self.factor_zoom == 1.0:
            self.pan_x = 0
            self.pan_y = 0
            self.is_panning = False
            if not self.modo_recorte and not self.modo_varita:
                self.canvas_imagen.unsetCursor()
        else:
            if not self.modo_recorte and not self.modo_varita:
                self.canvas_imagen.setCursor(Qt.CursorShape.OpenHandCursor)
        self._cargar_y_mostrar_imagen()

    def on_click_izquierdo(self, event) -> None:
        """Maneja el click izquierdo: inicia recorte o pan o varita."""
        if not self.img_pil_actual:
            return
        if self.modo_recorte:
            self.crop_start_x = event.pos().x()
            self.crop_start_y = event.pos().y()
            self.crop_end_x = self.crop_start_x
            self.crop_end_y = self.crop_start_y
            self.canvas_imagen.update()
        elif self.modo_varita:
            cx = event.pos().x()
            cy = event.pos().y()
            # Mapear coordenadas a la imagen real
            ix = int((cx - self.img_offset_render_x) * self.img_escala_render_x)
            iy = int((cy - self.img_offset_render_y) * self.img_escala_render_y)

            # Rotar temporalmente la imagen si tiene rotación (aunque ya se guarda rotada, por si acaso)
            img_real = self.img_pil_actual.rotate(self.angulo_rotacion, expand=True)

            if 0 <= ix < img_real.width and 0 <= iy < img_real.height:
                self._push_historial()
                try:
                    if img_real.mode != "RGB":
                        img_real = img_real.convert("RGB")
                    ImageDraw.floodfill(img_real, (ix, iy), (255, 255, 255), thresh=self.tolerance)
                    self.img_pil_actual = img_real
                    self.angulo_rotacion = 0
                    self._cargar_y_mostrar_imagen()
                    self._guardar_imagen_actual()
                except Exception as e:
                    QMessageBox.critical(
                        self, "Error", f"No se pudo aplicar la varita mágica: {e}"
                    )
        else:
            if self.factor_zoom > 1.0 and event.button() == Qt.MouseButton.LeftButton:
                self.is_panning = True
                self.start_x = event.pos().x()
                self.start_y = event.pos().y()
                self.canvas_imagen.setCursor(Qt.CursorShape.ClosedHandCursor)

    def on_movimiento_izquierdo(self, event) -> None:
        """Maneja el arrastre: actualiza recorte o pan."""
        if not self.img_pil_actual:
            return
        if self.modo_recorte and self.crop_start_x is not None:
            self.crop_end_x = event.pos().x()
            self.crop_end_y = event.pos().y()
            self.canvas_imagen.update()
        elif self.is_panning and (event.buttons() & Qt.MouseButton.LeftButton):
            if self.factor_zoom > 1.0:
                dx = event.pos().x() - self.start_x
                dy = event.pos().y() - self.start_y
                self.pan_x += dx
                self.pan_y += dy
                self.start_x = event.pos().x()
                self.start_y = event.pos().y()
                self._cargar_y_mostrar_imagen()

    def on_soltar_izquierdo(self, event) -> None:
        """Maneja el soltar botón: finaliza recorte o pan."""
        if self.modo_recorte and self.coords_recorte_draw is not None:
            x1, y1, x2, y2 = self.coords_recorte_draw
            left_canvas = min(x1, x2)
            top_canvas = min(y1, y2)
            right_canvas = max(x1, x2)
            bottom_canvas = max(y1, y2)

            if (right_canvas - left_canvas) > 10 and (
                bottom_canvas - top_canvas
            ) > 10:
                self.coords_recorte_actual = (
                    left_canvas,
                    top_canvas,
                    right_canvas,
                    bottom_canvas,
                )
                self.btn_confirmar_crop.show()
                self.btn_cancelar_crop.show()
            else:
                self._cancelar_recorte_dibujado()
        self.crop_start_x = None
        self.crop_start_y = None
        self.crop_end_x = None
        self.crop_end_y = None

        if self.is_panning:
            self.is_panning = False
            if self.factor_zoom > 1.0 and not self.modo_recorte and not self.modo_varita:
                self.canvas_imagen.setCursor(Qt.CursorShape.OpenHandCursor)

    # ----------------------------------------------------------------
    # Rotación y eliminación
    # ----------------------------------------------------------------

    def _reset_zoom(self) -> None:
        """Resetea el zoom y el pan a valores por defecto."""
        self.factor_zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.is_panning = False
        if not self.modo_recorte and not self.modo_varita:
            self.canvas_imagen.unsetCursor()
        self._cargar_y_mostrar_imagen()

    def _rotar_imagen(self, angulo: int) -> None:
        """Rota la imagen y la guarda."""
        if not self.img_pil_actual or self.indice_actual == -1:
            return
        try:
            self._push_historial()
            self.img_pil_actual = self.img_pil_actual.rotate(angulo, expand=True)
            self.angulo_rotacion = 0
            self._cargar_y_mostrar_imagen()
            self._guardar_imagen_actual()
        except Exception as e:
            QMessageBox.critical(
                self, "Error al rotar", f"No se pudo guardar: {e}"
            )

    def _eliminar_foto(self) -> None:
        """Elimina la foto actual del disco y de la lista."""
        if self.indice_actual == -1 or not self.image_paths:
            return
        ruta_foto = self.image_paths[self.indice_actual]
        nombre_foto = os.path.basename(ruta_foto)
        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"¿Eliminar {nombre_foto}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.img_pil_actual:
                    self.img_pil_actual.close()
                os.remove(ruta_foto)
                self.tree.takeTopLevelItem(self.indice_actual)
                self.image_paths.pop(self.indice_actual)
                self.lbl_contador.setText(
                    f"Fotos encontradas: {len(self.image_paths)}"
                )
                if not self.image_paths:
                    self.indice_actual = -1
                    self.canvas_imagen.clear()
                    self._habilitar_controles(False)
                else:
                    if self.indice_actual >= len(self.image_paths):
                        self.indice_actual = len(self.image_paths) - 1
                    item = self.tree.topLevelItem(self.indice_actual)
                    self.tree.setCurrentItem(item)
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"No se pudo eliminar: {e}"
                )



    # ----------------------------------------------------------------
    # Procesamiento de imagen
    # ----------------------------------------------------------------

    def _process_pil_image(
        self, img: Image.Image, mode: str, fill_name: str, remove_bg: bool = False, session=None
    ) -> Image.Image:
        """Redimensiona una imagen a 800×800 según el método seleccionado."""
        if remove_bg:
            try:
                from rembg import remove
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                if session is not None:
                    out_bytes = remove(buf.getvalue(), session=session)
                else:
                    out_bytes = remove(buf.getvalue())
                img = Image.open(io.BytesIO(out_bytes)).convert("RGBA")
                bbox = img.getbbox()
                if bbox:
                    img = img.crop(bbox)
            except Exception as e:
                print(f"Error al remover fondo en editor: {e}")

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert(
                "RGBA"
                if "transparency" in img.info or img.mode == "P"
                else "RGB"
            )

        target_size = (800, 800)
        if mode == "stretch":
            res = img.resize(target_size, Image.Resampling.LANCZOS)
        elif mode == "crop":
            res = ImageOps.fit(img, target_size, Image.Resampling.LANCZOS)
        else:
            img.thumbnail(target_size, Image.Resampling.LANCZOS)
            res = img

        if fill_name == "Transparente" and not self.resize_jpg:
            bg = Image.new("RGBA", target_size, (0, 0, 0, 0))
        else:
            color_map = {
                "Negro": (0, 0, 0),
                "Blanco": (255, 255, 255),
                "Gris": (128, 128, 128),
            }
            bg_color = color_map.get(fill_name, (255, 255, 255))
            if res.mode == "RGBA":
                bg = Image.new("RGBA", target_size, bg_color + (255,))
            else:
                bg = Image.new("RGB", target_size, bg_color)

        x = (target_size[0] - res.width) // 2
        y = (target_size[1] - res.height) // 2
        bg.paste(res, (x, y), res if res.mode == "RGBA" else None)
        return bg

    def _process_single_image(
        self, img_path: str, mode: str, fill_name: str, remove_bg: bool = False, session=None
    ) -> Image.Image:
        """Abre y procesa una imagen individual."""
        with Image.open(img_path) as img:
            return self._process_pil_image(img, mode, fill_name, remove_bg=remove_bg, session=session)

    def _save_with_smart_compression(
        self, res_img: Image.Image, target_path: str, save_format: str
    ) -> None:
        """Guarda la imagen con compresión inteligente para mantenerla <1 MB."""
        quality = 90
        buffer = io.BytesIO()
        if save_format == "JPEG" and res_img.mode == "RGBA":
            res_img = res_img.convert("RGB")

        res_img.save(buffer, format=save_format, quality=quality)
        if (
            self.resize_limit
            and buffer.tell() > 1048576
            and save_format in ("JPEG", "WEBP")
        ):
            while quality > 20:
                buffer = io.BytesIO()
                quality -= 5
                res_img.save(buffer, format=save_format, quality=quality)
                if buffer.tell() <= 972800:
                    break

        with open(target_path, "wb") as f:
            f.write(buffer.getvalue())

    # ----------------------------------------------------------------
    # Procesamiento por lotes
    # ----------------------------------------------------------------

    def _process_images(self) -> None:
        """Procesa todas las imágenes de la lista en lote."""
        if not self.image_paths:
            return
        out_dir = self.txt_out.text().strip()
        if not out_dir:
            return
        os.makedirs(out_dir, exist_ok=True)

        self.btn_process.setEnabled(False)
        self.progress.setMaximum(len(self.image_paths))

        processed_count, error_count = 0, 0
        mode = self.resize_mode
        fill_name = self.resize_fill
        remove_bg = self.resize_rembg

        session = None
        if remove_bg:
            try:
                from rembg import new_session
                try:
                    session = new_session("birefnet-general-use")
                except Exception:
                    session = new_session("isnet-general-use")
            except Exception as e:
                print(f"Error al inicializar rembg: {e}")

        from PyQt6.QtWidgets import QApplication

        for idx, path in enumerate(self.image_paths):
            try:
                res_img = self._process_single_image(
                    path, mode, fill_name, remove_bg=remove_bg, session=session
                )
                name_part, ext = os.path.splitext(os.path.basename(path))

                if self.resize_jpg:
                    target_path = os.path.join(out_dir, f"{name_part}.jpg")
                    save_format = "JPEG"
                else:
                    ext_lower = ext.lower()
                    if ext_lower in (".jpg", ".jpeg"):
                        save_format = "JPEG"
                        target_path = os.path.join(out_dir, f"{name_part}.jpg")
                    elif ext_lower == ".png":
                        save_format = "PNG"
                        target_path = os.path.join(out_dir, f"{name_part}.png")
                    elif ext_lower == ".webp":
                        save_format = "WEBP"
                        target_path = os.path.join(out_dir, f"{name_part}.webp")
                    else:
                        save_format = "JPEG"
                        target_path = os.path.join(out_dir, f"{name_part}.jpg")

                self._save_with_smart_compression(res_img, target_path, save_format)
                processed_count += 1

                if self.resize_del and os.path.exists(path):
                    if os.path.abspath(path) != os.path.abspath(target_path):
                        os.remove(path)
            except Exception:
                error_count += 1
            self.progress.setValue(idx + 1)
            QApplication.processEvents()

        self.btn_process.setEnabled(True)
        QMessageBox.information(
            self,
            "Finalizado",
            f"Procesadas: {processed_count}\nErrores: {error_count}",
        )

        if self.resize_del:
            # Filtrar rutas existentes
            self.image_paths = [p for p in self.image_paths if os.path.exists(p)]
            # Reconstruir árbol
            self.tree.clear()
            self.indice_actual = -1
            self.img_pil_actual = None
            self.canvas_imagen.clear()
            for path in self.image_paths:
                try:
                    with Image.open(path) as img:
                        size_str = f"{img.width} x {img.height}"
                except Exception:
                    size_str = "Error"
                item = QTreeWidgetItem([os.path.basename(path), size_str])
                self.tree.addTopLevelItem(item)
            self.lbl_contador.setText(f"Fotos encontradas: {len(self.image_paths)}")
            if self.image_paths:
                self.tree.setCurrentItem(self.tree.topLevelItem(0))
