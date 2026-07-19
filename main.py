from fastapi import FastAPI, HTTPException, Request
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configuration (Note : En production, utilisez les variables d'environnement)
DB_CONFIG = {
    "dbname": "postgres", "user": "postgres", "password": "MBLjcmk@2026",
    "host": "104.18.38.10", "port": "5432", "sslmode": "require"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG, connect_timeout=10, cursor_factory=RealDictCursor)

@app.api_route("/webhooks/kobo-menages/", methods=["POST"])
async def receive_kobo_menage(request: Request):
    try:
        payload = await request.json()
        data = payload.get("data", payload)
        
        # 1. Calculs rapides
        total_membres = (
            int(data.get("garcons_5_17", 0)) + int(data.get("filles_5_17", 0)) + 
            int(data.get("garcons_moins_5", 0)) + int(data.get("filles_moins_5", 0))
        )
        
        # 2. Préparation de la requête
        query = """
            INSERT INTO menages (
                code_menage, code_village, nom_chef_menage, total_membres_menage,
                nbre_latrines, nbre_latrines_hygieniques, environnement_propre, presence_caca
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code_menage) DO UPDATE SET 
                nom_chef_menage = EXCLUDED.nom_chef_menage,
                total_membres_menage = EXCLUDED.total_membres_menage,
                nbre_latrines = EXCLUDED.nbre_latrines,
                environnement_propre = EXCLUDED.environnement_propre;
        """
        
        # 3. Exécution
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, (
                data.get("code_menage"), data.get("village"), data.get("nom_chef_menage"), total_membres,
                data.get("nbre_latrines", 0), data.get("nbre_latrines_hygieniques", 0), 
                data.get("environnement_propre"), data.get("presence_caca")
            ))
            conn.commit()
        conn.close()
        
        return {"status": "success", "menage": data.get("code_menage")}
        
    except Exception as e:
        logger.error(f"Erreur d'insertion : {e}")
        return {"status": "error", "message": str(e)}
