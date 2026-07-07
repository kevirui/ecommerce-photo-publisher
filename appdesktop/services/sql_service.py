"""
Servicio de conexión a SQL Server mediante pyodbc.

Provee métodos para conectar, desconectar, ejecutar queries y
llamar Stored Procedures con parámetros seguros (nunca concatenación).
Implementa autodetección del driver ODBC disponible y soporte
para transacciones con begin/commit/rollback.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import pyodbc

logger = logging.getLogger(__name__)

# Drivers ODBC en orden de preferencia para autodetección
ODBC_DRIVERS = [
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server",
]


class SqlServiceError(Exception):
    """Excepción base para errores del servicio SQL."""
    pass


class SqlConnectionError(SqlServiceError):
    """Error de conexión a SQL Server."""
    pass


class SqlExecutionError(SqlServiceError):
    """Error al ejecutar una query o Stored Procedure."""
    pass


class SqlService:
    """
    Servicio de conexión y ejecución de queries contra SQL Server.

    Utiliza pyodbc para establecer conexiones, ejecutar queries parametrizadas
    y llamar Stored Procedures. Nunca construye SQL por concatenación de cadenas.

    Attributes:
        server: Nombre o IP del servidor SQL Server.
        database: Nombre de la base de datos.
        username: Usuario de SQL Server.
        password: Contraseña de SQL Server.

    Example:
        >>> sql = SqlService("localhost", "MiDB", "sa", "pass123")
        >>> sql.connect()
        True
        >>> results = sql.execute("SELECT * FROM ARTICULOS WHERE COD_ARTICULO = ?", ("R123",))
        >>> sql.disconnect()
    """

    def __init__(
        self,
        server: str,
        database: str,
        username: str,
        password: str,
    ) -> None:
        """
        Inicializa el servicio SQL con las credenciales de conexión.

        Args:
            server: Nombre o IP del servidor SQL Server.
            database: Nombre de la base de datos.
            username: Usuario de SQL Server.
            password: Contraseña de SQL Server.
        """
        self._server = server
        self._database = database
        self._username = username
        self._password = password
        self._connection: Optional[pyodbc.Connection] = None
        self._driver: Optional[str] = None

    # ================================================================
    # Propiedades
    # ================================================================

    @property
    def is_connected(self) -> bool:
        """Indica si hay una conexión activa a SQL Server."""
        if self._connection is None:
            return False
        try:
            # Verificar que la conexión sigue viva
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except (pyodbc.Error, Exception):
            self._connection = None
            return False

    @property
    def server(self) -> str:
        """Nombre del servidor SQL."""
        return self._server

    @property
    def database(self) -> str:
        """Nombre de la base de datos."""
        return self._database

    # ================================================================
    # Conexión / Desconexión
    # ================================================================

    def _detect_driver(self) -> str:
        """
        Detecta el driver ODBC disponible en el sistema.

        Returns:
            Nombre del driver ODBC encontrado.

        Raises:
            SqlConnectionError: Si no se encuentra ningún driver compatible.
        """
        available_drivers = pyodbc.drivers()
        logger.debug(f"Drivers ODBC disponibles: {available_drivers}")

        for driver in ODBC_DRIVERS:
            if driver in available_drivers:
                logger.info(f"Driver ODBC seleccionado: {driver}")
                return driver

        raise SqlConnectionError(
            f"No se encontró ningún driver ODBC compatible. "
            f"Drivers disponibles: {available_drivers}. "
            f"Se requiere uno de: {ODBC_DRIVERS}"
        )

    def _build_connection_string(self) -> str:
        """
        Construye la cadena de conexión ODBC.

        Returns:
            Cadena de conexión formateada para pyodbc.
        """
        if self._driver is None:
            self._driver = self._detect_driver()

        conn_str = (
            f"DRIVER={{{self._driver}}};"
            f"SERVER={self._server};"
            f"DATABASE={self._database};"
            f"UID={self._username};"
            f"PWD={self._password};"
        )

        # Para ODBC Driver 18, agregar TrustServerCertificate
        if "18" in self._driver:
            conn_str += "TrustServerCertificate=yes;"

        return conn_str

    def connect(self) -> bool:
        """
        Establece una conexión con SQL Server.

        Returns:
            True si la conexión fue exitosa.

        Raises:
            SqlConnectionError: Si no se puede conectar.
        """
        if self._connection is not None:
            logger.warning("Ya existe una conexión activa. Se desconectará primero.")
            self.disconnect()

        start_time = time.time()
        try:
            conn_str = self._build_connection_string()
            logger.info(f"Conectando a SQL Server: {self._server}/{self._database}")

            self._connection = pyodbc.connect(conn_str, timeout=10)
            self._connection.autocommit = True

            elapsed = time.time() - start_time
            logger.info(
                f"Conexión SQL exitosa a {self._server}/{self._database} "
                f"(driver: {self._driver}, {elapsed:.2f}s)"
            )
            return True

        except pyodbc.Error as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            logger.error(
                f"Error al conectar a SQL Server: {error_msg} ({elapsed:.2f}s)"
            )
            self._connection = None
            raise SqlConnectionError(f"No se pudo conectar a SQL Server: {error_msg}")

    def disconnect(self) -> None:
        """Cierra la conexión activa con SQL Server si existe."""
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("Conexión SQL cerrada correctamente.")
            except pyodbc.Error as e:
                logger.warning(f"Error al cerrar conexión SQL: {e}")
            finally:
                self._connection = None

    def test_connection(self) -> bool:
        """
        Prueba la conexión ejecutando SELECT 1.

        Returns:
            True si la prueba es exitosa, False en caso contrario.
        """
        try:
            if self._connection is None:
                self.connect()

            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()

            is_ok = result is not None and result[0] == 1
            if is_ok:
                logger.info("Test de conexión SQL exitoso.")
            else:
                logger.warning("Test de conexión SQL: resultado inesperado.")
            return is_ok

        except (pyodbc.Error, SqlConnectionError) as e:
            logger.error(f"Test de conexión SQL fallido: {e}")
            return False

    # ================================================================
    # Ejecución de queries
    # ================================================================

    def execute(
        self,
        query: str,
        params: Optional[tuple] = None,
    ) -> list[dict[str, Any]]:
        """
        Ejecuta una query parametrizada y retorna los resultados como lista de dicts.

        IMPORTANTE: Siempre usar parámetros (?). Nunca concatenar cadenas SQL.

        Args:
            query: Query SQL con placeholders ? para parámetros.
            params: Tupla de valores para los placeholders.

        Returns:
            Lista de diccionarios con los resultados. Cada dict mapea
            nombre_columna → valor. Lista vacía si no hay resultados.

        Raises:
            SqlExecutionError: Si ocurre un error durante la ejecución.
            SqlConnectionError: Si no hay conexión activa.

        Example:
            >>> results = sql.execute(
            ...     "SELECT * FROM ARTICULOS WHERE COD_ARTICULO = ?",
            ...     ("R123",)
            ... )
        """
        if self._connection is None:
            raise SqlConnectionError("No hay conexión activa a SQL Server.")

        start_time = time.time()
        try:
            cursor = self._connection.cursor()

            if params:
                logger.debug(f"SQL Execute: {query} | Params: {params}")
                cursor.execute(query, params)
            else:
                logger.debug(f"SQL Execute: {query}")
                cursor.execute(query)

            # Verificar si hay resultados disponibles
            results: list[dict[str, Any]] = []
            if cursor.description is not None:
                columns = [column[0] for column in cursor.description]
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))

            cursor.close()

            elapsed = time.time() - start_time
            logger.debug(
                f"SQL Execute completado: {len(results)} filas ({elapsed:.3f}s)"
            )
            return results

        except pyodbc.Error as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            logger.error(
                f"Error SQL Execute: {error_msg} | Query: {query} ({elapsed:.3f}s)"
            )
            raise SqlExecutionError(f"Error al ejecutar query: {error_msg}")

    def call_procedure(
        self,
        name: str,
        params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Ejecuta un Stored Procedure con parámetros nombrados.

        Construye la llamada EXEC con parámetros ? de pyodbc.
        Nunca concatena valores en la cadena SQL.

        Args:
            name: Nombre del Stored Procedure.
            params: Diccionario de parámetros {nombre: valor}.

        Returns:
            Lista de diccionarios con los resultados, o lista vacía.

        Raises:
            SqlExecutionError: Si ocurre un error durante la ejecución.
            SqlConnectionError: Si no hay conexión activa.

        Example:
            >>> sql.call_procedure(
            ...     "eco_articulos_publi_web_actua",
            ...     {"cod_articulo": "R123", "web_publi": "S", "web_imagen": "R123.jpg"}
            ... )
        """
        if self._connection is None:
            raise SqlConnectionError("No hay conexión activa a SQL Server.")

        start_time = time.time()
        try:
            if params:
                # Construir EXEC con parámetros nombrados usando ?
                param_placeholders = ", ".join(
                    f"@{key}=?" for key in params.keys()
                )
                query = f"EXEC {name} {param_placeholders}"
                param_values = tuple(params.values())

                logger.info(
                    f"SQL Procedure: EXEC {name} | Params: {params}"
                )
            else:
                query = f"EXEC {name}"
                param_values = None
                logger.info(f"SQL Procedure: EXEC {name}")

            cursor = self._connection.cursor()

            if param_values:
                cursor.execute(query, param_values)
            else:
                cursor.execute(query)

            # Recoger resultados si los hay
            results: list[dict[str, Any]] = []
            if cursor.description is not None:
                columns = [column[0] for column in cursor.description]
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))

            cursor.close()

            elapsed = time.time() - start_time
            logger.info(
                f"SQL Procedure completado: EXEC {name} "
                f"({len(results)} filas, {elapsed:.3f}s)"
            )
            return results

        except pyodbc.Error as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            logger.error(
                f"Error SQL Procedure: EXEC {name} | {error_msg} ({elapsed:.3f}s)"
            )
            raise SqlExecutionError(
                f"Error al ejecutar procedimiento '{name}': {error_msg}"
            )

    # ================================================================
    # Transacciones
    # ================================================================

    def begin_transaction(self) -> None:
        """
        Inicia una transacción explícita.

        Desactiva autocommit para que los cambios no se apliquen
        hasta que se llame a commit() o rollback().

        Raises:
            SqlConnectionError: Si no hay conexión activa.
        """
        if self._connection is None:
            raise SqlConnectionError("No hay conexión activa a SQL Server.")

        self._connection.autocommit = False
        logger.debug("Transacción SQL iniciada (autocommit=False).")

    def commit(self) -> None:
        """
        Confirma la transacción actual y reactiva autocommit.

        Raises:
            SqlConnectionError: Si no hay conexión activa.
            SqlExecutionError: Si ocurre un error durante el commit.
        """
        if self._connection is None:
            raise SqlConnectionError("No hay conexión activa a SQL Server.")

        try:
            self._connection.commit()
            self._connection.autocommit = True
            logger.debug("Transacción SQL confirmada (commit).")
        except pyodbc.Error as e:
            logger.error(f"Error al hacer commit: {e}")
            raise SqlExecutionError(f"Error en commit: {e}")

    def rollback(self) -> None:
        """
        Revierte la transacción actual y reactiva autocommit.

        Raises:
            SqlConnectionError: Si no hay conexión activa.
        """
        if self._connection is None:
            raise SqlConnectionError("No hay conexión activa a SQL Server.")

        try:
            self._connection.rollback()
            self._connection.autocommit = True
            logger.warning("Transacción SQL revertida (rollback).")
        except pyodbc.Error as e:
            logger.error(f"Error al hacer rollback: {e}")

    # ================================================================
    # Context Manager
    # ================================================================

    def __enter__(self) -> SqlService:
        """Permite usar SqlService con la sentencia 'with'."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cierra la conexión al salir del contexto."""
        self.disconnect()

    def __repr__(self) -> str:
        status = "conectado" if self.is_connected else "desconectado"
        return f"SqlService(server='{self._server}', db='{self._database}', {status})"
