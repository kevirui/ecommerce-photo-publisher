"""
Servicio de publicación de artículos al ecommerce.

Orquesta el flujo completo de publicación: subida FTP de imágenes
y ejecución de Stored Procedures. Soporta modo simulación
(valida sin ejecutar) y políticas de conflicto FTP.

No interactúa directamente con SQL para los SPs; todo pasa
por EcommerceRepository.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Optional

from models.article import Article, ArticleStatus, FtpConflictPolicy
from services.ecommerce_repository import EcommerceRepository
from services.ftp_service import FtpService, FtpUploadError, FtpServiceError
from services.sql_service import SqlExecutionError

logger = logging.getLogger(__name__)


class PublishServiceError(Exception):
    """Excepción base para errores del servicio de publicación."""
    pass


class PublishService:
    """
    Servicio que orquesta la publicación de artículos al ecommerce.

    Para cada artículo:
    1. Verifica existencia en la base de datos.
    2. Sube la imagen principal al FTP.
    3. Ejecuta el SP eco_articulos_publi_web_actua.
    4. Por cada imagen adicional: sube al FTP + ejecuta eco_articulos_imagenes_actua.

    Soporta modo simulación que valida todo sin ejecutar SPs ni subir archivos,
    y políticas de conflicto FTP (sobrescribir, omitir, preguntar).

    Attributes:
        ecommerce_repo: Repositorio de operaciones ecommerce.
        ftp_service: Servicio de conexión FTP.
    """

    def __init__(
        self,
        ecommerce_repo: EcommerceRepository,
        ftp_service: FtpService,
    ) -> None:
        """
        Inicializa el servicio de publicación.

        Args:
            ecommerce_repo: Repositorio para ejecutar SPs.
            ftp_service: Servicio FTP para subir imágenes.
        """
        self._repo = ecommerce_repo
        self._ftp = ftp_service

    # ================================================================
    # Validación
    # ================================================================

    def validate_article(self, article: Article) -> list[str]:
        """
        Ejecuta validaciones previas a la publicación de un artículo.

        Verifica:
        - Que el artículo tenga imagen principal.
        - Que la imagen principal exista en disco.
        - Que todas las imágenes adicionales existan en disco.
        - Que el artículo exista en la base de datos.

        Args:
            article: Artículo a validar.

        Returns:
            Lista de mensajes de error. Lista vacía si todo es válido.
        """
        errors: list[str] = []

        # Verificar que el artículo tenga al menos una imagen (principal o adicionales)
        if not article.has_main_image and not article.additional_images:
            errors.append(
                f"[{article.code}] No tiene ninguna imagen para publicar (ni principal ni adicionales)."
            )
        elif article.has_main_image and not article.main_image.exists():
            errors.append(
                f"[{article.code}] Imagen principal no encontrada en disco: "
                f"{article.main_image_name}"
            )

        # Verificar imágenes adicionales
        for img_path in article.additional_images:
            if not img_path.exists():
                errors.append(
                    f"[{article.code}] Imagen adicional no encontrada: "
                    f"{img_path.name}"
                )

        # Verificar existencia en BD
        if not self.verify_article_exists(article.code):
            errors.append(
                f"[{article.code}] No existe en la base de datos."
            )

        if errors:
            logger.warning(
                f"Validación fallida para '{article.code}': "
                f"{len(errors)} errores"
            )
        else:
            logger.debug(f"Validación exitosa para '{article.code}'.")

        return errors

    def verify_article_exists(self, code: str) -> bool:
        """
        Verifica si un artículo existe en la base de datos.

        Args:
            code: Código del artículo.

        Returns:
            True si el artículo existe.
        """
        return self._repo.existe_articulo(code)

    # ================================================================
    # Publicación
    # ================================================================

    def publish_article(
        self,
        article: Article,
        simulation: bool = False,
        ftp_conflict_policy: FtpConflictPolicy = FtpConflictPolicy.OVERWRITE,
        conflict_callback: Optional[Callable[[str, str], bool]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Publica un artículo completo (imágenes + SPs).

        En modo simulación:
        - Verifica existencia del artículo en BD (SÍ ejecuta SELECT).
        - Verifica que las imágenes existen localmente.
        - Verifica conexión FTP (sin subir).
        - Verifica si las imágenes ya existen en FTP.
        - NO ejecuta Stored Procedures.
        - NO sube archivos al FTP.

        En modo real:
        1. Sube imagen principal al FTP.
        2. Ejecuta eco_articulos_publi_web_actua.
        3. Por cada imagen adicional: sube al FTP + ejecuta eco_articulos_imagenes_actua.

        Args:
            article: Artículo a publicar.
            simulation: True para modo simulación (solo validar).
            ftp_conflict_policy: Política cuando una imagen ya existe en FTP.
            conflict_callback: Función que recibe (código, nombre_imagen) y
                             retorna True para sobrescribir, False para omitir.
                             Solo se invoca si ftp_conflict_policy es ASK.
            progress_callback: Función para emitir mensajes de progreso.

        Returns:
            True si la publicación fue exitosa.

        Raises:
            PublishServiceError: Si ocurre un error irrecuperable.
        """
        article.mark_in_progress()
        start_time = time.time()

        try:
            # --- Validaciones ---
            self._emit_progress(
                progress_callback,
                f"[{article.code}] Validando artículo..."
            )

            validation_errors = self.validate_article(article)
            if validation_errors:
                article.mark_error("; ".join(validation_errors))
                return False

            if simulation:
                return self._publish_simulation(
                    article, progress_callback
                )

            return self._publish_real(
                article,
                ftp_conflict_policy,
                conflict_callback,
                progress_callback,
            )

        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"Error inesperado: {e}"
            logger.error(
                f"[{article.code}] {error_msg} ({elapsed:.2f}s)",
                exc_info=True,
            )
            article.mark_error(error_msg)
            return False

    def _publish_simulation(
        self,
        article: Article,
        progress_callback: Optional[Callable[[str], None]],
    ) -> bool:
        """
        Ejecuta la publicación en modo simulación (solo validación).

        Args:
            article: Artículo a simular.
            progress_callback: Callback de progreso.

        Returns:
            True si la simulación no detectó errores.
        """
        self._emit_progress(
            progress_callback,
            f"[{article.code}] [SIMULACIÓN] Artículo verificado en BD ✓"
        )

        # Verificar conexión FTP (sin subir)
        if not self._ftp.test_connection():
            article.mark_error("Conexión FTP no disponible (simulación).")
            return False

        self._emit_progress(
            progress_callback,
            f"[{article.code}] [SIMULACIÓN] Conexión FTP verificada ✓"
        )

        # Verificar si las imágenes ya existen en FTP
        warnings: list[str] = []
        for img_path in article.all_images:
            remote_name = self._get_remote_name(article, img_path)
            if self._ftp.exists(remote_name):
                warnings.append(f"Ya existe en FTP: {remote_name}")
                self._emit_progress(
                    progress_callback,
                    f"[{article.code}] [SIMULACIÓN] ⚠ {remote_name} ya existe en FTP"
                )
            else:
                self._emit_progress(
                    progress_callback,
                    f"[{article.code}] [SIMULACIÓN] {remote_name} listo para subir ✓"
                )

        # En simulación siempre marcamos como exitoso (validación pasó)
        if warnings:
            article.mark_success()
            article.error_message = f"Simulación OK con avisos: {'; '.join(warnings)}"
        else:
            article.mark_success()
            article.error_message = "Simulación OK — sin errores"

        self._emit_progress(
            progress_callback,
            f"[{article.code}] [SIMULACIÓN] Validación completada ✓"
        )

        logger.info(f"[{article.code}] Simulación completada exitosamente.")
        return True

    def _publish_real(
        self,
        article: Article,
        ftp_conflict_policy: FtpConflictPolicy,
        conflict_callback: Optional[Callable[[str, str], bool]],
        progress_callback: Optional[Callable[[str], None]],
    ) -> bool:
        """
        Ejecuta la publicación real (FTP + SPs).

        Args:
            article: Artículo a publicar.
            ftp_conflict_policy: Política de conflicto FTP.
            conflict_callback: Callback para preguntar al usuario.
            progress_callback: Callback de progreso.

        Returns:
            True si la publicación fue exitosa.
        """
        # --- 1. Subir imagen principal al FTP ---
        if article.has_main_image:
            main_remote_name = article.main_image_name
            should_upload_main = self._check_ftp_conflict(
                article.code,
                main_remote_name,
                ftp_conflict_policy,
                conflict_callback,
                progress_callback,
            )

            if should_upload_main:
                self._emit_progress(
                    progress_callback,
                    f"[{article.code}] Subiendo {main_remote_name} al FTP..."
                )
                try:
                    self._ftp.upload_file(article.main_image, main_remote_name)
                    self._emit_progress(
                        progress_callback,
                        f"[{article.code}] FTP OK: {main_remote_name} ✓"
                    )
                except (FtpUploadError, FtpServiceError) as e:
                    article.mark_error(f"FTP Error (principal): {e}")
                    return False
            else:
                self._emit_progress(
                    progress_callback,
                    f"[{article.code}] FTP omitido: {main_remote_name} (ya existe)"
                )

            # --- 2. Ejecutar SP principal ---
            self._emit_progress(
                progress_callback,
                f"[{article.code}] Ejecutando SP publicación principal..."
            )
            try:
                self._repo.publicar_articulo(article.code, main_remote_name)
                self._emit_progress(
                    progress_callback,
                    f"[{article.code}] SQL OK: eco_articulos_publi_web_actua ✓"
                )
            except SqlExecutionError as e:
                article.mark_error(f"SQL Error (principal): {e}")
                return False
        else:
            self._emit_progress(
                progress_callback,
                f"[{article.code}] Sin imagen principal, omitiendo subida principal."
            )

        # --- 3. Por cada imagen adicional ---
        for img_path in article.additional_images:
            remote_name = article.get_additional_image_remote_name(img_path)
            indice = article.get_additional_image_index(img_path)

            # Verificar conflicto FTP
            should_upload = self._check_ftp_conflict(
                article.code,
                remote_name,
                ftp_conflict_policy,
                conflict_callback,
                progress_callback,
            )

            if should_upload:
                self._emit_progress(
                    progress_callback,
                    f"[{article.code}] Subiendo {remote_name} al FTP..."
                )
                try:
                    self._ftp.upload_file(img_path, remote_name)
                    self._emit_progress(
                        progress_callback,
                        f"[{article.code}] FTP OK: {remote_name} ✓"
                    )
                except (FtpUploadError, FtpServiceError) as e:
                    article.mark_error(f"FTP Error ({remote_name}): {e}")
                    return False
            else:
                self._emit_progress(
                    progress_callback,
                    f"[{article.code}] FTP omitido: {remote_name} (ya existe)"
                )

            # Ejecutar SP de imagen adicional
            self._emit_progress(
                progress_callback,
                f"[{article.code}] Ejecutando SP imagen adicional ({indice})..."
            )
            try:
                self._repo.publicar_imagen_adicional(
                    article.code, remote_name, indice
                )
                self._emit_progress(
                    progress_callback,
                    f"[{article.code}] SQL OK: imagen adicional {indice} ✓"
                )
            except SqlExecutionError as e:
                article.mark_error(f"SQL Error ({remote_name}): {e}")
                return False

        # --- Todo exitoso ---
        article.mark_success()
        self._emit_progress(
            progress_callback,
            f"[{article.code}] ✓ Publicación completada exitosamente"
        )
        logger.info(
            f"[{article.code}] Publicación completada: "
            f"{article.image_count} imágenes, {article.elapsed_time:.2f}s"
        )
        return True

    # ================================================================
    # Conflictos FTP
    # ================================================================

    def _check_ftp_conflict(
        self,
        article_code: str,
        remote_name: str,
        policy: FtpConflictPolicy,
        conflict_callback: Optional[Callable[[str, str], bool]],
        progress_callback: Optional[Callable[[str], None]],
    ) -> bool:
        """
        Verifica si una imagen ya existe en FTP y aplica la política.

        Args:
            article_code: Código del artículo.
            remote_name: Nombre remoto del archivo.
            policy: Política de conflicto.
            conflict_callback: Callback para preguntar al usuario.
            progress_callback: Callback de progreso.

        Returns:
            True si se debe subir el archivo, False si se omite.
        """
        try:
            if not self._ftp.exists(remote_name):
                return True  # No existe, subir normalmente
        except FtpServiceError:
            return True  # Error al verificar, intentar subir

        # El archivo existe en el FTP
        logger.info(
            f"[{article_code}] Imagen '{remote_name}' ya existe en FTP. "
            f"Política: {policy.value}"
        )

        if policy == FtpConflictPolicy.OVERWRITE:
            self._emit_progress(
                progress_callback,
                f"[{article_code}] '{remote_name}' existe en FTP → Sobrescribiendo"
            )
            return True

        if policy == FtpConflictPolicy.SKIP:
            self._emit_progress(
                progress_callback,
                f"[{article_code}] '{remote_name}' existe en FTP → Omitiendo"
            )
            return False

        if policy == FtpConflictPolicy.ASK:
            if conflict_callback is not None:
                should_overwrite = conflict_callback(article_code, remote_name)
                if should_overwrite:
                    self._emit_progress(
                        progress_callback,
                        f"[{article_code}] '{remote_name}' → Usuario eligió sobrescribir"
                    )
                    return True
                else:
                    self._emit_progress(
                        progress_callback,
                        f"[{article_code}] '{remote_name}' → Usuario eligió omitir"
                    )
                    return False
            else:
                # Sin callback, sobrescribir por defecto
                return True

        return True

    # ================================================================
    # Utilidades
    # ================================================================

    def _get_remote_name(self, article: Article, image_path: Path) -> str:
        """
        Determina el nombre remoto para una imagen.

        Args:
            article: Artículo dueño de la imagen.
            image_path: Ruta local a la imagen.

        Returns:
            Nombre de archivo remoto.
        """
        if image_path == article.main_image:
            return article.main_image_name
        return article.get_additional_image_remote_name(image_path)

    @staticmethod
    def _emit_progress(
        callback: Optional[Callable[[str], None]],
        message: str,
    ) -> None:
        """
        Emite un mensaje de progreso si hay callback disponible.

        Args:
            callback: Función callback o None.
            message: Mensaje a emitir.
        """
        if callback is not None:
            callback(message)

    def __repr__(self) -> str:
        return f"PublishService(repo={self._repo}, ftp={self._ftp})"
