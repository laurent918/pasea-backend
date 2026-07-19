from fastapi import FastAPI, HTTPException, Request
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
app = FastAPI()

DB_CONFIG = {
    "dbname": "postgres", "user": "postgres", "password": "MBLjcmk@2026",
    "host": "104.18.38.10", "port": "5432", "sslmode": "require"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG, connect_timeout=10, cursor_factory=RealDictCursor)

@app.api_route("/webhooks/kobo-menages/", methods=["POST"])
async def receive_kobo_menage(request: Request):
    try:
        data = (await request.json()).get("data", await request.json())
        
        # Calcul du total
        total_membres = (
            int(data.get("garcons_5_17", 0)) + int(data.get("filles_5_17", 0)) + 
            int(data.get("garcons_moins_5", 0)) + int(data.get("filles_moins_5", 0))
        )
        
        query = """
            INSERT INTO menages (
                code_menage, code_village, nom_chef_menage, total_membres_menage,
                nbre_latrines, nbre_latrines_hygieniques, environnement_propre, presence_caca
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code_menage) DO UPDATE SET 
                nom_chef_menage = EXCLUDED.nom_chef_menage,
                total_membres_menage = EXCLUDED.total_membres_menage,
                nbre_latrines = EXCLUDED.nbre_latrines,
                environnement_propre = EXCLUDED.environnement_propre,
                presence_caca = EXCLUDED.presence_caca;
        """
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, (
                data.get("code_menage"), data.get("village"), data.get("nom_chef_menage"), 
                total_membres, data.get("nbre_latrines", 0), 
                data.get("nbre_latrines_hygieniques", 0), 
                data.get("environnement_propre"), data.get("presence_caca")
            ))
            conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
