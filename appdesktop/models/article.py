"""
Modelo de datos para artículos del ecommerce.

Define la dataclass Article que representa un artículo con sus imágenes,
estado de publicación, tiempos y errores. También incluye los enums
ArticleStatus y FtpConflictPolicy utilizados en toda la aplicación.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


class ArticleStatus(enum.Enum):
    """Estado de publicación de un artículo."""

    PENDING = "Pendiente"
    IN_PROGRESS = "En proceso"
    SUCCESS = "Correcto"
    ERROR = "Error"
    SKIPPED = "Omitido"

    def __str__(self) -> str:
        return self.value


class FtpConflictPolicy(enum.Enum):
    """Política de resolución cuando una imagen ya existe en el FTP."""

    OVERWRITE = "Sobrescribir"
    SKIP = "Omitir"
    ASK = "Preguntar siempre"

    def __str__(self) -> str:
        return self.value


@dataclass
class Article:
    """
    Representa un artículo del ecommerce con sus imágenes asociadas.

    Attributes:
        code: Código único del artículo (ej: 'R123').
        main_image: Ruta local a la imagen principal (ej: R123.jpg).
        additional_images: Lista ordenada de rutas a imágenes adicionales.
        description: Descripción del artículo (del Excel o vacía).
        status: Estado actual de publicación.
        error_message: Mensaje de error si la publicación falló.
        start_time: Momento en que inició el procesamiento.
        end_time: Momento en que finalizó el procesamiento.
    """

    code: str
    main_image: Optional[Path] = None
    additional_images: list[Path] = field(default_factory=list)
    description: str = ""
    status: ArticleStatus = ArticleStatus.PENDING
    error_message: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def image_count(self) -> int:
        """Cantidad total de imágenes (principal + adicionales)."""
        count = len(self.additional_images)
        if self.main_image is not None:
            count += 1
        return count

    @property
    def elapsed_time(self) -> float:
        """
        Tiempo transcurrido en segundos desde el inicio del procesamiento.

        Returns:
            Segundos transcurridos. 0.0 si no se ha iniciado.
        """
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time is not None else datetime.now()
        delta = end - self.start_time
        return delta.total_seconds()

    @property
    def elapsed_time_formatted(self) -> str:
        """Tiempo transcurrido formateado como 'Xm Ys' o 'Xs'."""
        seconds = self.elapsed_time
        if seconds == 0.0:
            return ""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.0f}s"

    @property
    def main_image_name(self) -> str:
        """Nombre del archivo de la imagen principal, o cadena vacía."""
        if self.main_image is not None:
            return self.main_image.name
        return ""

    @property
    def all_images(self) -> list[Path]:
        """Lista con todas las imágenes (principal + adicionales) en orden."""
        images: list[Path] = []
        if self.main_image is not None:
            images.append(self.main_image)
        images.extend(self.additional_images)
        return images

    @property
    def has_main_image(self) -> bool:
        """Indica si el artículo tiene imagen principal."""
        return self.main_image is not None

    def mark_in_progress(self) -> None:
        """Marca el artículo como en proceso y registra el tiempo de inicio."""
        self.status = ArticleStatus.IN_PROGRESS
        self.start_time = datetime.now()
        self.error_message = ""

    def mark_success(self) -> None:
        """Marca el artículo como publicado exitosamente."""
        self.status = ArticleStatus.SUCCESS
        self.end_time = datetime.now()

    def mark_error(self, message: str) -> None:
        """
        Marca el artículo con error.

        Args:
            message: Descripción del error ocurrido.
        """
        self.status = ArticleStatus.ERROR
        self.error_message = message
        self.end_time = datetime.now()

    def mark_skipped(self, reason: str = "") -> None:
        """
        Marca el artículo como omitido.

        Args:
            reason: Razón por la que se omitió.
        """
        self.status = ArticleStatus.SKIPPED
        self.error_message = reason
        self.end_time = datetime.now()

    def get_additional_image_index(self, image_path: Path) -> str:
        """
        Obtiene el índice de una imagen adicional (ej: '_1', '_2').

        Args:
            image_path: Ruta a la imagen adicional.

        Returns:
            Cadena con el índice (ej: '_1') o cadena vacía si no se encuentra.
        """
        import re
        # Intentar extraer el índice del nombre del archivo (ej. R123_2.jpg -> _2)
        stem = image_path.stem
        match = re.search(r'[_-](\d+)$', stem)
        if match:
            return f"_{match.group(1)}"

        try:
            position = self.additional_images.index(image_path)
            return f"_{position + 1}"
        except ValueError:
            return ""

    def get_additional_image_remote_name(self, image_path: Path) -> str:
        """
        Genera el nombre remoto para una imagen adicional.

        Ejemplo: Para el artículo R123 e índice 1, genera 'R123_1.jpg'.

        Args:
            image_path: Ruta local a la imagen adicional.

        Returns:
            Nombre de archivo remoto con índice.
        """
        index = self.get_additional_image_index(image_path)
        if not index:
            return image_path.name
        extension = image_path.suffix.lower()
        return f"{self.code}{index}{extension}"

    def reset(self) -> None:
        """Reinicia el estado del artículo a pendiente."""
        self.status = ArticleStatus.PENDING
        self.error_message = ""
        self.start_time = None
        self.end_time = None

    def __repr__(self) -> str:
        return (
            f"Article(code='{self.code}', "
            f"images={self.image_count}, "
            f"status={self.status})"
        )
