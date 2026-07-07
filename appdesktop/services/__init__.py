"""Módulo de servicios de la aplicación."""

# Los imports se hacen de forma explícita donde se necesiten
# para evitar errores si alguna dependencia no está instalada.

__all__ = [
    "SqlService",
    "FtpService",
    "EcommerceRepository",
    "ImageService",
    "ExcelService",
    "PublishService",
    "ReportService",
]


def __getattr__(name: str):
    """Lazy import de servicios para evitar errores de dependencias."""
    if name == "SqlService":
        from services.sql_service import SqlService
        return SqlService
    if name == "FtpService":
        from services.ftp_service import FtpService
        return FtpService
    if name == "EcommerceRepository":
        from services.ecommerce_repository import EcommerceRepository
        return EcommerceRepository
    if name == "ImageService":
        from services.image_service import ImageService
        return ImageService
    if name == "ExcelService":
        from services.excel_service import ExcelService
        return ExcelService
    if name == "PublishService":
        from services.publish_service import PublishService
        return PublishService
    if name == "ReportService":
        from services.report_service import ReportService
        return ReportService
    raise AttributeError(f"module 'services' has no attribute {name!r}")
