import os
from PIL import Image

def optimizar_y_convertir_imagenes():
    # Obtener el directorio actual donde se encuentra el script
    directorio_actual = os.getcwd()
    
    # Extensiones de imagen que el script va a procesar
    extensiones_validas = ('.jpg', '.jpeg', '.png', '.webp')
    
    print("🚀 Iniciando el procesamiento de imágenes...")
    
    for archivo in os.listdir(directorio_actual):
        # Comprobar si es un archivo de imagen compatible
        if archivo.lower().endswith(extensiones_validas):
            ruta_original = os.path.join(directorio_actual, archivo)
            
            # 1. Limpiar el nombre eliminando "-Photoroom"
            nombre_limpio = archivo.replace("-Photoroom", "")
            
            # 2. Forzar que la extensión final sea .jpeg si es un PNG
            nombre_base, extension = os.path.splitext(nombre_limpio)
            if extension.lower() == '.png':
                nuevo_nombre = nombre_base + '.jpeg'
            else:
                nuevo_nombre = nombre_limpio
                
            ruta_nueva = os.path.join(directorio_actual, nuevo_nombre)
            
            try:
                # Abrir la imagen original
                with Image.open(ruta_original) as img:
                    # Convertir a RGB si tiene transparencias (RGBA/P) para poder guardarla como JPEG
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    
                    # 3. Comprimir la imagen para que pese menos de 1MB (1024 KB)
                    calidad = 95
                    img.save(ruta_nueva, 'JPEG', quality=calidad)
                    
                    # Bajar la calidad gradualmente si el archivo supera 1MB
                    while os.path.getsize(ruta_nueva) > 1024 * 1024 and calidad > 10:
                        calidad -= 5
                        img.save(ruta_nueva, 'JPEG', quality=calidad)
                
                # Si el archivo final tiene un nombre o extensión diferente, eliminamos el original
                if ruta_original != ruta_nueva:
                    os.remove(ruta_original)
                    
                print(f"✅ Procesado: '{archivo}' -> '{nuevo_nombre}' (Calidad: {calidad}%)")
                
            except Exception as e:
                print(f"❌ Error al procesar {archivo}: {e}")

    print("\n🎉 ¡Proceso finalizado con éxito!")

if __name__ == "__main__":
    optimizar_y_convertir_imagenes()