"""
Pestaña de Editor, Renombrador y Reescalador de Fotos.

Permite cargar imágenes desde archivos o carpetas, previsualizarlas con
zoom/pan, recortarlas (libre o cuadrado 1:1), rotarlas, renombrarlas
y redimensionarlas a 800×800 por lotes con compresión inteligente.
"""

import io
import os

from PIL import Image, ImageOps

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QCheckBox,
    QLineEdit,
    QGroupBox,
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
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QPixmap,
    QImage,
    QPainter,
    QPen,
    QKeySequence,
    QShortcut,
    QColor,
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

            if self.parent_tab.chk_cuadrado.isChecked():
                lado = max(abs(x2 - x1), abs(y2 - y1))
                x2 = x1 + lado if x2 >= x1 else x1 - lado
                y2 = y1 + lado if y2 >= y1 else y1 - lado

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

        # Recorte
        self.modo_recorte = False
        self.crop_start_x = None
        self.crop_start_y = None
        self.crop_end_x = None
        self.crop_end_y = None
        self.coords_recorte_draw = None
        self.coords_recorte_actual = None

        # Escala de renderizado (para mapear coords canvas → imagen real)
        self.img_escala_render_x = 1.0
        self.img_escala_render_y = 1.0
        self.img_offset_render_x = 0
        self.img_offset_render_y = 0

        # Contador secuencial para renombrado
        self.contador_secuencial = 1
        self.output_dir = ""

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
        self.btn_files = QPushButton("📂 Seleccionar Archivos")
        self.btn_files.clicked.connect(self._load_files)
        self.btn_folder = QPushButton("📁 Seleccionar Carpeta")
        self.btn_folder.clicked.connect(self._load_folder)
        self.btn_clear = QPushButton("❌ Limpiar Lista")
        self.btn_clear.clicked.connect(self._clear_list)

        self.lbl_contador = QLabel("Fotos encontradas: 0")

        top_panel.addWidget(self.btn_files)
        top_panel.addWidget(self.btn_folder)
        top_panel.addWidget(self.btn_clear)
        top_panel.addWidget(self.lbl_contador)
        top_panel.addStretch()

        self.chk_secuencial = QCheckBox("Modo Secuencial (Auto -1, -2...)")
        top_panel.addWidget(self.chk_secuencial)
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

        # Barra de herramientas
        controles_layout = QHBoxLayout()
        self.btn_rotar_izq = QPushButton("🔄 Rotar Izq")
        self.btn_rotar_izq.clicked.connect(lambda: self._rotar_imagen(-90))
        self.btn_rotar_der = QPushButton("🔄 Rotar Der")
        self.btn_rotar_der.clicked.connect(lambda: self._rotar_imagen(90))
        self.btn_reset_zoom = QPushButton("🔍 Reset Zoom")
        self.btn_reset_zoom.clicked.connect(self._reset_zoom)

        self.btn_recortar = QPushButton("✂️ Modo Recorte")
        self.btn_recortar.setStyleSheet(
            f"background-color: {COLOR_WARNING}; color: {COLOR_BG_PRIMARY}; font-weight: bold;"
        )
        self.btn_recortar.clicked.connect(self._toggle_recorte)
        self.chk_cuadrado = QCheckBox("Forzar Cuadrado (1:1 Web)")
        self.chk_cuadrado.setChecked(True)

        self.btn_confirmar_crop = QPushButton("✔️ Confirmar")
        self.btn_confirmar_crop.setStyleSheet(
            f"background-color: {COLOR_SUCCESS}; color: {COLOR_BG_PRIMARY}; font-weight: bold;"
        )
        self.btn_confirmar_crop.hide()
        self.btn_confirmar_crop.clicked.connect(self._confirmar_recorte)

        self.btn_cancelar_crop = QPushButton("❌ Cancelar")
        self.btn_cancelar_crop.setStyleSheet(
            f"background-color: {COLOR_BTN_DANGER_BG}; color: {COLOR_BTN_DANGER_TEXT}; font-weight: bold;"
        )
        self.btn_cancelar_crop.hide()
        self.btn_cancelar_crop.clicked.connect(self._cancelar_recorte_dibujado)

        self.btn_eliminar = QPushButton("🗑️ Eliminar (Supr)")
        self.btn_eliminar.setStyleSheet(
            f"background-color: {COLOR_BTN_DANGER_BG}; color: {COLOR_BTN_DANGER_TEXT}; font-weight: bold;"
        )
        self.btn_eliminar.clicked.connect(self._eliminar_foto)

        controles_layout.addWidget(self.btn_rotar_izq)
        controles_layout.addWidget(self.btn_rotar_der)
        controles_layout.addWidget(self.btn_reset_zoom)
        controles_layout.addWidget(self.btn_recortar)
        controles_layout.addWidget(self.chk_cuadrado)
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

        # --- Panel inferior: renombrado + reescalado ---
        bottom_config_layout = QHBoxLayout()

        # Grupo de renombrado
        group_rename = QGroupBox("Opciones de Renombrado")
        rename_form = QFormLayout(group_rename)
        self.txt_nuevo_nombre = QLineEdit()
        self.txt_nuevo_nombre.returnPressed.connect(self._renombrar_foto)
        self.btn_renombrar = QPushButton("Renombrar (Enter)")
        self.btn_renombrar.setStyleSheet(
            f"background-color: {COLOR_SUCCESS}; color: {COLOR_BG_PRIMARY}; font-weight: bold;"
        )
        self.btn_renombrar.clicked.connect(self._renombrar_foto)

        rename_form.addRow("Nuevo nombre:", self.txt_nuevo_nombre)
        rename_form.addRow("", self.btn_renombrar)
        bottom_config_layout.addWidget(group_rename, stretch=1)

        # Grupo de reescalado
        group_resize = QGroupBox("Configuración de Reescalado 800x800")
        resize_form = QFormLayout(group_resize)

        mode_layout = QHBoxLayout()
        self.rb_fit = QRadioButton("Ajustar")
        self.rb_fit.setChecked(True)
        self.rb_crop = QRadioButton("Recortar")
        self.rb_stretch = QRadioButton("Estirar")
        self.bg_mode = QButtonGroup()
        self.bg_mode.addButton(self.rb_fit)
        self.bg_mode.addButton(self.rb_crop)
        self.bg_mode.addButton(self.rb_stretch)
        mode_layout.addWidget(self.rb_fit)
        mode_layout.addWidget(self.rb_crop)
        mode_layout.addWidget(self.rb_stretch)
        resize_form.addRow("Método:", mode_layout)

        self.cb_color = QComboBox()
        self.cb_color.addItems(["Blanco", "Negro", "Gris", "Transparente"])
        resize_form.addRow("Fondo:", self.cb_color)

        self.chk_jpg = QCheckBox("Forzar .JPG")
        self.chk_jpg.setChecked(True)
        self.chk_limit = QCheckBox("Optimizar (<1MB)")
        self.chk_limit.setChecked(True)
        self.chk_del = QCheckBox("Eliminar orig.")
        chk_layout = QHBoxLayout()
        chk_layout.addWidget(self.chk_jpg)
        chk_layout.addWidget(self.chk_limit)
        chk_layout.addWidget(self.chk_del)
        resize_form.addRow("Opciones:", chk_layout)

        bottom_config_layout.addWidget(group_resize, stretch=2)
        main_layout.addLayout(bottom_config_layout)

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
        self.btn_process = QPushButton(
            "⚡ REDIMENSIONAR Y OPTIMIZAR TODO POR LOTES"
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

    def _habilitar_controles(self, estado: bool) -> None:
        """Habilita o deshabilita controles de edición."""
        widgets = [
            self.btn_rotar_izq,
            self.btn_rotar_der,
            self.btn_reset_zoom,
            self.btn_recortar,
            self.btn_eliminar,
            self.btn_renombrar,
            self.txt_nuevo_nombre,
        ]
        for w in widgets:
            w.setEnabled(estado)

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

    def _load_files(self) -> None:
        """Abre diálogo para seleccionar archivos de imagen individuales."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleccionar Imágenes",
            "",
            "Imágenes (*.jpg *.jpeg *.png *.webp *.bmp *.tiff *.gif)",
        )
        if files:
            self._add_images_to_list(files)

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

        nombre_sin_ext, _ = os.path.splitext(os.path.basename(ruta_completa))
        self.txt_nuevo_nombre.clear()

        if self.chk_secuencial.isChecked():
            self.txt_nuevo_nombre.setText(nombre_sin_ext.rsplit("-", 1)[0])
        else:
            self.txt_nuevo_nombre.setText(nombre_sin_ext)

        self.txt_nuevo_nombre.setFocus()
        self.txt_nuevo_nombre.selectAll()

        self.angulo_rotacion = 0
        self.factor_zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self._desactivar_modo_recorte()

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
            self.modo_recorte = True
            self.btn_recortar.setText("Salir de Recorte")
            self.btn_recortar.setStyleSheet(
                f"background-color: {COLOR_BG_SECONDARY}; color: {COLOR_TEXT_PRIMARY};"
            )
            self.canvas_imagen.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self._desactivar_modo_recorte()

    def _desactivar_modo_recorte(self) -> None:
        """Desactiva el modo recorte y restaura el cursor."""
        self.modo_recorte = False
        self.btn_recortar.setText("✂️ Modo Recorte")
        self.btn_recortar.setStyleSheet(
            f"background-color: {COLOR_WARNING}; color: {COLOR_BG_PRIMARY}; font-weight: bold;"
        )
        self.canvas_imagen.unsetCursor()
        self._cancelar_recorte_dibujado()

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

            ruta_foto = self.image_paths[self.indice_actual]
            self.img_pil_actual.save(ruta_foto)
            # Actualizar resolución en el árbol
            if self.tree.currentItem():
                self.tree.currentItem().setText(
                    1,
                    f"{self.img_pil_actual.width} x {self.img_pil_actual.height}",
                )
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
        self._cargar_y_mostrar_imagen()

    def on_click_izquierdo(self, event) -> None:
        """Maneja el click izquierdo: inicia recorte o pan."""
        if not self.img_pil_actual:
            return
        if self.modo_recorte:
            self.crop_start_x = event.pos().x()
            self.crop_start_y = event.pos().y()
            self.crop_end_x = self.crop_start_x
            self.crop_end_y = self.crop_start_y
            self.canvas_imagen.update()
        else:
            if self.factor_zoom > 1.0:
                self.start_x = event.pos().x()
                self.start_y = event.pos().y()

    def on_movimiento_izquierdo(self, event) -> None:
        """Maneja el arrastre: actualiza recorte o pan."""
        if not self.img_pil_actual:
            return
        if self.modo_recorte and self.crop_start_x is not None:
            self.crop_end_x = event.pos().x()
            self.crop_end_y = event.pos().y()
            self.canvas_imagen.update()
        else:
            if self.factor_zoom > 1.0:
                dx = event.pos().x() - self.start_x
                dy = event.pos().y() - self.start_y
                self.pan_x += dx
                self.pan_y += dy
                self.start_x = event.pos().x()
                self.start_y = event.pos().y()
                self._cargar_y_mostrar_imagen()

    def on_soltar_izquierdo(self, event) -> None:
        """Maneja el soltar botón: finaliza recorte."""
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

    # ----------------------------------------------------------------
    # Rotación y eliminación
    # ----------------------------------------------------------------

    def _reset_zoom(self) -> None:
        """Resetea el zoom y el pan a valores por defecto."""
        self.factor_zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self._cargar_y_mostrar_imagen()

    def _rotar_imagen(self, angulo: int) -> None:
        """Rota la imagen y la guarda."""
        if not self.img_pil_actual or self.indice_actual == -1:
            return
        try:
            self.img_pil_actual = self.img_pil_actual.rotate(angulo, expand=True)
            ruta_foto = self.image_paths[self.indice_actual]
            self.img_pil_actual.save(ruta_foto)
            self.angulo_rotacion = 0
            self._cargar_y_mostrar_imagen()
            # Actualizar resolución en el árbol
            if self.tree.currentItem():
                self.tree.currentItem().setText(
                    1,
                    f"{self.img_pil_actual.width} x {self.img_pil_actual.height}",
                )
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
                    self.txt_nuevo_nombre.clear()
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
    # Renombrado
    # ----------------------------------------------------------------

    def _renombrar_foto(self) -> None:
        """Renombra la foto actual, la reescala a 800×800 y avanza a la siguiente."""
        if self.indice_actual == -1 or not self.image_paths:
            return
        ruta_original = self.image_paths[self.indice_actual]
        nombre_original = os.path.basename(ruta_original)
        dir_original = os.path.dirname(ruta_original)

        nuevo_nombre_base = self.txt_nuevo_nombre.text().strip()
        if not nuevo_nombre_base:
            return
        _, ext = os.path.splitext(nombre_original)

        if self.chk_jpg.isChecked():
            ext = ".jpg"
            save_format = "JPEG"
        else:
            ext_lower = ext.lower()
            if ext_lower in (".jpg", ".jpeg"):
                save_format, ext = "JPEG", ".jpg"
            elif ext_lower == ".png":
                save_format, ext = "PNG", ".png"
            elif ext_lower == ".webp":
                save_format, ext = "WEBP", ".webp"
            else:
                save_format, ext = "JPEG", ".jpg"

        if self.chk_secuencial.isChecked():
            nuevo_nombre_completo = (
                f"{nuevo_nombre_base}-{self.contador_secuencial}{ext}"
            )
        else:
            nuevo_nombre_completo = nuevo_nombre_base + ext

        ruta_nueva = os.path.join(dir_original, nuevo_nombre_completo)

        if os.path.exists(ruta_nueva) and os.path.abspath(
            ruta_original
        ) != os.path.abspath(ruta_nueva):
            QMessageBox.warning(
                self, "Atención", "Ya existe un archivo con ese nombre."
            )
            return

        try:
            if not self.img_pil_actual:
                self.img_pil_actual = Image.open(ruta_original)

            mode = "fit"
            if self.rb_crop.isChecked():
                mode = "crop"
            elif self.rb_stretch.isChecked():
                mode = "stretch"
            fill_name = self.cb_color.currentText()

            res_img = self._process_pil_image(self.img_pil_actual, mode, fill_name)
            self.img_pil_actual.close()
            self.img_pil_actual = None

            self._save_with_smart_compression(res_img, ruta_nueva, save_format)

            if os.path.abspath(ruta_original) != os.path.abspath(
                ruta_nueva
            ) and os.path.exists(ruta_original):
                os.remove(ruta_original)

            self.image_paths[self.indice_actual] = ruta_nueva
            if self.tree.currentItem():
                self.tree.currentItem().setText(0, nuevo_nombre_completo)
                self.tree.currentItem().setText(1, "800 x 800")
            if self.chk_secuencial.isChecked():
                self.contador_secuencial += 1

            proximo_indice = self.indice_actual + 1
            if proximo_indice < len(self.image_paths):
                item = self.tree.topLevelItem(proximo_indice)
                self.tree.setCurrentItem(item)
            else:
                self.contador_secuencial = 1
                QMessageBox.information(
                    self, "¡Terminado!", "Fin de la lista."
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo renombrar: {e}"
            )

    # ----------------------------------------------------------------
    # Procesamiento de imagen
    # ----------------------------------------------------------------

    def _process_pil_image(
        self, img: Image.Image, mode: str, fill_name: str
    ) -> Image.Image:
        """Redimensiona una imagen a 800×800 según el método seleccionado."""
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert(
                "RGBA"
                if "transparency" in img.info or img.mode == "P"
                else "RGB"
            )

        target_size = (800, 800)
        if mode == "stretch":
            return img.resize(target_size, Image.Resampling.LANCZOS)
        elif mode == "crop":
            return ImageOps.fit(img, target_size, Image.Resampling.LANCZOS)
        else:
            img.thumbnail(target_size, Image.Resampling.LANCZOS)
            if fill_name == "Transparente" and not self.chk_jpg.isChecked():
                bg = Image.new("RGBA", target_size, (0, 0, 0, 0))
            else:
                color_map = {
                    "Negro": (0, 0, 0),
                    "Blanco": (255, 255, 255),
                    "Gris": (128, 128, 128),
                }
                bg_color = color_map.get(fill_name, (255, 255, 255))
                if img.mode == "RGBA":
                    bg = Image.new("RGBA", target_size, bg_color + (255,))
                else:
                    bg = Image.new("RGB", target_size, bg_color)

            x = (target_size[0] - img.width) // 2
            y = (target_size[1] - img.height) // 2
            bg.paste(img, (x, y), img if img.mode == "RGBA" else None)
            return bg

    def _process_single_image(
        self, img_path: str, mode: str, fill_name: str
    ) -> Image.Image:
        """Abre y procesa una imagen individual."""
        with Image.open(img_path) as img:
            return self._process_pil_image(img, mode, fill_name)

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
            self.chk_limit.isChecked()
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
        mode = "fit"
        if self.rb_crop.isChecked():
            mode = "crop"
        elif self.rb_stretch.isChecked():
            mode = "stretch"
        fill_name = self.cb_color.currentText()

        from PyQt6.QtWidgets import QApplication

        for idx, path in enumerate(self.image_paths):
            try:
                res_img = self._process_single_image(path, mode, fill_name)
                name_part, ext = os.path.splitext(os.path.basename(path))

                if self.chk_jpg.isChecked():
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

                if self.chk_del.isChecked() and os.path.exists(path):
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

        if self.chk_del.isChecked():
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
