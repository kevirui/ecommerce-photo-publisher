import configparser
from pathlib import Path
import pyodbc

def main():
    config = configparser.ConfigParser(interpolation=None)
    config.read("config.ini", encoding="utf-8")
    
    server = config.get("SQL", "server", fallback="")
    database = config.get("SQL", "database", fallback="")
    username = config.get("SQL", "username", fallback="")
    password = config.get("SQL", "password", fallback="")
    
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
    )
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Obtener columnas de la tabla ARTICULOS
        cursor.execute("SELECT TOP 1 * FROM ARTICULOS")
        columns = [column[0] for column in cursor.description]
        print("Columnas de ARTICULOS:")
        print(sorted(columns))
        
        # Buscar columnas que contengan "ENVIO", "GRATIS", "SELLO", "WEB"
        interesting = [col for col in columns if any(kw in col.upper() for kw in ["ENVIO", "GRATIS", "SELLO", "WEB", "STAMP", "ENV"])]
        print("\nColumnas interesantes:")
        print(interesting)
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
