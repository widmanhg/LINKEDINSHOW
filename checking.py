import psycopg2
import pandas as pd

# Configurar la conexión a PostgreSQL
conn = psycopg2.connect(
    dbname="prueba",
    user="postgres",
    password="1234",
    host="localhost",
    port="5432"
)

# Crear un cursor para ejecutar la consulta
cursor = conn.cursor()

# Ejecutar la consulta SQL
query = "SELECT * from empresas_noprimary"
cursor.execute(query)

# Obtener los nombres de las columnas
colnames = [desc[0] for desc in cursor.description]

# Convertir los resultados en un DataFrame de Pandas
df = pd.DataFrame(cursor.fetchall(), columns=colnames)

# Cerrar la conexión
cursor.close()
conn.close()

# Mostrar el DataFrame
df.tail(10)
