"""
Worker de publicación basado en QThread.

Ejecuta la publicación de artículos en un hilo separado para no bloquear
la GUI. Emite señales Qt para actualizar la interfaz en tiempo real.
Soporta cancelación, lotes, modo simulación, y políticas de conflicto FTP.

Arquitectura de hilos:
    PublishWorker (QThread)
        ├── FTP uploads (paralelos vía PublishService → ThreadPoolExecutor)
        └── SQL calls (secuenciales vía EcommerceRepository)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from models.article import Article, FtpConflictPolicy
from services.publish_service import PublishService

logger = logging.getLogger(__name__)


class PublishWorker(QThread):
    """
    Worker que ejecuta la publicación de artículos en un hilo separado.

    Procesa una lista de artículos en lotes, emitiendo señales Qt
    para que la GUI se actualice en tiempo real. Soporta cancelación
    segura mediante un flag atómico.

    Signals:
        article_started: Emitido cuando inicia el procesamiento de un artículo.
            Payload: str (código del artículo).
        ftp_completed: Emitido cuando el upload FTP de un artículo es exitoso.
            Payload: str (código del artículo).
        sql_completed: Emitido cuando la ejecución SQL de un artículo es exitosa.
            Payload: str (código del artículo).
        article_completed: Emitido cuando un artículo finaliza (éxito o error).
            Payload: str (código), bool (True=éxito).
        article_error: Emitido cuando un artículo falla.
            Payload: str (código), str (mensaje de error).
        progress_updated: Emitido para actualizar la barra de progreso.
            Payload: int (actual), int (total).
        log_message: Emitido con mensajes para el log en tiempo real.
            Payload: str (mensaje).
        all_completed: Emitido cuando todos los artículos finalizan.
            Payload: int (exitosos), int (fallidos).
        cancelled: Emitido cuando la publicación se cancela.
        ftp_conflict_found: Emitido cuando se detecta una imagen existente en FTP
            y la política es ASK. Payload: str (código), str (nombre imagen).
    """

    # --- Señales Qt ---
    article_started = pyqtSignal(str)
    ftp_completed = pyqtSignal(str)
    sql_completed = pyqtSignal(str)
    article_completed = pyqtSignal(str, bool)
    article_error = pyqtSignal(str, str)
    progress_updated = pyqtSignal(int, int)
    log_message = pyqtSignal(str)
    all_completed = pyqtSignal(int, int)
    cancelled = pyqtSignal()
    ftp_conflict_found = pyqtSignal(str, str)

    def __init__(
        self,
        articles: list[Article],
        publish_service: PublishService,
        simulation: bool = False,
        ftp_conflict_policy: FtpConflictPolicy = FtpConflictPolicy.OVERWRITE,
        batch_size: int = 0,
        parent=None,
    ) -> None:
        """
        Inicializa el worker de publicación.

        Args:
            articles: Lista de artículos a publicar.
            publish_service: Servicio de publicación.
            simulation: True para modo simulación.
            ftp_conflict_policy: Política de conflicto FTP.
            batch_size: Tamaño del lote (0 = todos).
            parent: Widget padre de Qt.
        """
        super().__init__(parent)
        self._articles = articles
        self._publish_service = publish_service
        self._simulation = simulation
        self._ftp_conflict_policy = ftp_conflict_policy
        self._batch_size = batch_size

        # Control de cancelación thread-safe
        self._cancel_flag = threading.Event()

        # Control de conflicto FTP (para política ASK)
        self._conflict_event = threading.Event()
        self._conflict_response: bool = True  # True=sobrescribir, False=omitir

    # ================================================================
    # Control de cancelación
    # ================================================================

    def request_cancel(self) -> None:
        """
        Solicita la cancelación de la publicación.

        El worker verificará este flag entre artículos y se detendrá
        de forma segura.
        """
        logger.info("Cancelación solicitada por el usuario.")
        self._cancel_flag.set()

    @property
    def _is_cancelled(self) -> bool:
        """Verifica si se ha solicitado la cancelación."""
        return self._cancel_flag.is_set()

    # ================================================================
    # Control de conflictos FTP
    # ================================================================

    def resolve_conflict(self, overwrite: bool) -> None:
        """
        Resuelve un conflicto FTP pendiente.

        Llamado desde el hilo principal (GUI) cuando el usuario
        responde al diálogo de conflicto.

        Args:
            overwrite: True para sobrescribir, False para omitir.
        """
        self._conflict_response = overwrite
        self._conflict_event.set()

    def _conflict_callback(self, article_code: str, remote_name: str) -> bool:
        """
        Callback invocado por PublishService cuando detecta un conflicto FTP.

        Emite una señal Qt para que la GUI muestre el diálogo, y espera
        la respuesta del usuario.

        Args:
            article_code: Código del artículo.
            remote_name: Nombre del archivo en conflicto.

        Returns:
            True para sobrescribir, False para omitir.
        """
        self._conflict_event.clear()
        self._conflict_response = True

        # Emitir señal al hilo principal
        self.ftp_conflict_found.emit(article_code, remote_name)

        # Esperar respuesta del usuario (bloquea este hilo, no la GUI)
        self._conflict_event.wait()

        return self._conflict_response

    # ================================================================
    # Ejecución principal
    # ================================================================

    def run(self) -> None:
        """
        Método principal del hilo. Procesa los artículos y emite señales.

        Si batch_size > 0, procesa solo esa cantidad de artículos.
        Si batch_size == 0, procesa todos.
        """
        start_time = time.time()
        mode_str = "SIMULACIÓN" if self._simulation else "REAL"

        # Determinar artículos a procesar según batch_size
        articles_to_process = self._articles
        if self._batch_size > 0:
            articles_to_process = self._articles[:self._batch_size]

        total = len(articles_to_process)
        successful = 0
        failed = 0

        self._emit_log(
            f"═══ Inicio de publicación ({mode_str}) ═══"
        )
        self._emit_log(
            f"Artículos a procesar: {total}"
            + (f" (lote de {self._batch_size})" if self._batch_size > 0 else "")
        )

        logger.info(
            f"Worker iniciado: {total} artículos, modo={mode_str}, "
            f"batch={self._batch_size}, "
            f"ftp_policy={self._ftp_conflict_policy.value}"
        )

        # Determinar callback de conflicto
        conflict_cb = None
        if self._ftp_conflict_policy == FtpConflictPolicy.ASK:
            conflict_cb = self._conflict_callback

        for index, article in enumerate(articles_to_process, start=1):
            # Verificar cancelación
            if self._is_cancelled:
                remaining = total - index + 1
                self._emit_log(
                    f"⚠ Publicación cancelada. "
                    f"{remaining} artículos pendientes."
                )
                logger.info(
                    f"Worker cancelado. Procesados: {index - 1}/{total}, "
                    f"exitosos: {successful}, fallidos: {failed}"
                )
                self.cancelled.emit()
                return

            # Emitir señal de inicio de artículo
            self.article_started.emit(article.code)
            self._emit_log(
                f"─── [{index}/{total}] {article.code} "
                f"({article.image_count} imágenes) ───"
            )

            # Publicar artículo
            try:
                success = self._publish_service.publish_article(
                    article=article,
                    simulation=self._simulation,
                    ftp_conflict_policy=self._ftp_conflict_policy,
                    conflict_callback=conflict_cb,
                    progress_callback=self._progress_callback,
                )

                if success:
                    successful += 1
                    self.article_completed.emit(article.code, True)
                    if not self._simulation:
                        self.ftp_completed.emit(article.code)
                        self.sql_completed.emit(article.code)
                else:
                    failed += 1
                    self.article_error.emit(article.code, article.error_message)
                    self.article_completed.emit(article.code, False)

            except Exception as e:
                failed += 1
                error_msg = f"Error inesperado: {e}"
                article.mark_error(error_msg)
                self.article_error.emit(article.code, error_msg)
                self.article_completed.emit(article.code, False)
                logger.error(
                    f"Worker: Error procesando '{article.code}': {e}",
                    exc_info=True,
                )

            # Actualizar progreso
            self.progress_updated.emit(index, total)

        # Completado
        elapsed = time.time() - start_time
        self._emit_log(
            f"═══ Publicación finalizada ═══\n"
            f"    Exitosos: {successful}\n"
            f"    Fallidos: {failed}\n"
            f"    Tiempo total: {elapsed:.1f}s"
        )

        logger.info(
            f"Worker completado: {successful} exitosos, {failed} fallidos, "
            f"{elapsed:.1f}s total"
        )

        self.all_completed.emit(successful, failed)

    def _progress_callback(self, message: str) -> None:
        """
        Callback utilizado por PublishService para emitir mensajes de log.

        Args:
            message: Mensaje de progreso.
        """
        self._emit_log(message)

    def _emit_log(self, message: str) -> None:
        """
        Emite un mensaje al log de la GUI con timestamp.

        Args:
            message: Mensaje a emitir.
        """
        timestamp = time.strftime("%H:%M:%S")
        self.log_message.emit(f"{timestamp} — {message}")

    def __repr__(self) -> str:
        return (
            f"PublishWorker(articles={len(self._articles)}, "
            f"simulation={self._simulation}, "
            f"batch={self._batch_size})"
        )
