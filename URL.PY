import psycopg2
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

class LinkedInScraper:
    company_size_map = {
        '1-10': 'B', '11-50': 'C', '51-200': 'D',
        '201-500': 'E', '501-1000': 'F', '1001-5000': 'G',
        '5001-10000': 'H', '10000+': 'I'
    }

    def __init__(self, db_config, linkedin_credentials, locations_file, pages_per_size=None):
        self.db_config = db_config
        self.linkedin_credentials = linkedin_credentials
        self.pages_per_size = pages_per_size
        self.driver = None

        # Cargar el archivo JSON con los códigos de ubicación
        with open(locations_file, 'r', encoding='utf-8') as file:
            self.locations_map = json.load(file)

    def init_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def login(self):
        if not self.driver:
            print("❌ WebDriver no iniciado.")
            return False

        self.driver.get('https://www.linkedin.com/login')
        try:
            WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, 'username'))).send_keys(self.linkedin_credentials['email'])
            self.driver.find_element(By.ID, 'password').send_keys(self.linkedin_credentials['password'])
            self.driver.find_element(By.XPATH, '//button[@type="submit"]').click()
            time.sleep(15)
            if "login" in self.driver.current_url:
                print("⚠️ No se pudo iniciar sesión.")
                return False
            print("✅ Login exitoso.")
            return True
        except Exception as e:
            print(f"❌ Error en login: {e}")
            return False

    def insert_url(self, url, location_code, tabla):
        try:
            # Convertir el código de ubicación al nombre de la ciudad
            location_name = self.locations_map.get(location_code, "Desconocido")

            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            cursor.execute(f"INSERT INTO {tabla} (url, city) VALUES (%s, %s)", (url, location_name))
            conn.commit()
            print(f"✅ URL {url} with location {location_name} inserted successfully into table {tabla}.")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ Error inserting URL and location: {e}")

    def scrape_companies(self, base_url, industry, company_size, location_code, tabla):
        page = 1
        found_any = False
        company_size_code = self.company_size_map.get(company_size, '')

        while self.pages_per_size is None or page <= self.pages_per_size:
            url = base_url.replace("page=1", f"page={page}")
            url = url.replace("{company_size}", company_size_code)
            self.driver.get(url)
            time.sleep(10)

            try:
                company_links = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, '//a[contains(@href, "linkedin.com/company/")]'))
                )
                
                if not company_links:
                    print(f"🚫 No more companies found on page {page}. Stopping.")
                    break

                found_any = True
                print(f"📄 Page {page} (Industry {industry}, Size {company_size}): {len(company_links)} companies found.")
                
                for index, link in enumerate(company_links, start=1):
                    company_url = link.get_attribute('href')
                    print(f"{index}. {company_url}")
                    self.insert_url(company_url, location_code, tabla)  # Se usa el código para la búsqueda, pero se inserta el nombre

                page += 1

            except Exception as e:
                print(f"⚠️ Error on page {page}: {e}")
                break

        return found_any

    def scrape_all_companies(self, locations, industries, company_sizes, base_url_template, tabla):
        for loc in locations:
            location_name = self.locations_map.get(loc, "Desconocido")
            print(f"\n🌍 Searching companies in {location_name} (ID: {loc}), storing in table: {tabla}\n")
            
            for industry in industries:
                for size in company_sizes:
                    base_url = base_url_template.format(location=loc, industry=industry, company_size=size)
                    
                    print(f"🔄 Searching industry {industry} with company size {size} in {location_name}")
                    found = self.scrape_companies(base_url, industry, size, loc, tabla)
                    if not found:
                        print(f"⏭️ No companies found in industry {industry} with size {size}, skipping.")

    def close_driver(self):
        if self.driver:
            self.driver.quit()

# Function to run the scraper
def run_scraper():
    # Database configuration
    db_config = {
        'dbname': 'prueba',
        'user': 'postgres',
        'password': '1234',
        'host': 'localhost',
        'port': '5432'
    }

    # LinkedIn credentials
    linkedin_credentials = {
        'email': '????',
        'password': '?????'
    }

    # Number of pages per size (set None to scrape all available pages)
    pages_per_size = 1  

    # Table name in PostgreSQL
    table_name = "url_o"

    # JSON file with locations
    locations_file = "locations.json"

    # Locations to rotate (IDs from locations.json)
    locations = ["104969186", "104326492"]  

    # Industries and company sizes
    industries = [" "]
    company_sizes = [' ']

    # Base URL template
    base_url_template = "https://www.linkedin.com/search/results/companies/?companyHqGeo=%5B%22{location}%22%5D&industryCompanyVertical=%5B%22{industry}%22%5D&companySize=%5B%22{company_size}%22%5D&keywords=a&origin=FACETED_SEARCH&page=1"

    # Create instance of LinkedInScraper
    scraper = LinkedInScraper(db_config, linkedin_credentials, locations_file, pages_per_size)

    # Start WebDriver and login
    scraper.init_driver()
    if scraper.login():
        scraper.scrape_all_companies(locations, industries, company_sizes, base_url_template, table_name)

    # Close WebDriver
    scraper.close_driver()

# Ensure the script runs only when executed directly
if __name__ == "__main__":
    run_scraper()
