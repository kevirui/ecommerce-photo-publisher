"""
Worker de Sincronización basado en QThread.

Ejecuta el análisis de Excel y las consultas SQL de base de datos
en un hilo separado para mantener la GUI fluida e interactiva.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from PyQt6.QtCore import QThread, pyqtSignal

from services.sync_service import SyncService

logger = logging.getLogger(__name__)


class SyncWorker(QThread):
    """
    Worker que ejecuta la comparación de artículos contra la base de datos
    o consulta la base de datos directamente en segundo plano.
    """

    # --- Señales Qt ---
    progress_updated = pyqtSignal(int, int)  # (actual, total)
    log_message = pyqtSignal(str)           # Mensaje de log
    article_processed = pyqtSignal(dict)    # Envía cada artículo procesado
    finished_sync = pyqtSignal(list, dict)  # (lista_resultados, dict_estadisticas)
    error_occurred = pyqtSignal(str)        # Error fatal
    cancelled = pyqtSignal()                # Cancelación exitosa

    def __init__(
        self,
        sync_service: SyncService,
        mode: str,  # 'excel' o 'sql'
        excel_path: Optional[Path] = None,
        pending_only: bool = False,
        ignore_inexistent: bool = False,
        auto_export_pending: bool = False,
        output_dir: Optional[Path] = None,
        parent=None,
    ) -> None:
        """
        Inicializa el worker de sincronización.
        """
        super().__init__(parent)
        self._sync_service = sync_service
        self._mode = mode.lower()
        self._excel_path = excel_path
        self._pending_only = pending_only
        self._ignore_inexistent = ignore_inexistent
        self._auto_export_pending = auto_export_pending
        self._output_dir = output_dir if output_dir else Path.cwd()
        self._cancel_flag = threading.Event()

    def cancel(self) -> None:
        """Solicita la cancelación segura del proceso."""
        self._cancel_flag.set()
        logger.info("Cancelación solicitada para SyncWorker.")

    def run(self) -> None:
        """Método de ejecución principal en el hilo secundario."""
        start_time = time.time()
        self.log_message.emit("Inicio análisis" if self._mode == "excel" else "Inicio consulta SQL")

        try:
            if self._mode == "excel":
                self._run_excel_mode(start_time)
            elif self._mode == "sql":
                self._run_sql_mode(start_time)
            else:
                raise ValueError(f"Modo de sincronización no soportado: {self._mode}")

        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"Error SQL: {e}" if "pyodbc" in str(e) or "SQL" in str(e) else f"Error: {e}"
            logger.error(f"Error en SyncWorker: {e}", exc_info=True)
            self.log_message.emit(f"✗ {error_msg}")
            self.log_message.emit(f"Tiempo total: {elapsed:.2f}s con error.")
            self.error_occurred.emit(error_msg)

    def _run_excel_mode(self, start_time: float) -> None:
        """Ejecuta la lógica de comparación de Excel vs SQL Server."""
        if not self._excel_path:
            raise ValueError("No se especificó la ruta del archivo Excel.")

        # Leer códigos de Excel
        self.log_message.emit(f"Leyendo códigos desde {self._excel_path.name}...")
        codes = self._sync_service.read_excel_codes(self._excel_path)
        total = len(codes)

        if total == 0:
            self.log_message.emit("No se encontraron códigos para procesar en el Excel.")
            stats = self._compute_statistics([])
            self.finished_sync.emit([], stats)
            return

        results: List[Dict[str, Any]] = []
        processed_count = 0

        self.log_message.emit(f"Comparando {total} códigos contra SQL Server...")

        for code in codes:
            if self._cancel_flag.is_set():
                self.log_message.emit("Proceso cancelado por el usuario.")
                self.cancelled.emit()
                return

            try:
                # Consultar BD (con soporte de caché interno del servicio)
                art_data = self._sync_service.get_article_status_from_db(code)

                # Ignorar artículos inexistentes si está configurado
                if self._ignore_inexistent and art_data["estado"] == "INEXISTENTE":
                    self.log_message.emit(f"Artículo consultado: {code} - INEXISTENTE (ignorado por opción)")
                else:
                    results.append(art_data)
                    self.article_processed.emit(art_data)
                    self.log_message.emit(f"Artículo consultado: {code} - {art_data['estado']}")

            except Exception as e:
                # Logear error pero continuar con los siguientes si es error individual
                self.log_message.emit(f"✗ Error consultando artículo {code}: {e}")

            processed_count += 1
            self.progress_updated.emit(processed_count, total)
            # Pequeño sleep opcional para no saturar si es muy rápido, pero omitimos para máximo rendimiento

        # Generar estadísticas
        stats = self._compute_statistics(results)

        # Exportar automáticamente pendientes si está habilitado
        if self._auto_export_pending:
            try:
                export_path = self._sync_service.export_pending_auto(self._output_dir, results)
                self.log_message.emit(f"Archivo exportado: {export_path.name}")
            except Exception as e:
                self.log_message.emit(f"✗ Error al exportar pendientes automáticamente: {e}")

        elapsed = time.time() - start_time
        self.log_message.emit(f"Tiempo total: {elapsed:.2f}s")
        self.finished_sync.emit(results, stats)

    def _run_sql_mode(self, start_time: float) -> None:
        """Ejecuta la consulta directa SQL Server."""
        self.log_message.emit("Consultando artículos de la base de datos...")
        
        # Ejecutar query pesada
        articles = self._sync_service.get_all_articles_status_from_db(self._pending_only)
        total = len(articles)

        if self._cancel_flag.is_set():
            self.log_message.emit("Proceso cancelado.")
            self.cancelled.emit()
            return

        self.log_message.emit(f"Procesando {total} artículos obtenidos de SQL Server...")

        # Simular progreso de carga rápido en la UI para feedback
        chunk_size = max(1, total // 50)
        for i, art in enumerate(articles):
            if self._cancel_flag.is_set():
                self.log_message.emit("Proceso cancelado.")
                self.cancelled.emit()
                return

            self.article_processed.emit(art)
            if i % chunk_size == 0 or i == total - 1:
                self.progress_updated.emit(i + 1, total)

        stats = self._compute_statistics(articles)
        elapsed = time.time() - start_time
        self.log_message.emit(f"Tiempo total: {elapsed:.2f}s")
        self.finished_sync.emit(articles, stats)

    def _compute_statistics(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcula estadísticas generales sobre los artículos procesados."""
        total = len(data)
        published = sum(1 for item in data if item.get("estado") == "PUBLICADO")
        pending = sum(1 for item in data if item.get("estado") == "PENDIENTE")
        incomplete = sum(1 for item in data if item.get("estado") == "INCOMPLETO")
        inexistent = sum(1 for item in data if item.get("estado") == "INEXISTENTE")
        errors = sum(1 for item in data if item.get("estado") == "INEXISTENTE" or "error" in str(item.get("observaciones", "")).lower())

        pct_published = (published / total * 100) if total > 0 else 0.0
        pct_pending = (pending / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "published": published,
            "pending": pending,
            "incomplete": incomplete,
            "inexistent": inexistent,
            "errors": errors,
            "pct_published": pct_published,
            "pct_pending": pct_pending
        }
