"""
Servicio de escaneo y gestión de imágenes de artículos.

Escanea una carpeta local para detectar imágenes de artículos,
agrupa por código, identifica imagen principal y adicionales,
valida extensiones, detecta duplicados y convierte PNG a JPG.

Patrones de nombre:
    - Imagen principal: CODE.jpg (ej: R123.jpg)
    - Imágenes adicionales: CODE_N.ext (ej: R123_1.jpg, R123_2.jpg)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from PIL import Image

from models.article import Article

logger = logging.getLogger(__name__)

# Extensiones de imagen válidas (en minúsculas)
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Patrón regex para parsear nombres de archivo de artículos
# Grupo 1: código del artículo (alfanumérico)
# Grupo 2 (opcional): índice con guión bajo o guión medio (_1, -1, etc.)
FILENAME_PATTERN = re.compile(
    r"^([A-Za-z0-9]+?)(?:[_-](\d+))?$",
    re.IGNORECASE,
)


class ImageServiceError(Exception):
    """Excepción base para errores del servicio de imágenes."""
    pass


class ImageService:
    """
    Servicio para escanear, validar y procesar imágenes de artículos.

    Escanea una carpeta local, agrupa las imágenes por código de artículo,
    identifica la imagen principal y las adicionales, valida que sean
    archivos de imagen válidos, y opcionalmente convierte PNG a JPG.

    Attributes:
        image_folder: Ruta a la carpeta de imágenes.

    Example:
        >>> service = ImageService(Path("C:/imagenes/articulos"))
        >>> articles = service.scan_articles()
        >>> for article in articles:
        ...     print(f"{article.code}: {article.image_count} imágenes")
    """

    def __init__(self, image_folder: Path) -> None:
        """
        Inicializa el servicio con la carpeta de imágenes.

        Args:
            image_folder: Ruta a la carpeta que contiene las imágenes.

        Raises:
            ImageServiceError: Si la carpeta no existe o no es un directorio.
        """
        self._image_folder = Path(image_folder)
        if not self._image_folder.exists():
            raise ImageServiceError(
                f"La carpeta de imágenes no existe: {self._image_folder}"
            )
        if not self._image_folder.is_dir():
            raise ImageServiceError(
                f"La ruta no es un directorio: {self._image_folder}"
            )

    @property
    def image_folder(self) -> Path:
        """Ruta a la carpeta de imágenes."""
        return self._image_folder

    # ================================================================
    # Escaneo de artículos
    # ================================================================

    def scan_articles(self) -> list[Article]:
        """
        Escanea la carpeta de imágenes y genera una lista de artículos.

        Agrupa las imágenes por código de artículo, identifica la imagen
        principal (CODE.ext) y las adicionales (CODE_N.ext), y crea
        objetos Article para cada código encontrado.

        Returns:
            Lista de objetos Article ordenados alfabéticamente por código.
        """
        logger.info(f"Escaneando carpeta de imágenes: {self._image_folder}")

        # Diccionario temporal: código → {main: Path, additional: [Path]}
        articles_map: dict[str, dict] = {}

        # Recorrer todos los archivos con extensiones válidas
        image_files = self._get_image_files()

        for image_path in image_files:
            code, index = self._parse_code(image_path.stem)

            if code is None:
                logger.warning(
                    f"No se pudo parsear el nombre de archivo: {image_path.name}"
                )
                continue

            # Normalizar código a mayúsculas
            code_upper = code.upper()

            if code_upper not in articles_map:
                articles_map[code_upper] = {
                    "main": None,
                    "additional": [],
                    "original_code": code,
                }

            if index is None:
                # Es la imagen principal
                if articles_map[code_upper]["main"] is not None:
                    logger.warning(
                        f"Imagen principal duplicada para '{code_upper}': "
                        f"{image_path.name} (se usa la primera encontrada)"
                    )
                else:
                    articles_map[code_upper]["main"] = image_path
            else:
                # Es una imagen adicional
                articles_map[code_upper]["additional"].append(
                    (index, image_path)
                )

        # Construir lista de Article
        articles: list[Article] = []
        for code_upper, data in sorted(articles_map.items()):
            # Ordenar imágenes adicionales por índice
            additional_sorted = sorted(data["additional"], key=lambda x: x[0])
            additional_paths = [path for _, path in additional_sorted]

            article = Article(
                code=code_upper,
                main_image=data["main"],
                additional_images=additional_paths,
            )
            articles.append(article)

        logger.info(
            f"Escaneo completado: {len(articles)} artículos encontrados, "
            f"{sum(a.image_count for a in articles)} imágenes totales"
        )

        return articles

    def _get_image_files(self) -> list[Path]:
        """
        Obtiene todos los archivos de imagen válidos en la carpeta y subcarpetas.

        Returns:
            Lista de rutas a archivos con extensiones válidas.
        """
        image_files: list[Path] = []
        try:
            for file_path in self._image_folder.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in VALID_EXTENSIONS:
                    image_files.append(file_path)
        except Exception as e:
            logger.error(f"Error al escanear subcarpetas de '{self._image_folder}': {e}")

        logger.debug(f"Archivos de imagen encontrados (recursivo): {len(image_files)}")
        return image_files

    # ================================================================
    # Detección de imágenes por código
    # ================================================================

    def get_main_image(self, code: str) -> Optional[Path]:
        """
        Busca la imagen principal de un artículo por código en la carpeta y subcarpetas.

        Busca archivos que coincidan con CODE.jpg, CODE.jpeg o CODE.png.

        Args:
            code: Código del artículo (ej: 'R123').

        Returns:
            Ruta a la imagen principal, o None si no se encuentra.
        """
        for file_path in self._get_image_files():
            parsed_code, index = self._parse_code(file_path.stem)
            if (
                parsed_code is not None
                and parsed_code.upper() == code.upper()
                and index is None
            ):
                return file_path
        return None

    def get_additional_images(self, code: str) -> list[Path]:
        """
        Busca las imágenes adicionales de un artículo por código.

        Busca archivos que coincidan con CODE_1.ext, CODE_2.ext, etc.

        Args:
            code: Código del artículo (ej: 'R123').

        Returns:
            Lista ordenada de rutas a imágenes adicionales.
        """
        additional: list[tuple[int, Path]] = []

        for file_path in self._get_image_files():
            parsed_code, index = self._parse_code(file_path.stem)
            if (
                parsed_code is not None
                and parsed_code.upper() == code.upper()
                and index is not None
            ):
                additional.append((index, file_path))

        # Ordenar por índice
        additional.sort(key=lambda x: x[0])
        return [path for _, path in additional]

    # ================================================================
    # Validación
    # ================================================================

    def validate_image(self, path: Path) -> bool:
        """
        Valida que un archivo sea una imagen legible.

        Verifica la extensión y que Pillow pueda abrirla.

        Args:
            path: Ruta al archivo de imagen.

        Returns:
            True si la imagen es válida y legible.
        """
        if not path.exists():
            logger.warning(f"Imagen no existe: {path}")
            return False

        if path.suffix.lower() not in VALID_EXTENSIONS:
            logger.warning(f"Extensión no válida: {path.suffix} ({path.name})")
            return False

        try:
            with Image.open(path) as img:
                img.verify()
            return True
        except Exception as e:
            logger.warning(f"Imagen no legible: {path.name} | {e}")
            return False

    def detect_duplicates(self) -> list[str]:
        """
        Detecta artículos con imágenes principales duplicadas.

        Un duplicado ocurre cuando existe R123.jpg y R123.png
        para el mismo código.

        Returns:
            Lista de códigos de artículos con imágenes duplicadas.
        """
        code_counts: dict[str, list[str]] = {}

        for file_path in self._get_image_files():
            code, index = self._parse_code(file_path.stem)
            if code is not None and index is None:
                # Es una imagen principal
                code_upper = code.upper()
                if code_upper not in code_counts:
                    code_counts[code_upper] = []
                code_counts[code_upper].append(file_path.name)

        duplicates = [
            code
            for code, files in code_counts.items()
            if len(files) > 1
        ]

        if duplicates:
            logger.warning(
                f"Imágenes principales duplicadas detectadas: {duplicates}"
            )

        return duplicates

    # ================================================================
    # Conversión
    # ================================================================

    def convert_png_to_jpg(self, path: Path) -> Path:
        """
        Convierte una imagen PNG a formato JPG.

        Crea el archivo JPG en la misma carpeta. El archivo PNG
        original se mantiene.

        Args:
            path: Ruta al archivo PNG.

        Returns:
            Ruta al nuevo archivo JPG.

        Raises:
            ImageServiceError: Si la conversión falla.
        """
        if path.suffix.lower() != ".png":
            raise ImageServiceError(f"El archivo no es PNG: {path.name}")

        jpg_path = path.with_suffix(".jpg")

        try:
            with Image.open(path) as img:
                # Convertir a RGB si tiene canal alfa (RGBA)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(jpg_path, "JPEG", quality=95)

            logger.info(f"Conversión PNG→JPG exitosa: {path.name} → {jpg_path.name}")
            return jpg_path

        except Exception as e:
            logger.error(f"Error al convertir PNG a JPG: {path.name} | {e}")
            raise ImageServiceError(f"Error de conversión: {e}")

    def convert_all_png(self) -> list[Path]:
        """
        Convierte todas las imágenes PNG de la carpeta a JPG.

        Returns:
            Lista de rutas a los nuevos archivos JPG creados.
        """
        converted: list[Path] = []
        for file_path in self._get_image_files():
            if file_path.suffix.lower() == ".png":
                try:
                    jpg_path = self.convert_png_to_jpg(file_path)
                    converted.append(jpg_path)
                except ImageServiceError:
                    continue  # Ya logueado en convert_png_to_jpg
        return converted

    # ================================================================
    # Utilidades internas
    # ================================================================

    @staticmethod
    def _parse_code(filename_stem: str) -> tuple[Optional[str], Optional[int]]:
        """
        Extrae el código de artículo y el índice del nombre de archivo.

        Patrones reconocidos:
            - 'R123' → code='R123', index=None (imagen principal)
            - 'R123_1' → code='R123', index=1 (imagen adicional)
            - 'R123_2' → code='R123', index=2

        Args:
            filename_stem: Nombre del archivo sin extensión.

        Returns:
            Tupla (código, índice) donde índice es None para la imagen principal.
            Retorna (None, None) si no se puede parsear.
        """
        match = FILENAME_PATTERN.match(filename_stem)
        if match is None:
            return None, None

        code = match.group(1)
        index_str = match.group(2)
        index = int(index_str) if index_str is not None else None

        return code, index

    def __repr__(self) -> str:
        return f"ImageService(folder='{self._image_folder}')"
