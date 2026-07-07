"""
Widget embebido de progreso detallado para la publicación.

Muestra información en tiempo real: artículo actual, porcentaje
completado, tiempo transcurrido, tiempo estimado restante, y
contadores de artículos exitosos, fallidos y pendientes.
"""

from __future__ import annotations

import time
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ui.styles import (
    COLOR_SUCCESS,
    COLOR_ERROR,
    COLOR_WARNING,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class ProgressWidget(QWidget):
    """
    Widget embebido que muestra el progreso detallado de la publicación.

    Incluye:
    - Barra de progreso con porcentaje.
    - Label con el artículo en proceso actual.
    - Tiempo transcurrido y estimado restante.
    - Contadores: exitosos / fallidos / pendientes.

    Example:
        >>> progress = ProgressWidget()
        >>> progress.set_total(100)
        >>> progress.update_progress(25, "R123")
        >>> progress.increment_success()
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Inicializa el widget de progreso.

        Args:
            parent: Widget padre.
        """
        super().__init__(parent)
        self._total = 0
        self._current = 0
        self._start_time: Optional[float] = None
        self._success_count = 0
        self._error_count = 0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construye la interfaz del widget de progreso."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(6)

        # Fila superior: artículo actual + tiempo
        top_row = QHBoxLayout()

        self._lbl_current_article = QLabel("")
        self._lbl_current_article.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: bold;"
        )
        top_row.addWidget(self._lbl_current_article)

        top_row.addStretch()

        self._lbl_time = QLabel("")
        self._lbl_time.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;"
        )
        top_row.addWidget(self._lbl_time)

        layout.addLayout(top_row)

        # Barra de progreso
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%v%")
        self._progress_bar.setFixedHeight(24)
        layout.addWidget(self._progress_bar)

        # Fila inferior: contadores
        bottom_row = QHBoxLayout()

        self._lbl_success = QLabel("✓ 0")
        self._lbl_success.setStyleSheet(
            f"color: {COLOR_SUCCESS}; font-size: 12px; font-weight: bold;"
        )
        bottom_row.addWidget(self._lbl_success)

        separator1 = QLabel("  │  ")
        separator1.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        bottom_row.addWidget(separator1)

        self._lbl_errors = QLabel("✗ 0")
        self._lbl_errors.setStyleSheet(
            f"color: {COLOR_ERROR}; font-size: 12px; font-weight: bold;"
        )
        bottom_row.addWidget(self._lbl_errors)

        separator2 = QLabel("  │  ")
        separator2.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        bottom_row.addWidget(separator2)

        self._lbl_pending = QLabel("◌ 0")
        self._lbl_pending.setStyleSheet(
            f"color: {COLOR_WARNING}; font-size: 12px; font-weight: bold;"
        )
        bottom_row.addWidget(self._lbl_pending)

        bottom_row.addStretch()

        self._lbl_progress_text = QLabel("")
        self._lbl_progress_text.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;"
        )
        bottom_row.addWidget(self._lbl_progress_text)

        layout.addLayout(bottom_row)

    # ================================================================
    # API pública
    # ================================================================

    def set_total(self, total: int) -> None:
        """
        Establece el total de artículos a procesar y reinicia contadores.

        Args:
            total: Cantidad total de artículos.
        """
        self._total = total
        self._current = 0
        self._success_count = 0
        self._error_count = 0
        self._start_time = time.time()

        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._update_counters()
        self._lbl_current_article.setText("Preparando publicación...")
        self._lbl_time.setText("")
        self._lbl_progress_text.setText(f"0 / {total}")

    def update_progress(self, current: int, article_code: str = "") -> None:
        """
        Actualiza el progreso actual.

        Args:
            current: Número de artículo actual (1-based).
            article_code: Código del artículo en proceso.
        """
        self._current = current

        # Calcular porcentaje
        if self._total > 0:
            percentage = int((current / self._total) * 100)
        else:
            percentage = 0

        self._progress_bar.setValue(percentage)
        self._lbl_progress_text.setText(f"{current} / {self._total}")

        if article_code:
            self._lbl_current_article.setText(
                f"Procesando: {article_code}"
            )

        # Calcular tiempos
        self._update_time()
        self._update_counters()

    def increment_success(self) -> None:
        """Incrementa el contador de artículos exitosos."""
        self._success_count += 1
        self._update_counters()

    def increment_error(self) -> None:
        """Incrementa el contador de artículos con error."""
        self._error_count += 1
        self._update_counters()

    def set_completed(self, successful: int, failed: int) -> None:
        """
        Marca la publicación como completada.

        Args:
            successful: Total de artículos exitosos.
            failed: Total de artículos fallidos.
        """
        self._success_count = successful
        self._error_count = failed
        self._progress_bar.setValue(100)
        self._lbl_current_article.setText("Publicación completada")
        self._update_counters()
        self._update_time()

    def set_cancelled(self) -> None:
        """Marca la publicación como cancelada."""
        self._lbl_current_article.setText("Publicación cancelada")
        self._lbl_current_article.setStyleSheet(
            f"color: {COLOR_WARNING}; font-size: 12px; font-weight: bold;"
        )

    def reset(self) -> None:
        """Reinicia el widget a su estado inicial."""
        self._total = 0
        self._current = 0
        self._success_count = 0
        self._error_count = 0
        self._start_time = None

        self._progress_bar.setValue(0)
        self._lbl_current_article.setText("")
        self._lbl_time.setText("")
        self._lbl_progress_text.setText("")
        self._lbl_success.setText("✓ 0")
        self._lbl_errors.setText("✗ 0")
        self._lbl_pending.setText("◌ 0")

    # ================================================================
    # Actualización interna
    # ================================================================

    def _update_counters(self) -> None:
        """Actualiza los labels de contadores."""
        self._lbl_success.setText(f"✓ {self._success_count}")
        self._lbl_errors.setText(f"✗ {self._error_count}")

        pending = max(
            0,
            self._total - self._success_count - self._error_count
        )
        self._lbl_pending.setText(f"◌ {pending}")

    def _update_time(self) -> None:
        """Actualiza el label de tiempo transcurrido y estimado."""
        if self._start_time is None:
            return

        elapsed = time.time() - self._start_time
        elapsed_str = self._format_time(elapsed)

        if self._current > 0 and self._current < self._total:
            # Estimar tiempo restante
            avg_per_article = elapsed / self._current
            remaining = avg_per_article * (self._total - self._current)
            remaining_str = self._format_time(remaining)
            self._lbl_time.setText(
                f"⏱ {elapsed_str}  │  ~{remaining_str} restante"
            )
        else:
            self._lbl_time.setText(f"⏱ {elapsed_str}")

    @staticmethod
    def _format_time(seconds: float) -> str:
        """
        Formatea segundos como texto legible.

        Args:
            seconds: Cantidad de segundos.

        Returns:
            Cadena formateada (ej: '2m 30s', '45s').
        """
        if seconds < 60:
            return f"{seconds:.0f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        if minutes < 60:
            return f"{minutes}m {secs}s"
        hours = int(minutes // 60)
        mins = minutes % 60
        return f"{hours}h {mins}m"
