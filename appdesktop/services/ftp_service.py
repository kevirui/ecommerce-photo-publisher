"""
Servicio de conexión y transferencia FTP.

Provee métodos para conectar, subir archivos con reintentos y backoff
exponencial, verificar existencia de archivos remotos, y subir múltiples
archivos en paralelo mediante ThreadPoolExecutor.
"""

from __future__ import annotations

import ftplib
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class FtpServiceError(Exception):
    """Excepción base para errores del servicio FTP."""
    pass


# Tupla con todos los errores FTP posibles y OSError para evitar excepciones por tuplas anidadas
FTP_ERRORS = (
    ftplib.error_reply,
    ftplib.error_temp,
    ftplib.error_perm,
    ftplib.error_proto,
    OSError,
)



class FtpConnectionError(FtpServiceError):
    """Error de conexión al servidor FTP."""
    pass


class FtpUploadError(FtpServiceError):
    """Error al subir un archivo al servidor FTP."""
    pass


class FtpService:
    """
    Servicio de conexión y transferencia de archivos vía FTP.

    Soporta subidas con reintentos automáticos y backoff exponencial,
    verificación de archivos remotos, eliminación, y uploads paralelos
    mediante ThreadPoolExecutor.

    Attributes:
        host: Dirección del servidor FTP.
        port: Puerto del servidor FTP.
        username: Usuario FTP.
        password: Contraseña FTP.
        remote_path: Ruta remota base donde se suben los archivos.
        timeout: Timeout en segundos para operaciones FTP.
        max_retries: Cantidad máxima de reintentos ante fallos.

    Example:
        >>> ftp = FtpService("ftp.example.com", 21, "user", "pass", "/img/articulos")
        >>> ftp.connect()
        True
        >>> ftp.upload_file(Path("R123.jpg"), "R123.jpg")
        True
        >>> ftp.disconnect()
    """

    def __init__(
        self,
        host: str,
        port: int = 21,
        username: str = "",
        password: str = "",
        remote_path: str = "/",
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """
        Inicializa el servicio FTP con los parámetros de conexión.

        Args:
            host: Dirección del servidor FTP.
            port: Puerto del servidor FTP (default: 21).
            username: Usuario FTP.
            password: Contraseña FTP.
            remote_path: Ruta remota base para uploads.
            timeout: Timeout en segundos (default: 30).
            max_retries: Máximo de reintentos ante fallos (default: 3).
        """
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._remote_path = remote_path
        self._timeout = timeout
        self._max_retries = max_retries
        self._ftp: Optional[ftplib.FTP] = None

    # ================================================================
    # Propiedades
    # ================================================================

    @property
    def is_connected(self) -> bool:
        """Indica si hay una conexión FTP activa."""
        if self._ftp is None:
            return False
        try:
            self._ftp.voidcmd("NOOP")
            return True
        except (ftplib.error_reply, ftplib.error_temp, ftplib.error_perm,
                OSError, EOFError):
            self._ftp = None
            return False

    @property
    def host(self) -> str:
        """Dirección del servidor FTP."""
        return self._host

    @property
    def remote_path(self) -> str:
        """Ruta remota base."""
        return self._remote_path

    @property
    def max_retries(self) -> int:
        """Cantidad máxima de reintentos."""
        return self._max_retries

    # ================================================================
    # Conexión / Desconexión
    # ================================================================

    def connect(self) -> bool:
        """
        Establece una conexión con el servidor FTP.

        Returns:
            True si la conexión fue exitosa.

        Raises:
            FtpConnectionError: Si no se puede conectar.
        """
        if self._ftp is not None:
            logger.warning("Ya existe una conexión FTP activa. Se desconectará primero.")
            self.disconnect()

        start_time = time.time()
        try:
            logger.info(f"Conectando a FTP: {self._host}:{self._port}")

            self._ftp = ftplib.FTP()
            self._ftp.connect(
                host=self._host,
                port=self._port,
                timeout=self._timeout,
            )
            self._ftp.login(
                user=self._username,
                passwd=self._password,
            )

            # Modo binario por defecto
            self._ftp.sendcmd("TYPE I")

            # Navegar al directorio remoto
            if self._remote_path and self._remote_path != "/":
                self._ftp.cwd(self._remote_path)
                logger.debug(f"FTP CWD: {self._remote_path}")

            elapsed = time.time() - start_time
            logger.info(
                f"Conexión FTP exitosa a {self._host}:{self._port} "
                f"(ruta: {self._remote_path}, {elapsed:.2f}s)"
            )
            return True

        except FTP_ERRORS as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Error al conectar a FTP: {error_msg} ({elapsed:.2f}s)")
            self._ftp = None
            raise FtpConnectionError(f"No se pudo conectar al FTP: {error_msg}")

    def disconnect(self) -> None:
        """Cierra la conexión FTP activa si existe."""
        if self._ftp is not None:
            try:
                self._ftp.quit()
                logger.info("Conexión FTP cerrada correctamente (QUIT).")
            except FTP_ERRORS:
                try:
                    self._ftp.close()
                    logger.info("Conexión FTP cerrada forzosamente (CLOSE).")
                except Exception:
                    pass
            finally:
                self._ftp = None

    def test_connection(self) -> bool:
        """
        Prueba la conexión FTP ejecutando PWD.

        Returns:
            True si la prueba es exitosa, False en caso contrario.
        """
        try:
            if self._ftp is None:
                self.connect()

            pwd = self._ftp.pwd()
            logger.info(f"Test de conexión FTP exitoso. PWD: {pwd}")
            return True

        except (FtpConnectionError, *FTP_ERRORS) as e:
            logger.error(f"Test de conexión FTP fallido: {e}")
            return False

    def _ensure_connected(self) -> None:
        """
        Verifica que hay conexión activa y reconecta si es necesario.

        Raises:
            FtpConnectionError: Si no se puede restablecer la conexión.
        """
        if not self.is_connected:
            logger.warning("Conexión FTP perdida. Intentando reconexión...")
            self.connect()

    # ================================================================
    # Operaciones de archivos
    # ================================================================

    def upload_file(self, local_path: Path, remote_name: str) -> bool:
        """
        Sube un archivo local al servidor FTP con reintentos.

        Args:
            local_path: Ruta local completa al archivo.
            remote_name: Nombre del archivo en el servidor remoto.

        Returns:
            True si la subida fue exitosa.

        Raises:
            FtpUploadError: Si falla después de todos los reintentos.
            FileNotFoundError: Si el archivo local no existe.
        """
        if not local_path.exists():
            raise FileNotFoundError(f"Archivo local no encontrado: {local_path}")

        file_size = local_path.stat().st_size
        file_size_kb = file_size / 1024

        return self._retry(
            self._upload_file_single,
            local_path,
            remote_name,
            file_size_kb,
        )

    def _upload_file_single(
        self,
        local_path: Path,
        remote_name: str,
        file_size_kb: float,
    ) -> bool:
        """
        Ejecuta una subida FTP individual (sin reintentos).

        Args:
            local_path: Ruta local al archivo.
            remote_name: Nombre remoto del archivo.
            file_size_kb: Tamaño del archivo en KB (para logging).

        Returns:
            True si la subida fue exitosa.
        """
        self._ensure_connected()

        start_time = time.time()
        with open(local_path, "rb") as file_handle:
            self._ftp.storbinary(f"STOR {remote_name}", file_handle)

        elapsed = time.time() - start_time
        logger.info(
            f"FTP Upload OK: {remote_name} "
            f"({file_size_kb:.1f} KB, {elapsed:.2f}s)"
        )
        return True

    def upload_files_parallel(
        self,
        files: list[tuple[Path, str]],
        max_workers: int = 4,
        progress_callback: Optional[Callable[[str, bool], None]] = None,
    ) -> dict[str, bool]:
        """
        Sube múltiples archivos en paralelo mediante ThreadPoolExecutor.

        Cada hilo crea su propia conexión FTP para evitar conflictos.

        Args:
            files: Lista de tuplas (ruta_local, nombre_remoto).
            max_workers: Cantidad máxima de hilos paralelos.
            progress_callback: Función callback(remote_name, success) llamada
                              por cada archivo completado.

        Returns:
            Diccionario {nombre_remoto: True/False} con el resultado de cada archivo.
        """
        results: dict[str, bool] = {}

        if not files:
            return results

        logger.info(
            f"FTP Upload paralelo: {len(files)} archivos, "
            f"{max_workers} hilos máximo"
        )

        def _upload_in_thread(local_path: Path, remote_name: str) -> tuple[str, bool]:
            """Función ejecutada en cada hilo del pool."""
            thread_ftp: Optional[ftplib.FTP] = None
            try:
                # Crear conexión FTP propia para este hilo
                thread_ftp = ftplib.FTP()
                thread_ftp.connect(
                    host=self._host,
                    port=self._port,
                    timeout=self._timeout,
                )
                thread_ftp.login(user=self._username, passwd=self._password)
                thread_ftp.sendcmd("TYPE I")

                if self._remote_path and self._remote_path != "/":
                    thread_ftp.cwd(self._remote_path)

                start_time = time.time()
                with open(local_path, "rb") as f:
                    thread_ftp.storbinary(f"STOR {remote_name}", f)

                elapsed = time.time() - start_time
                file_size_kb = local_path.stat().st_size / 1024
                logger.info(
                    f"FTP Upload OK (paralelo): {remote_name} "
                    f"({file_size_kb:.1f} KB, {elapsed:.2f}s)"
                )
                return remote_name, True

            except (FileNotFoundError, *FTP_ERRORS) as e:
                logger.error(f"FTP Upload ERROR (paralelo): {remote_name} | {e}")
                return remote_name, False

            finally:
                if thread_ftp is not None:
                    try:
                        thread_ftp.quit()
                    except Exception:
                        try:
                            thread_ftp.close()
                        except Exception:
                            pass

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_upload_in_thread, local_path, remote_name): remote_name
                for local_path, remote_name in files
            }

            for future in as_completed(futures):
                remote_name, success = future.result()
                results[remote_name] = success
                if progress_callback:
                    progress_callback(remote_name, success)

        successful = sum(1 for v in results.values() if v)
        failed = len(results) - successful
        logger.info(
            f"FTP Upload paralelo completado: "
            f"{successful} exitosos, {failed} fallidos de {len(results)} total"
        )

        return results

    def exists(self, remote_name: str) -> bool:
        """
        Verifica si un archivo existe en el servidor FTP.

        Args:
            remote_name: Nombre del archivo a verificar.

        Returns:
            True si el archivo existe en el directorio remoto.
        """
        try:
            self._ensure_connected()
            file_list = self._ftp.nlst()
            found = remote_name in file_list
            logger.debug(
                f"FTP exists('{remote_name}'): "
                f"{'encontrado' if found else 'no encontrado'}"
            )
            return found
        except FTP_ERRORS as e:
            logger.error(f"Error al verificar existencia FTP de '{remote_name}': {e}")
            return False

    def list_remote_files(self) -> set[str]:
        """
        Lista todos los archivos en el directorio remoto actual.

        Útil para cachear la lista y evitar múltiples NLST.

        Returns:
            Conjunto de nombres de archivo en el directorio remoto.
        """
        try:
            self._ensure_connected()
            file_list = self._ftp.nlst()
            result = set(file_list)
            logger.debug(f"FTP list_remote_files: {len(result)} archivos encontrados")
            return result
        except FTP_ERRORS as e:
            logger.error(f"Error al listar archivos FTP: {e}")
            return set()

    def delete(self, remote_name: str) -> bool:
        """
        Elimina un archivo del servidor FTP.

        Args:
            remote_name: Nombre del archivo a eliminar.

        Returns:
            True si la eliminación fue exitosa, False en caso contrario.
        """
        try:
            self._ensure_connected()
            self._ftp.delete(remote_name)
            logger.info(f"FTP Delete OK: {remote_name}")
            return True
        except FTP_ERRORS as e:
            logger.error(f"Error al eliminar FTP '{remote_name}': {e}")
            return False

    # ================================================================
    # Reintentos
    # ================================================================

    def _retry(self, func: Callable, *args, **kwargs) -> bool:
        """
        Ejecuta una función con reintentos y backoff exponencial.

        Si la función falla, espera 1s, 2s, 4s... entre reintentos.
        Intenta reconectar antes de cada reintento.

        Args:
            func: Función a ejecutar.
            *args: Argumentos posicionales para la función.
            **kwargs: Argumentos nombrados para la función.

        Returns:
            True si la función se ejecutó exitosamente.

        Raises:
            FtpUploadError: Si falla después de todos los reintentos.
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (FtpConnectionError, *FTP_ERRORS) as e:
                last_error = e
                if attempt < self._max_retries:
                    wait_time = 2 ** (attempt - 1)  # 1s, 2s, 4s...
                    logger.warning(
                        f"FTP reintento {attempt}/{self._max_retries}: {e} "
                        f"(esperando {wait_time}s)"
                    )
                    time.sleep(wait_time)

                    # Intentar reconexión
                    try:
                        self.disconnect()
                        self.connect()
                    except FtpConnectionError:
                        logger.error("FTP: Reconexión fallida en reintento.")
                else:
                    logger.error(
                        f"FTP: Todos los reintentos agotados ({self._max_retries}). "
                        f"Último error: {e}"
                    )

        raise FtpUploadError(
            f"Fallo después de {self._max_retries} reintentos. "
            f"Último error: {last_error}"
        )

    # ================================================================
    # Context Manager
    # ================================================================

    def __enter__(self) -> FtpService:
        """Permite usar FtpService con la sentencia 'with'."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cierra la conexión al salir del contexto."""
        self.disconnect()

    def __repr__(self) -> str:
        status = "conectado" if self.is_connected else "desconectado"
        return f"FtpService(host='{self._host}', path='{self._remote_path}', {status})"
