from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import os
import tempfile
import shutil
from pathlib import Path

# from services.database import SqlService
# from services.ftp import FtpService
from services.image_processor import process_image

app = FastAPI(title="Ecommerce Uploader Backend")

import configparser

# Leer configuración de appdesktop
config_path = Path(__file__).parent.parent / "appdesktop" / "config.ini"
config = configparser.ConfigParser(interpolation=None)

# Valores por defecto
SQL_SERVER = "tu_servidor"
SQL_DB = "tu_basededatos"
SQL_USER = "tu_usuario"
SQL_PASS = "tu_password"

FTP_HOST = "ftp.tudominio.com"
FTP_USER = "tu_ftp_user"
FTP_PASS = "tu_ftp_pass"
FTP_PATH = "/public_html/imagenes"

if config_path.exists():
    try:
        config.read(config_path, encoding="utf-8")
        if "SQL" in config:
            SQL_SERVER = config.get("SQL", "server", fallback=SQL_SERVER)
            SQL_DB = config.get("SQL", "database", fallback=SQL_DB)
            SQL_USER = config.get("SQL", "username", fallback=SQL_USER)
            SQL_PASS = config.get("SQL", "password", fallback=SQL_PASS)
            
        if "FTP" in config:
            FTP_HOST = config.get("FTP", "host", fallback=FTP_HOST)
            FTP_USER = config.get("FTP", "username", fallback=FTP_USER)
            FTP_PASS = config.get("FTP", "password", fallback=FTP_PASS)
            FTP_PATH = config.get("FTP", "remote_path", fallback=FTP_PATH)
        
        print(f"Configuración cargada exitosamente desde {config_path}")
    except Exception as e:
        print(f"Error al leer config.ini: {e}")
else:
    print(f"Advertencia: No se encontró archivo de configuración en {config_path}")

# Directorio de respaldo local
BACKUP_DIR = Path("Respaldo_Imagenes")

@app.post("/api/v1/photos/upload")
async def upload_photo(
    file: UploadFile = File(...),
    article_code: str = Form(...),
    include_stamp: bool = Form(False),
    image_index: int = Form(0),
    watermark_opacity: float = Form(0.3)
):
    file_name = f"{article_code}.jpg" if image_index == 0 else f"{article_code}_{image_index}.jpg"

    # ==========================================
    # 1. Validación en Base de Datos
    # ==========================================
    from services.database import SqlService
    sql = SqlService(SQL_SERVER, SQL_DB, SQL_USER, SQL_PASS)
    try:
        sql.connect()
        results = sql.execute("SELECT * FROM ARTICULOS WHERE COD_ARTICULO = ?", (article_code,))
        if not results:
            return JSONResponse(status_code=404, content={"error": "Artículo no encontrado en la base de datos."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Error de Base de Datos (Validación): {e}"})
    finally:
        # No desconectamos todavía porque usaremos sql más adelante
        pass

    # ==========================================
    # 2. Procesamiento de la Imagen (IA, Recorte)
    # ==========================================
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / file.filename
        
        # Guardar archivo subido temporalmente
        with open(input_path, "wb") as buffer:
            buffer.write(await file.read())

        try:
            # Procesar imagen (Quitar fondo, ajustar, poner marca de agua y sello)
            processed_path = process_image(input_path, include_stamp=include_stamp, watermark_opacity=watermark_opacity)
        except Exception as e:
             sql.disconnect()
             return JSONResponse(status_code=500, content={"error": f"Error procesando imagen: {e}"})

        # ==========================================
        # 3. Guardar copia en Respaldo Local
        # ==========================================
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_file_path = BACKUP_DIR / file_name
        
        try:
            shutil.copy2(processed_path, backup_file_path)
        except Exception as e:
            # No interrumpir el proceso si falla el respaldo, solo hacer log
            print(f"Advertencia: No se pudo crear el respaldo local: {e}")

        # ==========================================
        # 4. Subida al Servidor FTP
        # ==========================================
        from services.ftp import FtpService
        ftp = FtpService(FTP_HOST, port=21, username=FTP_USER, password=FTP_PASS, remote_path=FTP_PATH)
        try:
            ftp.connect()
            ftp.upload_file(processed_path, file_name)
        except Exception as e:
            sql.disconnect()
            return JSONResponse(status_code=500, content={"error": f"Error subiendo a FTP: {e}"})
        finally:
            ftp.disconnect()

        # ==========================================
        # 5. Actualización en la Base de Datos
        # ==========================================
        try:
            if image_index == 0:
                sql.call_procedure(
                    "eco_articulos_publi_web_actua",
                    {
                        "cod_articulo": article_code,
                        "web_publi": "S",
                        "web_imagen": file_name,
                    }
                )
            else:
                sql.call_procedure(
                    "eco_articulos_imagenes_actua",
                    {
                        "cod_articulo": article_code,
                        "web_imagen": file_name,
                        "indice": f"_{image_index}",
                    }
                )
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Error ejecutando SP en BD: {e}"})
        finally:
            sql.disconnect()

    return {
        "message": "Imagen procesada, subida por FTP y registrada en BD con éxito", 
        "article": article_code,
        "image_index": image_index,
        "backup_path": str(backup_file_path)
    }

def normalize_header(text: str) -> str:
    import unicodedata
    if not text:
        return ""
    normalized = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    return normalized.lower().strip()

@app.get("/api/v1/articles/pending")
def get_pending_articles(pending_only: bool = True):
    from services.database import SqlService
    sql = SqlService(SQL_SERVER, SQL_DB, SQL_USER, SQL_PASS)
    try:
        sql.connect()
        query = """
        SELECT
            A.COD_ARTICULO,
            A.DESCRIP_ARTI,
            A.WEB_PUBLI,
            A.WEB_IMAGEN_PROVE,
            A.CANT_STOCK,
            A.AGRUP_ECOM_1,
            COUNT(I.COD_ARTICULO) AS cant_imagenes
        FROM ARTICULOS A
        LEFT JOIN ARTICULOS_IMAGENES I
            ON A.COD_ARTICULO = I.COD_ARTICULO
        """
        
        if pending_only:
            query += " WHERE A.WEB_PUBLI <> 'S' OR A.WEB_IMAGEN_PROVE IS NULL OR A.WEB_IMAGEN_PROVE = '' "
            
        query += """
        GROUP BY
            A.COD_ARTICULO,
            A.DESCRIP_ARTI,
            A.WEB_PUBLI,
            A.WEB_IMAGEN_PROVE,
            A.CANT_STOCK,
            A.AGRUP_ECOM_1
        """
        
        results = sql.execute(query)
        articles = []
        for row in results:
            code = row.get("COD_ARTICULO", "")
            descrip = row.get("DESCRIP_ARTI", "")
            web_publi = row.get("WEB_PUBLI", "")
            imagen_prov = row.get("WEB_IMAGEN_PROVE", "")
            cant_stock = float(row.get("CANT_STOCK", 0.0)) if row.get("CANT_STOCK") is not None else 0.0
            cant_imagenes = int(row.get("cant_imagenes", 0)) if row.get("cant_imagenes") is not None else 0
            categoria = row.get("AGRUP_ECOM_1", "")
            
            is_publi = (web_publi == "S")
            has_any_image = (imagen_prov is not None and str(imagen_prov).strip() != "") or (cant_imagenes > 0)
            
            if pending_only and is_publi and has_any_image:
                continue
                
            if not is_publi:
                estado = "PENDIENTE"
                observaciones = "El artículo no está marcado para publicar en la web."
            elif not has_any_image:
                estado = "INCOMPLETO"
                observaciones = "Marcado para publicar pero no tiene ninguna imagen."
            else:
                estado = "PUBLICADO"
                observaciones = "Artículo publicado."
                
            if cant_stock <= 0:
                continue
                
            articles.append({
                "codigo": code.strip() if code else "",
                "descripcion": descrip.strip() if descrip else "",
                "estado": estado,
                "stock": cant_stock,
                "cant_imagenes": cant_imagenes,
                "categoria": categoria.strip() if categoria else "OTROS",
                "observaciones": observaciones
            })
            
        return {"articles": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en BD: {e}")
    finally:
        sql.disconnect()

@app.post("/api/v1/articles/pending/from-excel")
async def get_pending_articles_from_excel(file: UploadFile = File(...)):
    import tempfile
    import openpyxl
    import xlrd
    
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx o .xls)")

    codes = []
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
        
    try:
        if suffix == ".xlsx":
            workbook = openpyxl.load_workbook(filename=str(tmp_path), read_only=True, data_only=True)
            sheet = workbook.active
            if sheet is not None:
                first_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=False))
                code_col_idx = None
                accepted_names = {"codigo", "articulo", "cod_articulo", "code", "cod"}
                for cell in first_row:
                    if cell.value is None:
                        continue
                    normalized_val = normalize_header(str(cell.value))
                    normalized_val_clean = normalized_val.replace("_", "").replace("-", "")
                    if normalized_val in accepted_names or normalized_val_clean in accepted_names:
                        code_col_idx = cell.column
                        break
                        
                if code_col_idx is not None:
                    for row in sheet.iter_rows(min_row=2, values_only=False):
                        cell_val = None
                        for cell in row:
                            if cell.column == code_col_idx:
                                cell_val = cell.value
                                break
                        if cell_val is not None:
                            if isinstance(cell_val, float) and cell_val.is_integer():
                                code_str = str(int(cell_val)).strip()
                            else:
                                code_str = str(cell_val).strip()
                            if code_str and code_str not in codes:
                                codes.append(code_str)
            workbook.close()
        else:
            workbook = xlrd.open_workbook(str(tmp_path))
            sheet = workbook.sheet_by_index(0)
            first_row = [sheet.cell_value(0, col_idx) for col_idx in range(sheet.ncols)]
            code_col_idx = None
            accepted_names = {"codigo", "articulo", "cod_articulo", "code", "cod"}
            for col_idx, cell_val in enumerate(first_row):
                if cell_val is None:
                    continue
                normalized_val = normalize_header(str(cell_val))
                normalized_val_clean = normalized_val.replace("_", "").replace("-", "")
                if normalized_val in accepted_names or normalized_val_clean in accepted_names:
                    code_col_idx = col_idx
                    break
                    
            if code_col_idx is not None:
                for row_idx in range(1, sheet.nrows):
                    cell_val = sheet.cell_value(row_idx, code_col_idx)
                    if cell_val is not None:
                        if isinstance(cell_val, float) and cell_val.is_integer():
                            code_str = str(int(cell_val)).strip()
                        else:
                            code_str = str(cell_val).strip()
                        if code_str and code_str not in codes:
                            codes.append(code_str)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo el archivo Excel: {e}")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    if not codes:
        return {"articles": []}

    from services.database import SqlService
    sql = SqlService(SQL_SERVER, SQL_DB, SQL_USER, SQL_PASS)
    try:
        sql.connect()
        articles = []
        chunk_size = 500
        for i in range(0, len(codes), chunk_size):
            chunk = codes[i:i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            query = f"""
            SELECT
                A.COD_ARTICULO,
                A.DESCRIP_ARTI,
                A.WEB_PUBLI,
                A.WEB_IMAGEN_PROVE,
                A.CANT_STOCK,
                A.AGRUP_ECOM_1,
                COUNT(I.COD_ARTICULO) AS cant_imagenes
            FROM ARTICULOS A
            LEFT JOIN ARTICULOS_IMAGENES I
                ON A.COD_ARTICULO = I.COD_ARTICULO
            WHERE A.COD_ARTICULO IN ({placeholders})
            GROUP BY
                A.COD_ARTICULO,
                A.DESCRIP_ARTI,
                A.WEB_PUBLI,
                A.WEB_IMAGEN_PROVE,
                A.CANT_STOCK,
                A.AGRUP_ECOM_1
            """
            results = sql.execute(query, tuple(chunk))
            
            for row in results:
                code = row.get("COD_ARTICULO", "")
                descrip = row.get("DESCRIP_ARTI", "")
                web_publi = row.get("WEB_PUBLI", "")
                imagen_prov = row.get("WEB_IMAGEN_PROVE", "")
                cant_stock = float(row.get("CANT_STOCK", 0.0)) if row.get("CANT_STOCK") is not None else 0.0
                cant_imagenes = int(row.get("cant_imagenes", 0)) if row.get("cant_imagenes") is not None else 0
                categoria = row.get("AGRUP_ECOM_1", "")
                
                is_publi = (web_publi == "S")
                has_any_image = (imagen_prov is not None and str(imagen_prov).strip() != "") or (cant_imagenes > 0)
                
                if is_publi and has_any_image:
                    continue
                    
                if not is_publi:
                    estado = "PENDIENTE"
                    observaciones = "El artículo no está marcado para publicar en la web."
                else:
                    estado = "INCOMPLETO"
                    observaciones = "Marcado para publicar pero no tiene ninguna imagen."
                    
                if cant_stock <= 0:
                    continue
                    
                articles.append({
                    "codigo": code.strip() if code else "",
                    "descripcion": descrip.strip() if descrip else "",
                    "estado": estado,
                    "stock": cant_stock,
                    "cant_imagenes": cant_imagenes,
                    "categoria": categoria.strip() if categoria else "OTROS",
                    "observaciones": observaciones
                })
                
        return {"articles": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error de BD: {e}")
    finally:
        sql.disconnect()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
