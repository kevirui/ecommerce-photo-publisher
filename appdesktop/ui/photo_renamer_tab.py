"""
Pestaña de Renombrador de Fotos.

Permite cargar imágenes desde archivos o carpetas, previsualizarlas,
y renombrarlas individualmente o en modo secuencial.
"""

import os
from PIL import Image

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
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QFormLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QPixmap,
    QImage,
    QKeySequence,
    QShortcut,
)

from ui.styles import (
    COLOR_SUCCESS,
    COLOR_BG_PRIMARY,
    COLOR_BORDER,
    COLOR_BTN_DANGER_BG,
    COLOR_BTN_DANGER_TEXT,
    COLOR_WARNING,
)


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


class PhotoRenamerTab(QWidget):
    """
    Renombrador de fotos individual y secuencial.
    """

    def __init__(self) -> None:
        super().__init__()
        self.carpeta_actual = ""
        self.image_paths: list[str] = []
        self.indice_actual = -1
        self.img_pil_actual: Image.Image | None = None

        self._setup_ui()
        self._bind_shortcuts()

    def _setup_ui(self) -> None:
        """Construye la interfaz de la pestaña renombradora."""
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

        # --- Splitter: árbol de archivos + renombrador/vista previa ---
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

        # Panel derecho: visualizador y renombrador
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Barra de herramientas para eliminación
        controles_layout = QHBoxLayout()
        self.btn_eliminar = QPushButton("Eliminar Foto (Supr)")
        self.btn_eliminar.setStyleSheet(
            f"background-color: {COLOR_BTN_DANGER_BG}; color: {COLOR_BTN_DANGER_TEXT}; font-weight: bold;"
        )
        self.btn_eliminar.clicked.connect(self._eliminar_foto)
        controles_layout.addStretch()
        controles_layout.addWidget(self.btn_eliminar)
        right_layout.addLayout(controles_layout)

        # Canvas de visualización simple
        self.canvas_imagen = QLabel()
        self.canvas_imagen.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

        # --- Panel inferior: renombrado ---
        bottom_config_layout = QHBoxLayout()

        # Grupo de renombrado
        group_rename = QGroupBox("Opciones de Renombrado")
        rename_form = QFormLayout(group_rename)
        self.chk_secuencial = QCheckBox("Modo secuencial (auto-completar nombre sin sufijo '-N')")
        self.chk_secuencial.setToolTip("Al seleccionar una foto con sufijo como '-1' o '-2', sugiere el código base sin el sufijo.")
        self.txt_nuevo_nombre = QLineEdit()
        self.txt_nuevo_nombre.returnPressed.connect(self._renombrar_foto)
        self.btn_renombrar = QPushButton("Renombrar (Enter)")
        self.btn_renombrar.setStyleSheet(
            f"background-color: {COLOR_SUCCESS}; color: {COLOR_BG_PRIMARY}; font-weight: bold;"
        )
        self.btn_renombrar.clicked.connect(self._renombrar_foto)

        rename_form.addRow("Nuevo nombre:", self.txt_nuevo_nombre)
        rename_form.addRow("", self.chk_secuencial)
        rename_form.addRow("", self.btn_renombrar)
        bottom_config_layout.addWidget(group_rename, stretch=1)

        main_layout.addLayout(bottom_config_layout)

        self._habilitar_controles(False)

    def _bind_shortcuts(self) -> None:
        """Configura atajos de teclado."""
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self._navegar_lista(1))
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self._navegar_lista(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._eliminar_foto)

    def _habilitar_controles(self, estado: bool) -> None:
        """Habilita o deshabilita controles."""
        widgets = [
            self.btn_eliminar,
            self.btn_renombrar,
            self.txt_nuevo_nombre,
            self.chk_secuencial,
        ]
        for w in widgets:
            w.setEnabled(estado)

    def _navegar_lista(self, direccion: int) -> None:
        """Navega a la foto anterior o siguiente en la lista."""
        if not self.image_paths or self.indice_actual == -1:
            return
        nuevo_idx = self.indice_actual + direccion
        if 0 <= nuevo_idx < len(self.image_paths):
            item = self.tree.topLevelItem(nuevo_idx)
            self.tree.setCurrentItem(item)

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
        """Agrega imágenes a la lista."""
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

        self._cargar_y_mostrar_imagen(ruta_completa)
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
            try:
                # Hacer una copia para visualización
                img_copy = self.img_pil_actual.copy()
                if img_copy.mode == "RGBA":
                    fondo_blanco = Image.new("RGB", img_copy.size, (255, 255, 255))
                    fondo_blanco.paste(img_copy, mask=img_copy.split()[3])
                    img_copy = fondo_blanco
                elif img_copy.mode != "RGB":
                    img_copy = img_copy.convert("RGB")

                ancho_max = max(100, self.canvas_imagen.width())
                alto_max = max(100, self.canvas_imagen.height())
                img_copy.thumbnail((ancho_max, alto_max))

                qpix = pil_to_pixmap(img_copy)
                self.canvas_imagen.setPixmap(qpix)
            except Exception:
                self.canvas_imagen.setText("Error al renderizar preview")

    def resizeEvent(self, event) -> None:
        """Actualizar el preview si cambia el tamaño de la ventana."""
        super().resizeEvent(event)
        if self.indice_actual != -1 and self.image_paths:
            self._cargar_y_mostrar_imagen()

    def _eliminar_foto(self) -> None:
        """Elimina el archivo físico de la foto y lo remueve de la lista."""
        if self.indice_actual == -1 or not self.image_paths:
            return
        ruta = self.image_paths[self.indice_actual]
        nombre = os.path.basename(ruta)

        res = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Seguro que desea ELIMINAR permanentemente la foto?\n{nombre}\n\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            try:
                if self.img_pil_actual:
                    self.img_pil_actual.close()
                    self.img_pil_actual = None
                if os.path.exists(ruta):
                    os.remove(ruta)

                self.image_paths.pop(self.indice_actual)
                self.tree.takeTopLevelItem(self.indice_actual)

                self.lbl_contador.setText(f"Fotos encontradas: {len(self.image_paths)}")

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

    def _renombrar_foto(self) -> None:
        """Renombra la foto actual en el disco y avanza a la siguiente."""
        if self.indice_actual == -1 or not self.image_paths:
            return
        ruta_original = self.image_paths[self.indice_actual]
        nombre_original = os.path.basename(ruta_original)
        dir_original = os.path.dirname(ruta_original)

        nuevo_nombre_base = self.txt_nuevo_nombre.text().strip()
        if not nuevo_nombre_base:
            return
        _, ext = os.path.splitext(nombre_original)

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
            # Cerrar el archivo por si está abierto
            if self.img_pil_actual:
                self.img_pil_actual.close()
                self.img_pil_actual = None

            # Cambiar nombre en disco
            os.rename(ruta_original, ruta_nueva)

            self.image_paths[self.indice_actual] = ruta_nueva
            if self.tree.currentItem():
                self.tree.currentItem().setText(0, nuevo_nombre_completo)

            proximo_indice = self.indice_actual + 1
            if proximo_indice < len(self.image_paths):
                item = self.tree.topLevelItem(proximo_indice)
                self.tree.setCurrentItem(item)
            else:
                QMessageBox.information(
                    self, "¡Terminado!", "Fin de la lista de renombrado."
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo renombrar: {e}"
            )
