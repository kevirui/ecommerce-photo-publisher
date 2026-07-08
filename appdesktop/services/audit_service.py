"""
Servicio de Auditoría de Artículos e Imágenes.

Verifica la consistencia entre SQL Server (tablas ARTICULOS y ARTICULOS_IMAGENES)
y los archivos alojados en el servidor FTP, identificando artículos correctos,
pendientes, errores por falta de imagen principal, advertencias por imágenes
adicionales faltantes, e imágenes huérfanas en el FTP.
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple, Set
from openpyxl import Workbook

from services.sql_service import SqlService
from services.ftp_service import FtpService

logger = logging.getLogger(__name__)


def extract_base_code(filename: str) -> str:
    """
    Extrae el código base del artículo a partir del nombre del archivo.
    Ejemplos:
        "R123.jpg" -> "R123"
        "R123_1.jpg" -> "R123"
        "R123_2.png" -> "R123"
    """
    # Quitar la extensión
    name_without_ext = filename.rsplit(".", 1)[0]
    # Comprobar si termina en _<número> y extraer el prefijo
    match = re.match(r"^(.+?)_\d+$", name_without_ext)
    if match:
        return match.group(1).upper()
    return name_without_ext.upper()


class AuditService:
    """
    Servicio encargado de ejecutar la lógica de auditoría entre la base de datos
    SQL Server y el repositorio FTP de imágenes.
    """

    def __init__(self, sql_service: SqlService, ftp_service: FtpService) -> None:
        """
        Inicializa el servicio de auditoría.
        """
        self._sql_service = sql_service
        self._ftp_service = ftp_service

    def run_audit(
        self,
        mode: str,  # 'sql', 'ftp', 'all'
        progress_callback=None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Ejecuta el proceso de auditoría y retorna los resultados y estadísticas.
        """
        results: List[Dict[str, Any]] = []
        
        # Estructuras de soporte
        ftp_files: Set[str] = set()
        db_articles: List[Dict[str, Any]] = []
        additional_images_by_code: Dict[str, List[str]] = {}
        all_db_codes: Set[str] = set()

        # 1. Obtener listado FTP si corresponde (modos 'ftp' o 'all')
        if mode in ("ftp", "all"):
            if self._ftp_service.is_connected:
                logger.info("Obteniendo listado de archivos del FTP...")
                ftp_files = self._ftp_service.list_remote_files()
                # Pasar todo a mayúsculas para comparación case-insensitive segura
                ftp_files = {f.upper() for f in ftp_files if f}
                logger.info(f"Se listaron {len(ftp_files)} archivos del FTP.")
            else:
                logger.warning("FTP no conectado. Saltando validaciones de FTP.")

        # 2. Consultar Base de Datos si corresponde (modos 'sql' o 'all')
        if mode in ("sql", "all"):
            logger.info("Consultando artículos de la base de datos...")
            
            # Traer artículos con count de adicionales
            query_articles = """
            SELECT
                A.COD_ARTICULO,
                A.DESCRIP_ARTI,
                A.WEB_PUBLI,
                A.WEB_LINK,
                A.WEB_IMAGEN_PROVE,
                COUNT(I.COD_ARTICULO) AS IMAGENES
            FROM ARTICULOS A
            LEFT JOIN ARTICULOS_IMAGENES I
                ON A.COD_ARTICULO = I.COD_ARTICULO
            GROUP BY
                A.COD_ARTICULO,
                A.DESCRIP_ARTI,
                A.WEB_PUBLI,
                A.WEB_LINK,
                A.WEB_IMAGEN_PROVE
            """
            
            db_articles = self._sql_service.execute(query_articles)
            
            # Consultar los nombres de imágenes adicionales específicas registradas
            logger.info("Consultando detalles de imágenes adicionales de la base de datos...")
            query_adicionales = "SELECT COD_ARTICULO, IMAGEN FROM ARTICULOS_IMAGENES"
            adicionales_res = self._sql_service.execute(query_adicionales)
            
            for row in adicionales_res:
                cod = str(row.get("COD_ARTICULO", "")).strip().upper()
                img_raw = str(row.get("IMAGEN", "")).strip()
                # La columna IMAGEN almacena URLs completas; extraer solo el nombre del archivo
                if "/" in img_raw:
                    img = img_raw.rsplit("/", 1)[-1].upper()
                else:
                    img = img_raw.upper()
                if cod and img:
                    if cod not in additional_images_by_code:
                        additional_images_by_code[cod] = []
                    additional_images_by_code[cod].append(img)

            # Obtener conjunto de códigos de artículos en BD para detección de huérfanos
            all_db_codes = {str(row.get("COD_ARTICULO", "")).strip().upper() for row in db_articles}

        # 3. Procesar Auditoría por Artículos
        total_items = len(db_articles)
        for i, art in enumerate(db_articles):
            code = str(art.get("COD_ARTICULO", "")).strip().upper()
            descrip = art.get("DESCRIP_ARTI", "")
            web_publi = art.get("WEB_PUBLI", "")
            web_link = art.get("WEB_LINK", "")
            web_img = str(art.get("WEB_IMAGEN_PROVE", "")).strip().upper()

            # Extraer el conteo de adicionales
            known_keys = {"COD_ARTICULO", "DESCRIP_ARTI", "WEB_PUBLI", "WEB_LINK", "WEB_IMAGEN_PROVE"}
            count_key = next((k for k in art.keys() if k not in known_keys), None)
            cant_adicionales_sql = int(art[count_key]) if count_key is not None and art[count_key] is not None else 0

            # Validar existencia de imagen principal en FTP
            main_img_exists = False
            main_img_status_text = "No verificado"
            if mode in ("all",):
                if web_img:
                    main_img_exists = (web_img in ftp_files)
                    main_img_status_text = "Sí" if main_img_exists else "No"
                else:
                    main_img_status_text = "Vacío"
            elif mode == "sql":
                main_img_status_text = "No verificado"

            # Validar imágenes adicionales
            missing_adicionales: List[str] = []
            registered_adicionales = additional_images_by_code.get(code, [])

            if mode in ("all",):
                for img_ad in registered_adicionales:
                    if img_ad not in ftp_files:
                        missing_adicionales.append(img_ad)

            # Clasificación de Reglas
            estado = "PENDIENTE"
            observaciones = ""

            is_publi = (web_publi == "S")

            if not is_publi:
                estado = "PENDIENTE"
                observaciones = "Artículo no marcado para publicar."
            else:
                # Está publicado (WEB_PUBLI = 'S')
                if mode == "all":
                    has_main_on_ftp = (web_img and web_img in ftp_files)
                    has_additional_on_ftp = any(img in ftp_files for img in registered_adicionales)
                    has_any_image_on_ftp = has_main_on_ftp or has_additional_on_ftp

                    if not has_any_image_on_ftp:
                        estado = "ERROR"
                        if not web_img and cant_adicionales_sql == 0:
                            observaciones = "Marcado para publicar pero no tiene ninguna imagen registrada en la base de datos."
                        else:
                            observaciones = "No tiene ninguna imagen (principal o adicional) cargada en el FTP."
                    else:
                        # Tiene al menos una imagen en el FTP
                        web_img_missing = (web_img and not has_main_on_ftp)
                        if web_img_missing or missing_adicionales:
                            estado = "ADVERTENCIA"
                            missing_parts = []
                            if web_img_missing:
                                missing_parts.append(f"principal '{web_img}'")
                            if missing_adicionales:
                                missing_parts.append(f"adicional(es) {', '.join(missing_adicionales)}")
                            observaciones = f"Publicado (habilitado) pero falta: {', '.join(missing_parts)} en FTP."
                        else:
                            estado = "CORRECTO"
                            observaciones = "Publicado correctamente con todas sus imágenes registradas en FTP."
                else:
                    # Modo SQL (no verifica FTP)
                    has_any_image_registered = bool(web_img) or (cant_adicionales_sql > 0)
                    if not has_any_image_registered:
                        estado = "ERROR"
                        observaciones = "Marcado para publicar pero no tiene ninguna imagen (principal o adicional) registrada."
                    else:
                        estado = "CORRECTO"
                        observaciones = "Configurado correctamente con imágenes en la base de datos."

            results.append({
                "codigo": code,
                "descripcion": descrip if descrip else "",
                "publicado": web_publi if web_publi else "N",
                "imagen_principal": web_img,
                "existe_ftp": main_img_status_text,
                "cant_adicionales": cant_adicionales_sql,
                "estado": estado,
                "observaciones": observaciones,
                "web_link": web_link if web_link else ""
            })

            if progress_callback and (i % max(1, total_items // 50) == 0 or i == total_items - 1):
                progress_callback(i + 1, total_items)

        # 4. Procesar Imágenes Huérfanas (solo modos 'ftp' y 'all')
        orphan_count = 0
        if mode in ("ftp", "all") and ftp_files:
            # Si sólo auditamos FTP, creamos el set de códigos a partir de una consulta simple de BD
            if mode == "ftp":
                logger.info("Obteniendo códigos de artículos de la base de datos para auditoría de huérfanos...")
                try:
                    db_codes_res = self._sql_service.execute("SELECT COD_ARTICULO FROM ARTICULOS")
                    all_db_codes = {str(row.get("COD_ARTICULO", "")).strip().upper() for row in db_codes_res}
                except Exception as e:
                    logger.error(f"Error cargando códigos para huérfanos: {e}")
            
            # Validar archivos FTP contra el set de códigos
            logger.info("Buscando imágenes huérfanas en el listado FTP...")
            for f in ftp_files:
                # Ignorar carpetas o archivos que no sean imágenes típicas
                if not f.endswith((".JPG", ".JPEG", ".PNG", ".GIF", ".WEBP")):
                    continue

                base_code = extract_base_code(f)
                if base_code not in all_db_codes:
                    # Es una imagen huérfana
                    results.append({
                        "codigo": f,  # Mostrar nombre del archivo como código
                        "descripcion": "Archivo huérfano en FTP",
                        "publicado": "",
                        "imagen_principal": "",
                        "existe_ftp": "Sí",
                        "cant_adicionales": 0,
                        "estado": "HUÉRFANA",
                        "observaciones": f"El archivo existe en FTP pero no está registrado en ningún artículo (Código base: {base_code}).",
                        "web_link": ""
                    })
                    orphan_count += 1

        # Generar estadísticas finales
        stats = self._compute_stats(results, mode)
        return results, stats

    def _compute_stats(self, results: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
        """Calcula estadísticas agregadas sobre los resultados de la auditoría."""
        total = len(results)
        correctos = sum(1 for item in results if item.get("estado") == "CORRECTO")
        pendientes = sum(1 for item in results if item.get("estado") == "PENDIENTE")
        errores = sum(1 for item in results if item.get("estado") == "ERROR")
        advertencias = sum(1 for item in results if item.get("estado") == "ADVERTENCIA")
        huerfanos = sum(1 for item in results if item.get("estado") == "HUÉRFANA")

        return {
            "total": total,
            "correctos": correctos,
            "pendientes": pendientes,
            "errores": errores,
            "advertencias": advertencias,
            "huerfanos": huerfanos,
            "mode": mode
        }

    def export_to_excel(self, file_path: Path, data: List[Dict[str, Any]], filter_name: str = "Todos") -> None:
        """
        Exporta los resultados de la auditoría a Auditoria.xlsx.
        """
        logger.info(f"Exportando resultados de auditoría ({filter_name}) a: {file_path}")
        wb = Workbook()
        ws = wb.active
        ws.title = "Auditoría"

        headers = [
            "Código",
            "Descripción",
            "Publicado",
            "Imagen Principal",
            "Existe FTP",
            "Cantidad Imágenes",
            "Estado",
            "Observaciones"
        ]
        ws.append(headers)

        for item in data:
            ws.append([
                item.get("codigo", ""),
                item.get("descripcion", ""),
                item.get("publicado", ""),
                item.get("imagen_principal", ""),
                item.get("existe_ftp", ""),
                item.get("cant_adicionales", 0),
                item.get("estado", ""),
                item.get("observaciones", "")
            ])

        # Ajustar ancho de columnas
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        wb.save(str(file_path))
        wb.close()
        logger.info(f"Auditoría exportada exitosamente a {file_path}")
