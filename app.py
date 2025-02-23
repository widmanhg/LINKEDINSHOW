from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from INFO import DatabaseManager, WebScraper
from URL import LinkedInScraper
import time
import threading
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # O usa ["*"] en desarrollo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "API de Scraping en ejecución."}

# Modelo para scraping de URLs
class ScraperRequest(BaseModel):
    email: str
    password: str
    tabla: str
    location: list[str]
    industries: list[str]
    company_sizes: list[str]
    pages_per_size: int

# Mecanismo de cancelación usando threading.Event
cancel_event = threading.Event()

# Endpoint para cancelar el proceso
@app.post("/cancel-process")
def cancel_scrape():
    cancel_event.set()
    return {"message": "El proceso de scraping se ha cancelado."}

# Función que realiza el proceso de scraping
def scraping_thread(request: ScraperRequest):
    # Reiniciar la señal de cancelación antes de iniciar
    cancel_event.clear()

    db_config = {
        'dbname': 'prueba',
        'user': 'postgres',
        'password': '1234',
        'host': 'localhost',
        'port': '5432'
    }

    linkedin_credentials = {
        'email': request.email,
        'password': request.password
    }

    pages_per_size = request.pages_per_size
    tabla = request.tabla
    locations = request.location  
    industries = request.industries
    company_sizes = request.company_sizes

    scraper = LinkedInScraper(db_config, linkedin_credentials, "locations.json", pages_per_size)
    scraper.init_driver()

    try:
        if scraper.login():
            for loc in locations:
                if cancel_event.is_set():
                    print("⚠️ Cancelado antes de procesar la ubicación.")
                    return
                
                print(f"\n🌍 Scraping en ubicación {loc}, guardando en tabla: {tabla}\n")
                for industry in industries:
                    if cancel_event.is_set():
                        print("⚠️ Cancelado antes de procesar la industria.")
                        return
                    for size in company_sizes:
                        if cancel_event.is_set():
                            print("⚠️ Cancelado antes de procesar el tamaño de empresa.")
                            return

                        base_url = (
                            "https://www.linkedin.com/search/results/companies/"
                            f"?companyHqGeo=%5B%22{loc}%22%5D"
                            f"&industryCompanyVertical=%5B%22{industry}%22%5D"
                            f"&companySize=%5B%22{size}%22%5D"
                            "&keywords=a&origin=FACETED_SEARCH&page=1"
                        )

                        print(f"🔍 Scraping con URL: {base_url}")

                        # **PASO CRÍTICO: Verificar cancelación dentro del scraping**
                        scraper.scrape_companies(base_url, industry, size, loc, tabla)
                        
                        if cancel_event.is_set():
                            print("⚠️ Cancelado mientras se ejecutaba `scrape_companies`.")
                            return

                        time.sleep(0.5)
        else:
            print("🚫 Login fallido en LinkedIn.")
    finally:
        print("🛑 Cerrando el WebDriver...")
        scraper.close_driver()


# Endpoint que inicia el scraping en un hilo en segundo plano
@app.post("/url")
async def run_scraper(request: ScraperRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(scraping_thread, request)
    return {"message": "Proceso de scraping iniciado en segundo plano."}


# Configuración de la base de datos para el scraping de información (asumiendo implementación)
db = DatabaseManager("prueba", "postgres", "1234", "localhost", "5432")

# Modelo para scraping de información
class ScrapeinfoRequest(BaseModel):
    email: str
    password: str
    tabla_origen: str
    tabla_destino: str

def scraping_info_thread(request: ScrapeinfoRequest):
    # Reiniciamos la bandera
    cancel_event.clear()

    try:
        scraper = WebScraper()
        scraper.login(request.email, request.password)

        urls = db.get_urls(request.tabla_origen)
        if not urls:
            print("No URLs found in the source table")
            return

        scraped_data = []
        for url, ciudad in urls:
            if cancel_event.is_set():
                print("Proceso de scraping de información cancelado.")
                return
            data = scraper.scrape(url)
            if data:
                db.insert_data(data, request.tabla_destino, ciudad)
                scraped_data.append(data)
            time.sleep(1)
        print("Scraping de información completado:", scraped_data)
    except Exception as e:
        print("Error:", e)
    finally:
        cancel_event.clear()

@app.post("/scrape")
async def scrape_data(request: ScrapeinfoRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(scraping_info_thread, request)
    return {"message": "Proceso de scraping de información iniciado en segundo plano."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
