"""
Worker de Auditoría basado en QThread.

Ejecuta el proceso de auditoría y comparación de artículos e imágenes
en segundo plano para no bloquear la interfaz.
"""

import logging
import threading
import time
from typing import Optional, List, Dict, Any
from PyQt6.QtCore import QThread, pyqtSignal

from services.audit_service import AuditService

logger = logging.getLogger(__name__)


class AuditWorker(QThread):
    """
    Worker que ejecuta la auditoría SQL y FTP en segundo plano.
    """

    # --- Señales Qt ---
    progress_updated = pyqtSignal(int, int)  # (actual, total)
    log_message = pyqtSignal(str)           # Mensajes para la consola/log
    finished_audit = pyqtSignal(list, dict) # (lista_resultados, dict_estadisticas)
    error_occurred = pyqtSignal(str)        # Errores fatales
    cancelled = pyqtSignal()                # Señal de cancelación

    def __init__(
        self,
        audit_service: AuditService,
        mode: str,  # 'sql', 'ftp', 'all'
        parent=None,
    ) -> None:
        """
        Inicializa el worker de auditoría.
        """
        super().__init__(parent)
        self._audit_service = audit_service
        self._mode = mode.lower()
        self._cancel_flag = threading.Event()

    def cancel(self) -> None:
        """Solicita la cancelación segura del proceso."""
        self._cancel_flag.set()
        logger.info("Cancelación de auditoría solicitada.")

    def run(self) -> None:
        """Método de ejecución del hilo secundario."""
        start_time = time.time()
        self.log_message.emit("Inicio auditoría")
        
        try:
            # Lógica de callback para reportar progreso
            def progress_callback(actual: int, total: int):
                if self._cancel_flag.is_set():
                    return
                self.progress_updated.emit(actual, total)

            # Ejecutar análisis en el servicio
            results, stats = self._audit_service.run_audit(
                mode=self._mode,
                progress_callback=progress_callback
            )

            # Validar si hubo cancelación durante la query
            if self._cancel_flag.is_set():
                self.log_message.emit("Auditoría cancelada por el usuario.")
                self.cancelled.emit()
                return

            elapsed = time.time() - start_time
            
            # Registrar estadísticas en el log de la pestaña
            self.log_message.emit(f"Cantidad de artículos analizados: {stats.get('total', 0)}")
            
            # Calcular imágenes en FTP a partir de los datos analizados
            # En modo ALL o FTP, podemos contar cuántos no son huérfanos + huérfanos
            # Pero para ser más directos, informamos de los huérfanos encontrados
            self.log_message.emit(f"Cantidad de imágenes huérfanas: {stats.get('huerfanos', 0)}")
            self.log_message.emit(f"Fin auditoría. Tiempo total: {elapsed:.2f}s")
            
            self.finished_audit.emit(results, stats)

        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"Error SQL: {e}" if "pyodbc" in str(e) or "SQL" in str(e) else f"Error FTP: {e}" if "ftp" in str(e).lower() else f"Error: {e}"
            logger.error(f"Error en AuditWorker: {e}", exc_info=True)
            self.log_message.emit(f"✗ {error_msg}")
            self.log_message.emit(f"Fin auditoría con error. Tiempo total: {elapsed:.2f}s")
            self.error_occurred.emit(error_msg)
