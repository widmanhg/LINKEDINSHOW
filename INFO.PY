import psycopg2
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from collections import defaultdict
import time
import re
import json

class DatabaseManager:
    def __init__(self, dbname, user, password, host, port):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
    
    def get_urls(self, tabla_origen):
        # Establecemos la conexión con la base de datos
        conn = psycopg2.connect(
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port
        )
        cur = conn.cursor()
        # Ejecutamos la consulta para obtener los datos de la tabla de origen
        cur.execute(f"SELECT * FROM {tabla_origen};")
        rows = cur.fetchall()
        # Generamos las URLs que se necesitan, usando solo aquellas filas impares
        urls = [(row[1].strip() + "/about/", row[2]) for i, row in enumerate(rows) if (i + 1) % 2 != 0]
        cur.close()
        conn.close()
        return urls
    
    def insert_data(self, data, tabla_destino, ciudad):
        try:
            conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            cur = conn.cursor()

            # Función para formatear las listas en caso de que sean vacías
            def format_array(value):
                return value if isinstance(value, list) and value else "{}"

            # Interpolamos el nombre de la tabla de forma segura usando `sql.SQL` y `sql.Identifier`
            from psycopg2 import sql
            query = sql.SQL("""
                INSERT INTO {tabla} (nombre, resumen, telefono, tamano, ubicaciones, fundacion, sector, sitio_web, sede, especialidades, codigo_postal, ciudad)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """).format(tabla=sql.Identifier(tabla_destino))

            cur.execute(query, (
                data.get("Nombre de la empresa"),
                data.get("Resumen"),
                data.get("Teléfono"),
                data.get("Tamaño de la empresa"),
                data.get("Ubicaciones"),
                data.get("Año de fundación"),
                format_array(data.get("Sector", [])),
                format_array(data.get("Sitio web", [])),
                format_array(data.get("Sede", [])),
                format_array(data.get("Especialidades", [])),
                data.get("Código Postal"),
                ciudad  # Agregar la ciudad obtenida de la tabla de origen
            ))

            conn.commit()
            cur.close()
            conn.close()
            print("✅ Datos insertados correctamente en la base de datos.")
        except Exception as e:
            print(f"❌ Error al insertar datos en la base de datos: {e}")


class WebScraper:
    def __init__(self):
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    def login(self, email, password):
        try:
            print("Iniciando sesión en LinkedIn...")
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(2)
            WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, 'username'))).send_keys(email)
            self.driver.find_element(By.ID, 'password').send_keys(password)
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
            time.sleep(10)
            print("Sesión iniciada con éxito.")
        except Exception as e:
            print(f"Error al iniciar sesión: {e}")
    
    def scrape(self, url):
        try:
            print(f"Scrapeando datos de: {url}")
            self.driver.get(url)
            time.sleep(5)
            sections = defaultdict(list)

            try:
                sections['Nombre de la empresa'] = self.driver.find_element(By.XPATH, "//h1[contains(@class, 'org-top-card-summary__title')]").text.strip()
            except Exception:
                print("No se pudo obtener el nombre de la empresa.")

            try:
                sections['Sector'] = self.driver.find_element(By.XPATH, "//div[contains(@class, 'org-top-card-summary-info-list__info-item')][1]").text.strip()
            except Exception:
                print("No se pudo obtener la descripción de la empresa.")

            try:
                sections['Resumen'] = self.driver.find_element(By.XPATH, "//p[contains(@class, 'break-words')]").text.strip()
            except Exception:
                print("No se pudo obtener el resumen de la empresa.")

            dt_elements = self.driver.find_elements(By.XPATH, "//dl/dt")
            dd_elements = self.driver.find_elements(By.XPATH, "//dl/dd")
            current_dt_index = 0

            for i, dt in enumerate(dt_elements):
                title = dt.text.strip()
                sections[title] = []
                dd_values = []
                while current_dt_index < len(dd_elements) and (i == len(dt_elements)-1 or dd_elements[current_dt_index].location['y'] < dt_elements[i+1].location['y']):
                    dd_values.append(dd_elements[current_dt_index].text.strip())
                    current_dt_index += 1
                sections[title] = dd_values
            
            try:
                locations = [loc.text.strip().split("Cómo llegar")[0].strip() for loc in self.driver.find_elements(By.XPATH, "//div[contains(@class, 'org-location-card')]")]
                sections['Ubicaciones'] = ', '.join(locations)

                # Buscar código postal en las ubicaciones usando una expresión regular
                cp_list = []
                for location in locations:
                    cp = re.findall(r'\b\d{5}\b', location)  # Encuentra códigos postales de 5 dígitos
                    if cp:
                        cp_list.append(cp[0])  # Tomamos solo el primer código postal encontrado
                sections['Código Postal'] = cp_list[0] if cp_list else None  # Solo el primer Cp de la lista
            except Exception:
                print("Error al obtener ubicaciones o códigos postales.")

            # Formatear los datos para inserción en la base de datos
            formatted_result = self.format_data(dict(sections))
            print(json.dumps(formatted_result, indent=4, ensure_ascii=False))
            return formatted_result
        except Exception as e:
            print(f"Error al scrape: {e}")
            return {}


    @staticmethod
    def format_data(data):
        formatted_data = {}
        for key, value in data.items():
            if key.lower() == "teléfono":
                formatted_data[key] = value[0].split("\\n")[0].split("\n")[0].strip() if isinstance(value, list) and value else value
            elif key.lower() == "tamaño de la empresa":
                formatted_data[key] = value[0] if isinstance(value, list) and value else value
            elif key.lower() == "resumen":
                formatted_data[key] = value[:150] + "..." if isinstance(value, str) and len(value) > 100 else value
            else:
                formatted_data[key] = value
        return formatted_data

# Este bloque de código solo se ejecutará cuando se ejecute el script directamente
if __name__ == "__main__":
    db = DatabaseManager("prueba", "postgres", "1234", "localhost", "5432")
    scraper = WebScraper()
    scraper.login("????", "?????")

    tabla_origen = 'url_i'  # Tabla de origen para obtener URLs
    tabla_destino = 'empresas_expo'  # Tabla de destino para insertar datos

    # Obtener todas las URLs de la tabla de origen
    urls = db.get_urls(tabla_origen)

    # Ahora, procesa todas las URLs y guarda los datos en la tabla de destino
    for url, ciudad in urls:
        data = scraper.scrape(url)
        if data:
            db.insert_data(data, tabla_destino, ciudad)

    print("Proceso finalizado.")
