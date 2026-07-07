"""
Repositorio de operaciones Ecommerce contra SQL Server.

Encapsula todas las llamadas a Stored Procedures del ecommerce
en un único punto. Si un SP cambia de nombre o parámetros,
solo se modifica este archivo.

Todas las queries utilizan parámetros (?) para evitar inyección SQL
y errores de escape.
"""

from __future__ import annotations

import logging
from typing import Any

from services.sql_service import SqlService, SqlExecutionError

logger = logging.getLogger(__name__)

# ============================================================
# Nombres de Stored Procedures centralizados
# ============================================================

SP_PUBLICAR_ARTICULO = "eco_articulos_publi_web_actua"
SP_PUBLICAR_IMAGEN_ADICIONAL = "eco_articulos_imagenes_actua"

# ============================================================
# Nombres de tablas y campos
# ============================================================

TABLE_ARTICULOS = "ARTICULOS"
FIELD_COD_ARTICULO = "COD_ARTICULO"


class EcommerceRepository:
    """
    Repositorio que encapsula todas las operaciones de base de datos
    del ecommerce.

    Centraliza las llamadas a Stored Procedures y consultas directas.
    Si en el futuro cambia el nombre de un procedimiento almacenado
    o la estructura de la tabla, solo se modifica este archivo.

    Attributes:
        sql_service: Instancia del servicio SQL para ejecutar operaciones.

    Example:
        >>> repo = EcommerceRepository(sql_service)
        >>> if repo.existe_articulo("R123"):
        ...     repo.publicar_articulo("R123", "R123.jpg")
        ...     repo.publicar_imagen_adicional("R123", "R123_1.jpg", "_1")
    """

    def __init__(self, sql_service: SqlService) -> None:
        """
        Inicializa el repositorio con el servicio SQL.

        Args:
            sql_service: Instancia de SqlService conectada.
        """
        self._sql_service = sql_service

    # ================================================================
    # Consultas
    # ================================================================

    def existe_articulo(self, codigo: str) -> bool:
        """
        Verifica si un artículo existe en la base de datos.

        Ejecuta:
            SELECT COUNT(*) FROM ARTICULOS WHERE COD_ARTICULO = ?

        Args:
            codigo: Código del artículo a verificar (ej: 'R123').

        Returns:
            True si el artículo existe, False si no existe o hay error.
        """
        query = (
            f"SELECT COUNT(*) AS cantidad "
            f"FROM {TABLE_ARTICULOS} "
            f"WHERE {FIELD_COD_ARTICULO} = ?"
        )
        try:
            results = self._sql_service.execute(query, (codigo,))
            if results and "cantidad" in results[0]:
                count = results[0]["cantidad"]
                exists = count > 0
                logger.info(
                    f"Verificación artículo '{codigo}': "
                    f"{'existe' if exists else 'NO existe'} (count={count})"
                )
                return exists
            logger.warning(
                f"Verificación artículo '{codigo}': resultado inesperado."
            )
            return False

        except SqlExecutionError as e:
            logger.error(f"Error al verificar artículo '{codigo}': {e}")
            return False

    # ================================================================
    # Stored Procedures
    # ================================================================

    def publicar_articulo(self, codigo: str, imagen: str) -> bool:
        """
        Publica un artículo ejecutando el SP principal.

        Ejecuta:
            EXEC eco_articulos_publi_web_actua
                @cod_articulo = ?,
                @web_publi = ?,
                @web_imagen = ?

        Args:
            codigo: Código del artículo (ej: 'R123').
            imagen: Nombre de la imagen principal (ej: 'R123.jpg').

        Returns:
            True si la ejecución fue exitosa.

        Raises:
            SqlExecutionError: Si falla la ejecución del SP.
        """
        params: dict[str, Any] = {
            "cod_articulo": codigo,
            "web_publi": "S",
            "web_imagen": imagen,
        }

        try:
            self._sql_service.call_procedure(SP_PUBLICAR_ARTICULO, params)
            logger.info(
                f"SP {SP_PUBLICAR_ARTICULO} OK: "
                f"código='{codigo}', imagen='{imagen}'"
            )
            return True

        except SqlExecutionError as e:
            logger.error(
                f"SP {SP_PUBLICAR_ARTICULO} ERROR: "
                f"código='{codigo}', imagen='{imagen}' | {e}"
            )
            raise

    def publicar_imagen_adicional(
        self,
        codigo: str,
        imagen: str,
        indice: str,
    ) -> bool:
        """
        Publica una imagen adicional de un artículo.

        Ejecuta:
            EXEC eco_articulos_imagenes_actua
                @cod_articulo = ?,
                @web_imagen = ?,
                @indice = ?

        Args:
            codigo: Código del artículo (ej: 'R123').
            imagen: Nombre del archivo de imagen (ej: 'R123_1.jpg').
            indice: Índice de la imagen (ej: '_1', '_2').

        Returns:
            True si la ejecución fue exitosa.

        Raises:
            SqlExecutionError: Si falla la ejecución del SP.
        """
        params: dict[str, Any] = {
            "cod_articulo": codigo,
            "web_imagen": imagen,
            "indice": indice,
        }

        try:
            self._sql_service.call_procedure(SP_PUBLICAR_IMAGEN_ADICIONAL, params)
            logger.info(
                f"SP {SP_PUBLICAR_IMAGEN_ADICIONAL} OK: "
                f"código='{codigo}', imagen='{imagen}', indice='{indice}'"
            )
            return True

        except SqlExecutionError as e:
            logger.error(
                f"SP {SP_PUBLICAR_IMAGEN_ADICIONAL} ERROR: "
                f"código='{codigo}', imagen='{imagen}', indice='{indice}' | {e}"
            )
            raise

    def __repr__(self) -> str:
        return f"EcommerceRepository(sql={self._sql_service})"
