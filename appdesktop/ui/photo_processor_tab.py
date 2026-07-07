"""
Pestaña de Procesador IA con remoción de fondo (Rembg).

Permite procesar fotos con remoción de fondo por IA, aplicar marca de agua
(logo central + sello esquina), ajustes digitales (brillo, contraste, nitidez),
y exportar imágenes optimizadas para web en formato 800×800 JPG.
"""

import io
import os
import shutil

from PIL import Image, ImageEnhance

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QCheckBox,
    QLineEdit,
    QGroupBox,
    QSlider,
    QProgressBar,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QRectF
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor

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
)


# ============================================================
# Utilidades (compartida con photo_editor_tab)
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
# Diálogo de ajustes de imagen
# ============================================================


class SettingsDialog(QDialog):
    """Diálogo para configurar ajustes de procesamiento IA."""

    def __init__(
        self,
        parent,
        brillo: float,
        contraste: float,
        nitidez: float,
        calidad: int,
        opacidad_logo: int,
        incluir_sello: bool,
        sin_fondo: bool,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ajustes de Mejoras Digitales")
        self.setMinimumWidth(320)

        layout = QFormLayout(self)

        self.sp_brillo = QDoubleSpinBox()
        self.sp_brillo.setRange(0.0, 3.0)
        self.sp_brillo.setSingleStep(0.1)
        self.sp_brillo.setValue(brillo)

        self.sp_contraste = QDoubleSpinBox()
        self.sp_contraste.setRange(0.0, 3.0)
        self.sp_contraste.setSingleStep(0.1)
        self.sp_contraste.setValue(contraste)

        self.sp_nitidez = QDoubleSpinBox()
        self.sp_nitidez.setRange(0.0, 3.0)
        self.sp_nitidez.setSingleStep(0.1)
        self.sp_nitidez.setValue(nitidez)

        self.sp_calidad = QSpinBox()
        self.sp_calidad.setRange(10, 100)
        self.sp_calidad.setValue(calidad)

        self.sp_opacidad = QSpinBox()
        self.sp_opacidad.setRange(0, 100)
        self.sp_opacidad.setValue(opacidad_logo)

        self.chk_sello = QCheckBox()
        self.chk_sello.setChecked(incluir_sello)

        self.chk_sin_fondo = QCheckBox()
        self.chk_sin_fondo.setChecked(sin_fondo)

        layout.addRow("Nivel de Brillo:", self.sp_brillo)
        layout.addRow("Nivel de Contraste:", self.sp_contraste)
        layout.addRow("Nivel de Nitidez:", self.sp_nitidez)
        layout.addRow("Calidad de Salida (JPEG):", self.sp_calidad)
        layout.addRow("Opacidad Marca de Agua (%):", self.sp_opacidad)
        layout.addRow("Incluir Sello:", self.chk_sello)
        layout.addRow("Procesar sin fondo (IA):", self.chk_sin_fondo)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)


# ============================================================
# Canvas del procesador
# ============================================================


class ProcessorCanvas(QLabel):
    """Canvas para la vista previa del procesador IA con soporte para logo/sello."""

    def __init__(self, parent_tab: "PhotoProcessorTab") -> None:
        super().__init__()
        self.parent_tab = parent_tab
        self.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.setScaledContents(False)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        if self.parent_tab.img_tk_editor is None:
            return

        lado = self.parent_tab.img_tk_editor.width()
        off_x = (self.width() - lado) // 2
        off_y = (self.height() - lado) // 2
        painter.drawPixmap(off_x, off_y, self.parent_tab.img_tk_editor)

        if self.parent_tab.objeto_seleccionado == "logo":
            self._dibujar_guias(
                painter,
                self.parent_tab.logo_props,
                Qt.GlobalColor.blue,
                off_x,
                off_y,
            )
        elif (
            self.parent_tab.objeto_seleccionado == "sello"
            and self.parent_tab.chk_sello.isChecked()
        ):
            self._dibujar_guias(
                painter,
                self.parent_tab.sello_props,
                Qt.GlobalColor.magenta,
                off_x,
                off_y,
            )

    def _dibujar_guias(
        self, painter: QPainter, props: dict, color, off_x: int, off_y: int
    ) -> None:
        """Dibuja las guías visuales de posición/tamaño sobre logo o sello."""
        ex = self.parent_tab.escala_x
        ey = self.parent_tab.escala_y
        cx = (props["x"] * ex) + off_x
        cy = (props["y"] * ey) + off_y
        rw = (props["w"] / 2) * ex
        rh = (props["h"] / 2) * ey
        x1, y1 = cx - rw, cy - rh
        w, h = rw * 2, rh * 2

        pen = QPen(color, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(QRectF(x1, y1, w, h))
        painter.setBrush(QColor(color))
        painter.setPen(Qt.GlobalColor.white)
        painter.drawRect(QRectF(x1 + w - 6, y1 + h - 6, 12, 12))

    def mousePressEvent(self, event) -> None:
        self.parent_tab.on_canvas_click(event)

    def mouseMoveEvent(self, event) -> None:
        self.parent_tab.on_canvas_drag(event)

    def mouseReleaseEvent(self, event) -> None:
        self.parent_tab.on_canvas_release(event)


# ============================================================
# Workers (hilos de procesamiento)
# ============================================================


class PreviewWorker(QThread):
    """Hilo para generar la vista previa con remoción de fondo."""

    finished = pyqtSignal(object, object, object)

    def __init__(
        self,
        ruta: str,
        ruta_logo: str,
        ruta_sello: str,
        solo_marcas: bool,
    ) -> None:
        super().__init__()
        self.ruta = ruta
        self.ruta_logo = ruta_logo
        self.ruta_sello = ruta_sello
        self.solo_marcas = solo_marcas

    def run(self) -> None:
        try:
            from rembg import remove, new_session

            try:
                session = new_session("birefnet-general-use")
            except Exception:
                session = new_session("isnet-general-use")

            img_fondo, img_logo, img_sello = None, None, None

            if self.solo_marcas:
                img = Image.open(self.ruta).convert("RGBA")
            else:
                with open(self.ruta, "rb") as i:
                    img = Image.open(
                        io.BytesIO(remove(i.read(), session=session))
                    ).convert("RGBA")
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
            img.thumbnail((740, 740), Image.Resampling.LANCZOS)
            img_fondo = img

            if os.path.exists(self.ruta_logo):
                with open(self.ruta_logo, "rb") as f:
                    l_img = Image.open(
                        io.BytesIO(remove(f.read(), session=session))
                    ).convert("RGBA")
                img_logo = l_img
            if os.path.exists(self.ruta_sello):
                img_sello = Image.open(self.ruta_sello).convert("RGBA")

            self.finished.emit(img_fondo, img_logo, img_sello)
        except Exception:
            self.finished.emit(None, None, None)


class BatchWorker(QThread):
    """Hilo para procesamiento por lotes con remoción de fondo."""

    progress = pyqtSignal(int, str)
    finished_batch = pyqtSignal()

    def __init__(self, pt: "PhotoProcessorTab", lista: list[str]) -> None:
        super().__init__()
        self.pt = pt
        self.lista = lista

    def run(self) -> None:
        c_in = self.pt.txt_entrada.text()
        c_out = self.pt.txt_salida.text()
        c_arch = self.pt.txt_archivo.text()
        os.makedirs(c_out, exist_ok=True)
        os.makedirs(c_arch, exist_ok=True)

        try:
            from rembg import remove, new_session

            try:
                session = new_session("birefnet-general-use")
            except Exception:
                session = new_session("isnet-general-use")
        except Exception:
            session = None

        for idx, nom in enumerate(self.lista, 1):
            try:
                self.progress.emit(
                    idx, f"Procesando ({idx}/{len(self.lista)}): {nom}"
                )
                ruta_foto = os.path.join(c_in, nom)

                if self.pt.chk_marcas.isChecked():
                    img = Image.open(ruta_foto).convert("RGBA")
                else:
                    from rembg import remove

                    with open(ruta_foto, "rb") as i:
                        img = Image.open(
                            io.BytesIO(remove(i.read(), session=session))
                        ).convert("RGBA")

                bbox = img.getbbox()
                if bbox:
                    img = img.crop(bbox)
                img.thumbnail((740, 740), Image.Resampling.LANCZOS)
                img = self.pt.aplicar_filtros_imagen(img)

                lienzo = Image.new("RGB", (800, 800), (255, 255, 255))
                lienzo.paste(
                    img,
                    ((800 - img.width) // 2, (800 - img.height) // 2),
                    mask=img,
                )

                if self.pt.img_logo_limpia:
                    l_res = self.pt.img_logo_limpia.resize(
                        (
                            int(self.pt.logo_props["w"]),
                            int(self.pt.logo_props["h"]),
                        ),
                        Image.Resampling.LANCZOS,
                    )
                    l_op = l_res.copy()
                    factor_alfa = self.pt.slider_opacidad.value() / 100.0
                    l_op.putalpha(
                        l_res.getchannel("A").point(
                            lambda p: int(p * factor_alfa)
                        )
                    )
                    lienzo.paste(
                        l_op,
                        (
                            int(
                                self.pt.logo_props["x"] - l_res.width // 2
                            ),
                            int(
                                self.pt.logo_props["y"] - l_res.height // 2
                            ),
                        ),
                        mask=l_op,
                    )

                if (
                    self.pt.chk_sello.isChecked()
                    and self.pt.img_sello_limpia
                ):
                    s_res = self.pt.img_sello_limpia.resize(
                        (
                            int(self.pt.sello_props["w"]),
                            int(self.pt.sello_props["h"]),
                        ),
                        Image.Resampling.LANCZOS,
                    )
                    lienzo.paste(
                        s_res,
                        (
                            int(
                                self.pt.sello_props["x"]
                                - s_res.width // 2
                            ),
                            int(
                                self.pt.sello_props["y"]
                                - s_res.height // 2
                            ),
                        ),
                        mask=s_res,
                    )

                out_path = os.path.join(
                    c_out, f"{os.path.splitext(nom)[0]}.jpg"
                )
                lienzo.save(
                    out_path,
                    "JPEG",
                    quality=self.pt.val_calidad_jpeg,
                    optimize=True,
                )
                shutil.move(ruta_foto, os.path.join(c_arch, nom))
            except Exception as e:
                print(f"Error en batch: {e}")
        self.finished_batch.emit()


# ============================================================
# Pestaña: Procesador IA
# ============================================================


class PhotoProcessorTab(QWidget):
    """
    Procesador de fotos con IA (Rembg) para:
    - Remoción automática de fondo
    - Marca de agua con logo central (opacidad configurable)
    - Sello de esquina
    - Ajustes de brillo, contraste y nitidez
    - Procesamiento individual con renombrado
    - Procesamiento por lotes con respaldo automático
    """

    def __init__(self) -> None:
        super().__init__()
        escritorio = os.path.join(os.path.expanduser("~"), "Desktop")
        self.ruta_logo_default = os.path.join(escritorio, "cimer_logo.png")
        self.ruta_sello_default = os.path.join(escritorio, "cimer_sello.png")

        # Ajustes de imagen
        self.val_brillo = 1.0
        self.val_contraste = 1.0
        self.val_nitidez = 1.0
        self.val_calidad_jpeg = 90

        # Propiedades de logo y sello
        self.logo_props = {"x": 400, "y": 400, "w": 500, "h": 180}
        self.sello_props = {"x": 700, "y": 700, "w": 130, "h": 130}
        self.escala_x = 1.0
        self.escala_y = 1.0

        # Estado interno
        self.img_tk_editor: QPixmap | None = None
        self.objeto_seleccionado: str | None = None
        self.modo_interaccion: str | None = None
        self.chk_variables: dict[str, QCheckBox] = {}
        self.foto_seleccionada_actual: str | None = None
        self.img_fondo_limpia: Image.Image | None = None
        self.img_logo_limpia: Image.Image | None = None
        self.img_sello_limpia: Image.Image | None = None
        self.preview_worker: PreviewWorker | None = None
        self.batch_worker: BatchWorker | None = None

        self.start_x = 0.0
        self.start_y = 0.0

        self._setup_ui()

    # ----------------------------------------------------------------
    # Construcción de UI
    # ----------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Construye la interfaz completa de la pestaña."""
        main_layout = QVBoxLayout(self)

        # --- Directorios ---
        group_dirs = QGroupBox("Configuración de Directorios")
        grid_dirs = QVBoxLayout()

        self.txt_entrada = self._crear_fila_dir(
            grid_dirs, "Origen (Fotos):", folder=True, callback=self._cargar_lista_imagenes
        )
        self.txt_salida = self._crear_fila_dir(
            grid_dirs, "Destino (Web):", folder=True
        )
        self.txt_archivo = self._crear_fila_dir(
            grid_dirs, "Respaldo:", folder=True
        )
        self.txt_logo = self._crear_fila_dir(
            grid_dirs,
            "Logo Central:",
            folder=False,
            default=self.ruta_logo_default,
            callback=self._recargar_logos,
        )
        self.txt_sello = self._crear_fila_dir(
            grid_dirs,
            "Sello Esquina:",
            folder=False,
            default=self.ruta_sello_default,
            callback=self._recargar_logos,
        )

        group_dirs.setLayout(grid_dirs)
        main_layout.addWidget(group_dirs)

        # --- Controles internos (no visibles directamente, usados por ajustes) ---
        self.chk_sello = QCheckBox()
        self.chk_sello.setChecked(True)
        self.chk_marcas = QCheckBox()
        self.slider_opacidad = QSlider()
        self.slider_opacidad.setRange(0, 100)
        self.slider_opacidad.setValue(20)

        # --- Splitter: lista de fotos + canvas ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_panel = QVBoxLayout(left_widget)
        left_panel.setContentsMargins(0, 0, 0, 0)

        btn_layout = QHBoxLayout()
        btn_todo = QPushButton("☑️ Todo")
        btn_todo.clicked.connect(lambda: self._marcar_todos(True))
        btn_nada = QPushButton("☐ Ninguno")
        btn_nada.clicked.connect(lambda: self._marcar_todos(False))

        self.btn_ajustes = QPushButton("⚙️ Ajustes de Imagen")
        self.btn_ajustes.clicked.connect(self._abrir_ajustes)

        self.btn_procesar = QPushButton("🚀 INICIAR PROCESAMIENTO WEB")
        self.btn_procesar.setStyleSheet(
            f"background-color: {COLOR_SUCCESS}; color: {COLOR_BG_PRIMARY}; font-weight: bold;"
        )
        self.btn_procesar.clicked.connect(self._iniciar_hilo_proceso)

        btn_layout.addWidget(btn_todo)
        btn_layout.addWidget(btn_nada)
        btn_layout.addWidget(self.btn_ajustes)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_procesar)
        left_panel.addLayout(btn_layout)

        self.list_widget_files = QListWidget()
        left_panel.addWidget(self.list_widget_files)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_panel = QVBoxLayout(right_widget)
        right_panel.setContentsMargins(0, 0, 0, 0)
        self.canvas_editor = ProcessorCanvas(self)
        self.canvas_editor.setStyleSheet(
            f"background-color: #11111b; border: 1px solid {COLOR_BORDER};"
        )
        self.canvas_editor.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        right_panel.addWidget(self.canvas_editor)
        splitter.addWidget(right_widget)

        splitter.setSizes([350, 600])
        main_layout.addWidget(splitter, stretch=1)

        # --- Panel de renombrado individual ---
        rename_panel = QHBoxLayout()
        rename_panel.addWidget(QLabel("Nuevo Nombre para Foto Actual:"))
        self.txt_nuevo_nombre_ia = QLineEdit()
        self.txt_nuevo_nombre_ia.returnPressed.connect(
            self._procesar_y_guardar_individual
        )
        rename_panel.addWidget(self.txt_nuevo_nombre_ia, stretch=4)

        self.btn_procesar_individual = QPushButton(
            "⚡ Procesar e Importar (Enter)"
        )
        self.btn_procesar_individual.setStyleSheet(
            f"background-color: {COLOR_SUCCESS}; color: {COLOR_BG_PRIMARY}; font-weight: bold;"
        )
        self.btn_procesar_individual.clicked.connect(
            self._procesar_y_guardar_individual
        )
        rename_panel.addWidget(self.btn_procesar_individual, stretch=2)
        main_layout.addLayout(rename_panel)

        # --- Footer: estado + progreso ---
        footer = QHBoxLayout()
        self.lbl_estado = QLabel("Estado: Listo.")
        self.progress_bar = QProgressBar()
        footer.addWidget(self.lbl_estado, stretch=1)
        footer.addWidget(self.progress_bar, stretch=2)
        main_layout.addLayout(footer)

    # ----------------------------------------------------------------
    # Helpers de UI
    # ----------------------------------------------------------------

    def _crear_fila_dir(
        self,
        layout,
        label: str,
        folder: bool = True,
        default: str = "",
        callback=None,
    ) -> QLineEdit:
        """Crea una fila de configuración de directorio/archivo."""
        row = QHBoxLayout()
        row.addWidget(QLabel(label), stretch=1)
        txt = QLineEdit(default)
        row.addWidget(txt, stretch=6)
        btn = QPushButton("Buscar...")

        def al_clickear():
            if folder:
                ruta = QFileDialog.getExistingDirectory(self, label)
            else:
                ruta, _ = QFileDialog.getOpenFileName(
                    self,
                    label,
                    "",
                    "Imágenes (*.png *.jpg *.jpeg *.webp)",
                )
            if ruta:
                txt.setText(ruta)
                if callback:
                    callback()

        btn.clicked.connect(al_clickear)
        row.addWidget(btn, stretch=1)
        layout.addLayout(row)
        return txt

    # ----------------------------------------------------------------
    # Ajustes de imagen
    # ----------------------------------------------------------------

    def _abrir_ajustes(self) -> None:
        """Abre el diálogo de ajustes de procesamiento."""
        dlg = SettingsDialog(
            self,
            self.val_brillo,
            self.val_contraste,
            self.val_nitidez,
            self.val_calidad_jpeg,
            self.slider_opacidad.value(),
            self.chk_sello.isChecked(),
            not self.chk_marcas.isChecked(),
        )
        if dlg.exec():
            self.val_brillo = dlg.sp_brillo.value()
            self.val_contraste = dlg.sp_contraste.value()
            self.val_nitidez = dlg.sp_nitidez.value()
            self.val_calidad_jpeg = dlg.sp_calidad.value()
            self.slider_opacidad.setValue(dlg.sp_opacidad.value())
            self.chk_sello.setChecked(dlg.chk_sello.isChecked())
            nuevo_chk_marcas = not dlg.chk_sin_fondo.isChecked()
            cambio_fondo = self.chk_marcas.isChecked() != nuevo_chk_marcas
            self.chk_marcas.setChecked(nuevo_chk_marcas)
            if cambio_fondo:
                self._actualizar_vista_previa_actual()
            else:
                self._renderizar_canvas()

    # ----------------------------------------------------------------
    # Lista de imágenes
    # ----------------------------------------------------------------

    def _recargar_logos(self) -> None:
        """Recarga las imágenes de logo y sello."""
        self.img_logo_limpia = None
        self.img_sello_limpia = None
        self._actualizar_vista_previa_actual()

    def _marcar_todos(self, estado: bool) -> None:
        """Marca o desmarca todos los checkboxes de la lista."""
        for cb in self.chk_variables.values():
            cb.setChecked(estado)

    def _cargar_lista_imagenes(self) -> None:
        """Carga la lista de imágenes desde la carpeta de entrada."""
        self.list_widget_files.clear()
        self.chk_variables.clear()
        c_entrada = self.txt_entrada.text()
        if not c_entrada or not os.path.exists(c_entrada):
            return
        archivos = [
            f
            for f in os.listdir(c_entrada)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ]
        for f in archivos:
            item = QListWidgetItem(self.list_widget_files)
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(5, 2, 5, 2)
            cb = QCheckBox((f[:20] + "..") if len(f) > 22 else f)
            cb.setChecked(True)
            self.chk_variables[f] = cb
            layout.addWidget(cb)
            btn_preview = QPushButton("👁️")
            btn_preview.clicked.connect(
                lambda _, a=f: self._seleccionar_para_preview(a)
            )
            layout.addWidget(btn_preview)
            widget.setLayout(layout)
            item.setSizeHint(widget.sizeHint())
            self.list_widget_files.setItemWidget(item, widget)

    def _seleccionar_para_preview(self, archivo: str) -> None:
        """Selecciona una foto para vista previa con procesamiento IA."""
        self.foto_seleccionada_actual = archivo
        self.img_fondo_limpia = None
        name_sin_ext, _ = os.path.splitext(archivo)
        self.txt_nuevo_nombre_ia.setText(name_sin_ext)
        self.txt_nuevo_nombre_ia.setFocus()
        self.txt_nuevo_nombre_ia.selectAll()
        self._actualizar_vista_previa_actual()

    # ----------------------------------------------------------------
    # Filtros y renderizado
    # ----------------------------------------------------------------

    def aplicar_filtros_imagen(self, img_pil: Image.Image) -> Image.Image:
        """Aplica ajustes de brillo, contraste y nitidez a la imagen."""
        if self.val_brillo != 1.0:
            img_pil = ImageEnhance.Brightness(img_pil).enhance(self.val_brillo)
        if self.val_contraste != 1.0:
            img_pil = ImageEnhance.Contrast(img_pil).enhance(
                self.val_contraste
            )
        if self.val_nitidez != 1.0:
            img_pil = ImageEnhance.Sharpness(img_pil).enhance(self.val_nitidez)
        return img_pil

    def _actualizar_vista_previa_actual(self) -> None:
        """Lanza el worker de vista previa para la foto seleccionada."""
        if not self.foto_seleccionada_actual or not self.txt_entrada.text():
            return
        self.lbl_estado.setText("Generando vista previa (Rembg)...")
        ruta = os.path.join(
            self.txt_entrada.text(), self.foto_seleccionada_actual
        )
        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_worker.terminate()
        self.preview_worker = PreviewWorker(
            ruta=ruta,
            ruta_logo=self.txt_logo.text(),
            ruta_sello=self.txt_sello.text(),
            solo_marcas=self.chk_marcas.isChecked(),
        )
        self.preview_worker.finished.connect(self._on_preview_finished)
        self.preview_worker.start()

    def _on_preview_finished(
        self, img_fondo, img_logo, img_sello
    ) -> None:
        """Slot: vista previa del worker finalizada."""
        if img_fondo:
            self.img_fondo_limpia = img_fondo
        if img_logo:
            logo_es_nuevo = self.img_logo_limpia is None
            self.img_logo_limpia = img_logo
            if logo_es_nuevo:
                target_w = 500
                aspect = img_logo.height / img_logo.width
                self.logo_props["w"] = target_w
                self.logo_props["h"] = int(target_w * aspect)
        if img_sello:
            sello_es_nuevo = self.img_sello_limpia is None
            self.img_sello_limpia = img_sello
            if sello_es_nuevo:
                target_h = 130
                aspect = img_sello.width / img_sello.height
                self.sello_props["w"] = int(target_h * aspect)
                self.sello_props["h"] = target_h
        self.lbl_estado.setText("Vista previa lista.")
        self._renderizar_canvas()

    def _renderizar_canvas(self) -> None:
        """Renderiza la composición final en el canvas."""
        if self.img_fondo_limpia is None:
            return
        fondo_filtrado = self.aplicar_filtros_imagen(
            self.img_fondo_limpia.copy()
        )
        lienzo_virtual = Image.new("RGBA", (800, 800), (255, 255, 255, 255))
        lienzo_virtual.paste(
            fondo_filtrado,
            (
                (800 - fondo_filtrado.width) // 2,
                (800 - fondo_filtrado.height) // 2,
            ),
            mask=fondo_filtrado,
        )

        if (
            self.img_logo_limpia
            and self.logo_props["w"] > 10
            and self.logo_props["h"] > 10
        ):
            l_res = self.img_logo_limpia.resize(
                (int(self.logo_props["w"]), int(self.logo_props["h"])),
                Image.Resampling.LANCZOS,
            )
            l_op = l_res.copy()
            factor_alfa = self.slider_opacidad.value() / 100.0
            l_op.putalpha(
                l_res.getchannel("A").point(
                    lambda p: int(p * factor_alfa)
                )
            )
            lienzo_virtual.paste(
                l_op,
                (
                    int(self.logo_props["x"] - l_res.width // 2),
                    int(self.logo_props["y"] - l_res.height // 2),
                ),
                mask=l_op,
            )

        if (
            self.chk_sello.isChecked()
            and self.img_sello_limpia
            and self.sello_props["w"] > 10
            and self.sello_props["h"] > 10
        ):
            s_res = self.img_sello_limpia.resize(
                (int(self.sello_props["w"]), int(self.sello_props["h"])),
                Image.Resampling.LANCZOS,
            )
            lienzo_virtual.paste(
                s_res,
                (
                    int(self.sello_props["x"] - s_res.width // 2),
                    int(self.sello_props["y"] - s_res.height // 2),
                ),
                mask=s_res,
            )

        cw = max(10, self.canvas_editor.width())
        ch = max(10, self.canvas_editor.height())
        lado_cuadrado = min(cw, ch)
        self.escala_x = lado_cuadrado / 800.0
        self.escala_y = lado_cuadrado / 800.0
        img_final = lienzo_virtual.resize(
            (lado_cuadrado, lado_cuadrado), Image.Resampling.LANCZOS
        ).convert("RGB")
        self.img_tk_editor = pil_to_pixmap(img_final)
        self.canvas_editor.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.img_fondo_limpia:
            self._renderizar_canvas()

    # ----------------------------------------------------------------
    # Interacción con canvas (mover/redimensionar logo y sello)
    # ----------------------------------------------------------------

    def _get_canvas_mapped_coords(self, event) -> tuple[float, float]:
        """Convierte coordenadas del canvas a coordenadas virtuales 800×800."""
        cw = self.canvas_editor.width()
        ch = self.canvas_editor.height()
        lado = min(cw, ch)
        off_x = (cw - lado) // 2
        off_y = (ch - lado) // 2
        return (
            (event.pos().x() - off_x) / self.escala_x,
            (event.pos().y() - off_y) / self.escala_y,
        )

    def on_canvas_click(self, event) -> None:
        """Maneja click en el canvas para seleccionar logo o sello."""
        vx, vy = self._get_canvas_mapped_coords(event)
        self.objeto_seleccionado = None
        self.modo_interaccion = None

        if self.chk_sello.isChecked():
            sx = self.sello_props["x"]
            sy = self.sello_props["y"]
            sw = self.sello_props["w"]
            sh = self.sello_props["h"]
            if abs(vx - (sx + sw / 2)) < 15 and abs(vy - (sy + sh / 2)) < 15:
                self.objeto_seleccionado = "sello"
                self.modo_interaccion = "redimensionar"
                self.start_x, self.start_y = vx, vy
                self.canvas_editor.update()
                return
            elif (
                (sx - sw / 2) <= vx <= (sx + sw / 2)
                and (sy - sh / 2) <= vy <= (sy + sh / 2)
            ):
                self.objeto_seleccionado = "sello"
                self.modo_interaccion = "mover"
                self.start_x, self.start_y = vx, vy
                self.canvas_editor.update()
                return

        lx = self.logo_props["x"]
        ly = self.logo_props["y"]
        lw = self.logo_props["w"]
        lh = self.logo_props["h"]
        if abs(vx - (lx + lw / 2)) < 15 and abs(vy - (ly + lh / 2)) < 15:
            self.objeto_seleccionado = "logo"
            self.modo_interaccion = "redimensionar"
        elif (
            (lx - lw / 2) <= vx <= (lx + lw / 2)
            and (ly - lh / 2) <= vy <= (ly + lh / 2)
        ):
            self.objeto_seleccionado = "logo"
            self.modo_interaccion = "mover"
        self.start_x, self.start_y = vx, vy
        self.canvas_editor.update()

    def on_canvas_drag(self, event) -> None:
        """Maneja arrastre en el canvas para mover/redimensionar."""
        if not self.objeto_seleccionado or not self.modo_interaccion:
            return
        vx, vy = self._get_canvas_mapped_coords(event)
        dx = vx - self.start_x
        dy = vy - self.start_y
        props = (
            self.logo_props
            if self.objeto_seleccionado == "logo"
            else self.sello_props
        )

        if self.modo_interaccion == "mover":
            props["x"] = max(0, min(800, props["x"] + dx))
            props["y"] = max(0, min(800, props["y"] + dy))
        elif self.modo_interaccion == "redimensionar":
            props["w"] = max(20, props["w"] + dx * 2)
            props["h"] = max(20, props["h"] + dy * 2)

        self.start_x, self.start_y = vx, vy
        self._renderizar_canvas()

    def on_canvas_release(self, event) -> None:
        """Maneja soltar botón en el canvas."""
        self.modo_interaccion = None

    # ----------------------------------------------------------------
    # Procesamiento por lotes
    # ----------------------------------------------------------------

    def _iniciar_hilo_proceso(self) -> None:
        """Inicia el procesamiento por lotes en un hilo separado."""
        sel = [f for f, cb in self.chk_variables.items() if cb.isChecked()]
        if not sel or not self.txt_entrada.text() or not self.txt_salida.text():
            return
        self.btn_procesar.setEnabled(False)
        self.progress_bar.setMaximum(len(sel))
        self.progress_bar.setValue(0)
        self.batch_worker = BatchWorker(self, sel)
        self.batch_worker.progress.connect(self._actualizar_progreso_batch)
        self.batch_worker.finished_batch.connect(self._finalizar_batch)
        self.batch_worker.start()

    def _actualizar_progreso_batch(self, valor: int, texto: str) -> None:
        """Slot: actualiza la barra de progreso durante el lote."""
        self.progress_bar.setValue(valor)
        self.lbl_estado.setText(texto)

    def _finalizar_batch(self) -> None:
        """Slot: el procesamiento por lotes ha finalizado."""
        self._cargar_lista_imagenes()
        self.btn_procesar.setEnabled(True)
        self.lbl_estado.setText("Estado: Lote finalizado.")
        QMessageBox.information(
            self, "Éxito", "¡Proceso IA Completado!"
        )

    # ----------------------------------------------------------------
    # Procesamiento individual
    # ----------------------------------------------------------------

    def _procesar_y_guardar_individual(self) -> None:
        """Procesa la foto actual y la guarda con el nuevo nombre."""
        if not self.foto_seleccionada_actual:
            return
        c_in = self.txt_entrada.text()
        c_out = self.txt_salida.text()
        c_arch = self.txt_archivo.text()
        if not c_in or not c_out or not c_arch:
            return

        nuevo_nombre_base = self.txt_nuevo_nombre_ia.text().strip()
        if not nuevo_nombre_base:
            return

        os.makedirs(c_out, exist_ok=True)
        os.makedirs(c_arch, exist_ok=True)

        self.lbl_estado.setText("Procesando y guardando individualmente...")
        QApplication.processEvents()

        try:
            if self.img_fondo_limpia is None:
                QMessageBox.warning(
                    self,
                    "Espera",
                    "La vista previa de IA se está cargando. Por favor, espera a que termine.",
                )
                return

            img = self.img_fondo_limpia.copy()
            img = self.aplicar_filtros_imagen(img)

            lienzo = Image.new("RGB", (800, 800), (255, 255, 255))
            lienzo.paste(
                img,
                ((800 - img.width) // 2, (800 - img.height) // 2),
                mask=img,
            )

            if self.img_logo_limpia:
                l_res = self.img_logo_limpia.resize(
                    (
                        int(self.logo_props["w"]),
                        int(self.logo_props["h"]),
                    ),
                    Image.Resampling.LANCZOS,
                )
                l_op = l_res.copy()
                factor_alfa = self.slider_opacidad.value() / 100.0
                l_op.putalpha(
                    l_res.getchannel("A").point(
                        lambda p: int(p * factor_alfa)
                    )
                )
                lienzo.paste(
                    l_op,
                    (
                        int(self.logo_props["x"] - l_res.width // 2),
                        int(self.logo_props["y"] - l_res.height // 2),
                    ),
                    mask=l_op,
                )

            if self.chk_sello.isChecked() and self.img_sello_limpia:
                s_res = self.img_sello_limpia.resize(
                    (
                        int(self.sello_props["w"]),
                        int(self.sello_props["h"]),
                    ),
                    Image.Resampling.LANCZOS,
                )
                lienzo.paste(
                    s_res,
                    (
                        int(self.sello_props["x"] - s_res.width // 2),
                        int(self.sello_props["y"] - s_res.height // 2),
                    ),
                    mask=s_res,
                )

            out_path = os.path.join(c_out, f"{nuevo_nombre_base}.jpg")
            lienzo.save(
                out_path,
                "JPEG",
                quality=self.val_calidad_jpeg,
                optimize=True,
            )

            ruta_foto = os.path.join(c_in, self.foto_seleccionada_actual)
            shutil.move(ruta_foto, os.path.join(c_arch, self.foto_seleccionada_actual))

            self.lbl_estado.setText(
                f"Guardado y respaldado: {nuevo_nombre_base}.jpg"
            )

            self._cargar_lista_imagenes()
            self.txt_nuevo_nombre_ia.clear()
            self.foto_seleccionada_actual = None
            self.img_fondo_limpia = None
            self.img_tk_editor = None
            self.canvas_editor.clear()

            # Seleccionar primer ítem disponible
            files = list(self.chk_variables.keys())
            if files:
                self._seleccionar_para_preview(files[0])

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo guardar la imagen: {e}"
            )
