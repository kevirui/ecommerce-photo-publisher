import logging
import threading
import time
import tempfile
import shutil
from pathlib import Path
from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal
from services.ftp_service import FtpService, FtpServiceError

logger = logging.getLogger(__name__)


class FreeShippingWorker(QThread):
    """
    Worker que descarga, estampa y vuelve a subir (o restaura desde copia de seguridad)
    las fotos de los artículos seleccionados en segundo plano.
    """
    progress_updated = pyqtSignal(int, int)  # (actual, total)
    log_message = pyqtSignal(str)           # Mensajes para la consola de la UI
    finished_stamping = pyqtSignal(int, int) # (exitos, errores)
    error_occurred = pyqtSignal(str)        # Error fatal
    cancelled = pyqtSignal()                # Cancelación por usuario

    def __init__(
        self,
        ftp_service: FtpService,
        articles: list[dict],
        stamp_path: Path,
        action: str = "apply",  # "apply" o "remove"
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ftp_service = ftp_service
        self._articles = articles
        self._stamp_path = stamp_path
        self._action = action.lower()
        self._cancel_flag = threading.Event()

    def cancel(self) -> None:
        """Solicita la cancelación segura del proceso."""
        self._cancel_flag.set()
        logger.info(f"Cancelación de proceso de envío gratis ({self._action}) solicitada.")

    def run(self) -> None:
        """Hilo de ejecución principal."""
        if self._action == "apply" and not self._stamp_path.exists():
            self.error_occurred.emit(f"No se encontró el archivo del sello en: {self._stamp_path}")
            return

        success_count = 0
        error_count = 0
        total = len(self._articles)

        # Definir directorios de respaldo
        backend_backup_dir = Path(__file__).parent.parent.parent / "Backend" / "Respaldo_Imagenes"
        local_backup_dir = Path(__file__).parent.parent / "backups"
        local_backup_dir.mkdir(parents=True, exist_ok=True)

        self.log_message.emit(f"Iniciando acción '{self._action}' para {total} artículos...")

        try:
            # Asegurar conexión FTP
            if not self._ftp_service.is_connected:
                self.log_message.emit("Conectando al servidor FTP...")
                self._ftp_service.connect()

            for i, article in enumerate(self._articles):
                if self._cancel_flag.is_set():
                    self.log_message.emit("Proceso cancelado por el usuario.")
                    self.cancelled.emit()
                    return

                code = article["codigo"]
                remote_name = article["imagen"]

                self.progress_updated.emit(i, total)

                # Asegurar directorios
                try:
                    backend_backup_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                try:
                    local_backup_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass

                # Buscar si existe copia de respaldo sin sello
                backup_file = None
                if (backend_backup_dir / remote_name).exists():
                    backup_file = backend_backup_dir / remote_name
                elif (local_backup_dir / remote_name).exists():
                    backup_file = local_backup_dir / remote_name

                if self._action == "apply":
                    self.log_message.emit(f"[{i+1}/{total}] Descargando [{code}] ({remote_name})...")
                    try:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            local_temp_path = Path(tmpdir) / remote_name

                            # 1. Descargar imagen desde FTP
                            self._ftp_service.download_file(remote_name, local_temp_path)

                            # 2. Hacer copia de respaldo si no existe ya
                            if not backup_file:
                                try:
                                    # Intentar guardar en local_backup_dir
                                    dest_local = local_backup_dir / remote_name
                                    shutil.copy2(local_temp_path, dest_local)
                                    backup_file = dest_local

                                    # Intentar guardar también en backend_backup_dir
                                    try:
                                        dest_backend = backend_backup_dir / remote_name
                                        shutil.copy2(local_temp_path, dest_backend)
                                        backup_file = dest_backend
                                    except Exception:
                                        pass

                                    self.log_message.emit(f"   [Respaldo] Copia original guardada para [{code}] ✓")
                                except Exception as backup_err:
                                    logger.warning(f"No se pudo crear copia de respaldo para [{code}]: {backup_err}")

                            self.log_message.emit(f"   Aplicando sello a [{code}]...")

                            # 3. Cargar y estampar
                            with Image.open(local_temp_path) as img:
                                img = img.convert("RGBA")

                                with Image.open(self._stamp_path) as stamp:
                                    stamp = stamp.convert("RGBA")

                                    # Sello al 25% del ancho de la imagen principal
                                    stamp_w = int(img.width * 0.25)
                                    stamp_h = int(stamp.height * (stamp_w / stamp.width))
                                    stamp_resized = stamp.resize((stamp_w, stamp_h), Image.Resampling.LANCZOS)

                                    # Posicionar en esquina inferior derecha
                                    margin = 20
                                    x_offset = img.width - stamp_w - margin
                                    y_offset = img.height - stamp_h - margin

                                    # Pegar
                                    img.paste(stamp_resized, (x_offset, y_offset), mask=stamp_resized)

                                # Guardar de vuelta como JPG
                                final_img = img.convert("RGB")
                                final_img.save(local_temp_path, "JPEG", quality=85, optimize=True)

                            # 4. Subir de vuelta al FTP
                            self.log_message.emit(f"   Subiendo [{code}] estampado al FTP...")
                            self._ftp_service.upload_file(local_temp_path, remote_name)

                        self.log_message.emit(f"✓ [{code}] Sello aplicado con éxito.")
                        success_count += 1

                    except Exception as e:
                        logger.error(f"Error al estampar [{code}]: {e}", exc_info=True)
                        self.log_message.emit(f"✗ [{code}] Error: {e}")
                        error_count += 1

                elif self._action == "remove":
                    self.log_message.emit(f"[{i+1}/{total}] Restaurando [{code}] sin sello...")
                    try:
                        if backup_file and backup_file.exists():
                            # Subir directamente la copia de respaldo sin sello
                            self.log_message.emit(f"   Subiendo copia de respaldo original para [{code}]...")
                            self._ftp_service.upload_file(backup_file, remote_name)
                            self.log_message.emit(f"✓ [{code}] Sello removido (restaurado desde respaldo).")
                            success_count += 1
                        else:
                            # Si no hay respaldo local, intentamos descargarla del FTP y logear aviso,
                            # pero como el FTP ya está estampado no podemos "desestamparlo" de forma limpia.
                            self.log_message.emit(f"✗ [{code}] Error: No se encontró copia de seguridad original sin sello.")
                            error_count += 1
                    except Exception as e:
                        logger.error(f"Error al remover sello de [{code}]: {e}", exc_info=True)
                        self.log_message.emit(f"✗ [{code}] Error: {e}")
                        error_count += 1

            self.progress_updated.emit(total, total)
            self.finished_stamping.emit(success_count, error_count)

        except Exception as e:
            logger.error(f"Error general en FreeShippingWorker: {e}", exc_info=True)
            self.error_occurred.emit(f"Error de conexión FTP o general: {e}")
