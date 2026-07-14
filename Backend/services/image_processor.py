import os
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance
from rembg import remove, new_session
import tempfile

# Initialize session once globally to avoid reloading model
try:
    session = new_session("u2net")
except Exception as e:
    print(f"Warning: rembg model could not be loaded immediately: {e}")
    session = None

ASSETS_DIR = Path(__file__).parent.parent / "assets"
WATERMARK_PATH = ASSETS_DIR / "watermark.png"
STAMP_PATH = ASSETS_DIR / "stamp.png"

def process_image(input_path: Path, include_stamp: bool, watermark_opacity: float = 0.05) -> Path:
    """
    Procesa la imagen eliminando el fondo, aplicando recorte 1:1,
    y sobreponiendo la marca de agua (siempre al 5%) y el sello (opcional).
    Retorna la ruta al archivo temporal procesado (.jpg).
    """
    # Forzar opacidad de marca de agua al 5% siempre
    watermark_opacity = 0.05
    # 1. Cargar imagen original
    with Image.open(input_path) as img:
        img = img.convert("RGBA")
        
        # 2. Quitar fondo con IA (rembg)
        if session:
            img_no_bg = remove(img, session=session)
        else:
            # Fallback en caso de que rembg falle al cargar (útil para pruebas)
            img_no_bg = remove(img)
            
        # 3. Recorte 1:1 (Cuadrado). Se extrae el bounding box del elemento sin fondo
        bbox = img_no_bg.getbbox()
        if bbox:
            img_no_bg = img_no_bg.crop(bbox)
        
        # Calcular tamaño cuadrado basado en el lado más largo
        max_side = max(img_no_bg.width, img_no_bg.height)
        # Crear un lienzo cuadrado blanco (para JPEG)
        square_img = Image.new("RGBA", (max_side, max_side), (255, 255, 255, 255))
        
        # Pegar la imagen centrada en el lienzo
        offset = ((max_side - img_no_bg.width) // 2, (max_side - img_no_bg.height) // 2)
        square_img.paste(img_no_bg, offset, mask=img_no_bg)
        
        # Opcional: Redimensionar para unificar tamaño (ej. 1000x1000)
        target_size = (1000, 1000)
        square_img = square_img.resize(target_size, Image.Resampling.LANCZOS)
        
        # 4. Superponer Marca de Agua (Siempre)
        if WATERMARK_PATH.exists():
            with Image.open(WATERMARK_PATH) as wm:
                wm = wm.convert("RGBA")
                # Escalar la marca de agua al tamaño completo si es necesario
                wm = wm.resize(target_size, Image.Resampling.LANCZOS)
                
                # Aplicar transparencia configurable
                if watermark_opacity < 1.0:
                    r, g, b, a = wm.split()
                    a = a.point(lambda p: int(p * watermark_opacity))
                    wm = Image.merge("RGBA", (r, g, b, a))
                
                square_img.paste(wm, (0, 0), mask=wm)
        else:
            print(f"Aviso: Marca de agua no encontrada en {WATERMARK_PATH}")
                
        # 5. Superponer Sello (Condicional)
        if include_stamp and STAMP_PATH.exists():
            with Image.open(STAMP_PATH) as stamp:
                stamp = stamp.convert("RGBA")
                # Ajustar el sello a una esquina, ej: arriba a la derecha (tamaño 250x250)
                stamp_size = (250, 250)
                stamp = stamp.resize(stamp_size, Image.Resampling.LANCZOS)
                stamp_offset = (target_size[0] - stamp_size[0] - 20, 20) # 20px de margen
                square_img.paste(stamp, stamp_offset, mask=stamp)
        elif include_stamp:
            print(f"Aviso: Sello no encontrado en {STAMP_PATH}")
                
        # Convertir a RGB puro para guardar como JPEG
        final_img = square_img.convert("RGB")
        
        # Guardar en archivo temporal
        fd, temp_out_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd) # cerrar descriptor
        
        # Optimizar peso al guardar (<1MB usualmente se logra bajando calidad a 80-85)
        final_img.save(temp_out_path, "JPEG", quality=85, optimize=True)
        
        return Path(temp_out_path)
