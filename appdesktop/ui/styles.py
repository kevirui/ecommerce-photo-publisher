"""
Hoja de estilos QSS centralizada para la aplicación Publicador Ecommerce.

Define una paleta de colores moderna con tema oscuro y acentos azul/cyan,
estilos para todos los widgets de PyQt6 utilizados en la aplicación,
y colores semánticos para los estados de publicación.
"""

# ============================================================
# Colores de la paleta
# ============================================================

# Fondo principal
COLOR_BG_PRIMARY = "#1e1e2e"
COLOR_BG_SECONDARY = "#2b2b3d"
COLOR_BG_TERTIARY = "#363650"
COLOR_BG_INPUT = "#2b2b3d"

# Texto
COLOR_TEXT_PRIMARY = "#e0e0e0"
COLOR_TEXT_SECONDARY = "#a0a0b0"
COLOR_TEXT_MUTED = "#6c6c80"

# Acentos
COLOR_ACCENT = "#4fc3f7"
COLOR_ACCENT_HOVER = "#81d4fa"
COLOR_ACCENT_PRESSED = "#0288d1"

# Bordes
COLOR_BORDER = "#3d3d5c"
COLOR_BORDER_FOCUS = "#4fc3f7"

# Estados
COLOR_SUCCESS = "#66bb6a"
COLOR_SUCCESS_BG = "#1b3a1b"
COLOR_ERROR = "#ef5350"
COLOR_ERROR_BG = "#3a1b1b"
COLOR_WARNING = "#ffa726"
COLOR_WARNING_BG = "#3a2e1b"
COLOR_INFO = "#42a5f5"

# Botones
COLOR_BTN_PRIMARY_BG = "#4fc3f7"
COLOR_BTN_PRIMARY_TEXT = "#1e1e2e"
COLOR_BTN_SECONDARY_BG = "#363650"
COLOR_BTN_DANGER_BG = "#ef5350"
COLOR_BTN_DANGER_TEXT = "#ffffff"

# Barra de progreso
COLOR_PROGRESS_BG = "#2b2b3d"
COLOR_PROGRESS_CHUNK = "#4fc3f7"

# Scrollbar
COLOR_SCROLLBAR_BG = "#1e1e2e"
COLOR_SCROLLBAR_HANDLE = "#4a4a6a"

# Simulación
COLOR_SIMULATION_BG = "#2e1e3e"
COLOR_SIMULATION_BORDER = "#9c27b0"


def get_status_color(status_value: str) -> str:
    """
    Devuelve el color hexadecimal correspondiente a un estado de artículo.

    Args:
        status_value: Valor del estado ('Correcto', 'Error', 'Pendiente', etc.).

    Returns:
        Color hexadecimal como string.
    """
    status_colors = {
        "Correcto": COLOR_SUCCESS,
        "Error": COLOR_ERROR,
        "Pendiente": COLOR_WARNING,
        "En proceso": COLOR_INFO,
        "Omitido": COLOR_TEXT_MUTED,
    }
    return status_colors.get(status_value, COLOR_TEXT_PRIMARY)


def get_status_bg_color(status_value: str) -> str:
    """
    Devuelve el color de fondo correspondiente a un estado de artículo.

    Args:
        status_value: Valor del estado.

    Returns:
        Color hexadecimal de fondo.
    """
    bg_colors = {
        "Correcto": COLOR_SUCCESS_BG,
        "Error": COLOR_ERROR_BG,
        "Pendiente": COLOR_WARNING_BG,
        "En proceso": COLOR_BG_TERTIARY,
        "Omitido": COLOR_BG_SECONDARY,
    }
    return bg_colors.get(status_value, COLOR_BG_SECONDARY)


# ============================================================
# Hoja de estilos QSS completa
# ============================================================

APP_STYLESHEET = f"""
/* ---- Ventana principal ---- */
QMainWindow {{
    background-color: {COLOR_BG_PRIMARY};
    color: {COLOR_TEXT_PRIMARY};
}}

QWidget {{
    background-color: {COLOR_BG_PRIMARY};
    color: {COLOR_TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
    font-size: 13px;
}}

/* ---- Etiquetas ---- */
QLabel {{
    color: {COLOR_TEXT_PRIMARY};
    background-color: transparent;
    padding: 2px;
}}

QLabel[heading="true"] {{
    font-size: 22px;
    font-weight: bold;
    color: {COLOR_ACCENT};
    padding: 8px 0px;
}}

QLabel[subheading="true"] {{
    font-size: 14px;
    color: {COLOR_TEXT_SECONDARY};
    padding: 4px 0px;
}}

QLabel[status="connected"] {{
    color: {COLOR_SUCCESS};
    font-weight: bold;
}}

QLabel[status="disconnected"] {{
    color: {COLOR_ERROR};
    font-weight: bold;
}}

/* ---- Campos de texto ---- */
QLineEdit {{
    background-color: {COLOR_BG_INPUT};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {COLOR_ACCENT};
    selection-color: {COLOR_BG_PRIMARY};
}}

QLineEdit:focus {{
    border-color: {COLOR_BORDER_FOCUS};
}}

QLineEdit:disabled {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_TEXT_MUTED};
}}

/* ---- Botones ---- */
QPushButton {{
    background-color: {COLOR_BTN_SECONDARY_BG};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 500;
    min-height: 18px;
}}

QPushButton:hover {{
    background-color: {COLOR_BG_TERTIARY};
    border-color: {COLOR_ACCENT};
    color: {COLOR_ACCENT};
}}

QPushButton:pressed {{
    background-color: {COLOR_ACCENT_PRESSED};
    color: white;
}}

QPushButton:disabled {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_TEXT_MUTED};
    border-color: {COLOR_BG_TERTIARY};
}}

QPushButton[primary="true"] {{
    background-color: {COLOR_BTN_PRIMARY_BG};
    color: {COLOR_BTN_PRIMARY_TEXT};
    border: none;
    font-weight: bold;
}}

QPushButton[primary="true"]:hover {{
    background-color: {COLOR_ACCENT_HOVER};
    color: {COLOR_BTN_PRIMARY_TEXT};
}}

QPushButton[primary="true"]:pressed {{
    background-color: {COLOR_ACCENT_PRESSED};
    color: white;
}}

QPushButton[primary="true"]:disabled {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_TEXT_MUTED};
}}

QPushButton[danger="true"] {{
    background-color: {COLOR_BTN_DANGER_BG};
    color: {COLOR_BTN_DANGER_TEXT};
    border: none;
    font-weight: bold;
}}

QPushButton[danger="true"]:hover {{
    background-color: #f44336;
}}

QPushButton[danger="true"]:pressed {{
    background-color: #c62828;
}}

/* ---- Tabla ---- */
QTableWidget {{
    background-color: {COLOR_BG_SECONDARY};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    gridline-color: {COLOR_BORDER};
    selection-background-color: {COLOR_BG_TERTIARY};
    selection-color: {COLOR_ACCENT};
    font-size: 12px;
}}

QTableWidget::item {{
    padding: 6px 10px;
    border-bottom: 1px solid {COLOR_BORDER};
}}

QTableWidget::item:selected {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_ACCENT};
}}

QHeaderView::section {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_ACCENT};
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid {COLOR_ACCENT};
    font-weight: bold;
    font-size: 12px;
}}

QHeaderView::section:hover {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_ACCENT_HOVER};
}}

/* ---- Barra de progreso ---- */
QProgressBar {{
    background-color: {COLOR_PROGRESS_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    text-align: center;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 12px;
    font-weight: bold;
    min-height: 22px;
}}

QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLOR_ACCENT_PRESSED},
        stop:1 {COLOR_ACCENT}
    );
    border-radius: 7px;
}}

/* ---- Panel de log ---- */
QTextEdit {{
    background-color: {COLOR_BG_SECONDARY};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 8px;
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    selection-background-color: {COLOR_ACCENT};
    selection-color: {COLOR_BG_PRIMARY};
}}

QTextEdit[readOnly="true"] {{
    background-color: {COLOR_BG_SECONDARY};
}}

/* ---- GroupBox ---- */
QGroupBox {{
    background-color: {COLOR_BG_SECONDARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    color: {COLOR_ACCENT};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    background-color: {COLOR_BG_SECONDARY};
    border-radius: 4px;
    color: {COLOR_ACCENT};
}}

/* ---- ComboBox ---- */
QComboBox {{
    background-color: {COLOR_BG_INPUT};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    min-width: 100px;
    font-size: 13px;
}}

QComboBox:hover {{
    border-color: {COLOR_ACCENT};
}}

QComboBox:focus {{
    border-color: {COLOR_BORDER_FOCUS};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_BG_SECONDARY};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: {COLOR_BG_TERTIARY};
    selection-color: {COLOR_ACCENT};
    padding: 4px;
}}

/* ---- CheckBox ---- */
QCheckBox {{
    color: {COLOR_TEXT_PRIMARY};
    spacing: 8px;
    background-color: transparent;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {COLOR_BORDER};
    border-radius: 4px;
    background-color: {COLOR_BG_INPUT};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
}}

QCheckBox::indicator:hover {{
    border-color: {COLOR_ACCENT};
}}

/* ---- RadioButton ---- */
QRadioButton {{
    color: {COLOR_TEXT_PRIMARY};
    spacing: 8px;
    background-color: transparent;
    font-size: 13px;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {COLOR_BORDER};
    border-radius: 9px;
    background-color: {COLOR_BG_INPUT};
}}

QRadioButton::indicator:checked {{
    background-color: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
}}

QRadioButton::indicator:hover {{
    border-color: {COLOR_ACCENT};
}}

/* ---- TabWidget ---- */
QTabWidget::pane {{
    background-color: {COLOR_BG_SECONDARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 0px 0px 8px 8px;
    padding: 12px;
}}

QTabBar::tab {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_TEXT_SECONDARY};
    padding: 10px 20px;
    border: 1px solid {COLOR_BORDER};
    border-bottom: none;
    border-radius: 6px 6px 0px 0px;
    margin-right: 2px;
    font-size: 13px;
}}

QTabBar::tab:selected {{
    background-color: {COLOR_BG_SECONDARY};
    color: {COLOR_ACCENT};
    border-bottom: 2px solid {COLOR_ACCENT};
}}

QTabBar::tab:hover:!selected {{
    background-color: {COLOR_BG_SECONDARY};
    color: {COLOR_TEXT_PRIMARY};
}}

/* ---- SpinBox ---- */
QSpinBox {{
    background-color: {COLOR_BG_INPUT};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}}

QSpinBox:focus {{
    border-color: {COLOR_BORDER_FOCUS};
}}

/* ---- ScrollBar ---- */
QScrollBar:vertical {{
    background-color: {COLOR_SCROLLBAR_BG};
    width: 10px;
    border-radius: 5px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLOR_SCROLLBAR_HANDLE};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLOR_ACCENT};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {COLOR_SCROLLBAR_BG};
    height: 10px;
    border-radius: 5px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLOR_SCROLLBAR_HANDLE};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLOR_ACCENT};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ---- Tooltip ---- */
QToolTip {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 6px;
    font-size: 12px;
}}

/* ---- Dialog ---- */
QDialog {{
    background-color: {COLOR_BG_PRIMARY};
    color: {COLOR_TEXT_PRIMARY};
}}

/* ---- MessageBox ---- */
QMessageBox {{
    background-color: {COLOR_BG_PRIMARY};
    color: {COLOR_TEXT_PRIMARY};
}}

QMessageBox QLabel {{
    color: {COLOR_TEXT_PRIMARY};
}}

/* ---- Separador ---- */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {{
    color: {COLOR_BORDER};
    max-height: 1px;
}}

/* ---- TreeWidget (Editor de Fotos) ---- */
QTreeWidget {{
    background-color: {COLOR_BG_SECONDARY};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    font-size: 12px;
}}

QTreeWidget::item {{
    padding: 4px 8px;
    border-bottom: 1px solid {COLOR_BORDER};
}}

QTreeWidget::item:selected {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_ACCENT};
}}

QTreeWidget QHeaderView::section {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_ACCENT};
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid {COLOR_ACCENT};
    font-weight: bold;
    font-size: 12px;
}}

/* ---- ListWidget (Procesador IA) ---- */
QListWidget {{
    background-color: {COLOR_BG_SECONDARY};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    font-size: 12px;
}}

QListWidget::item {{
    padding: 2px 4px;
    border-bottom: 1px solid {COLOR_BORDER};
}}

QListWidget::item:selected {{
    background-color: {COLOR_BG_TERTIARY};
    color: {COLOR_ACCENT};
}}

/* ---- Slider ---- */
QSlider::groove:horizontal {{
    border: 1px solid {COLOR_BORDER};
    height: 6px;
    background: {COLOR_BG_SECONDARY};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {COLOR_ACCENT};
    border: none;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: {COLOR_ACCENT_HOVER};
}}

/* ---- DoubleSpinBox ---- */
QDoubleSpinBox {{
    background-color: {COLOR_BG_INPUT};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}}

QDoubleSpinBox:focus {{
    border-color: {COLOR_BORDER_FOCUS};
}}

/* ---- FormLayout labels ---- */
QFormLayout QLabel {{
    color: {COLOR_TEXT_PRIMARY};
    background-color: transparent;
}}
"""

# ============================================================
# Estilos específicos para modo simulación
# ============================================================

SIMULATION_FRAME_STYLE = f"""
    QFrame#simulation_frame {{
        background-color: {COLOR_SIMULATION_BG};
        border: 2px dashed {COLOR_SIMULATION_BORDER};
        border-radius: 8px;
        padding: 8px;
    }}
"""

# ============================================================
# Estilos para indicadores de conexión
# ============================================================

INDICATOR_CONNECTED = f"""
    color: {COLOR_SUCCESS};
    font-weight: bold;
    font-size: 13px;
"""

INDICATOR_DISCONNECTED = f"""
    color: {COLOR_ERROR};
    font-weight: bold;
    font-size: 13px;
"""
