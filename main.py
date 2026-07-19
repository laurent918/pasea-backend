from fastapi import FastAPI, Request
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PASEA Backend API")

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST", "104.18.38.10"),
        port=os.getenv("DB_PORT", "5432"),
        sslmode='require',
        connect_timeout=10,
        cursor_factory=RealDictCursor
    )

@app.api_route("/webhooks/kobo-menages/", methods=["POST"])
async def receive_kobo_menage(request: Request):
    payload = await request.json()
    data = payload.get("data", payload)
    
    try:
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
                nbre_latrines_hygieniques = EXCLUDED.nbre_latrines_hygieniques,
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
        # En cas d'erreur, on enregistre dans la nouvelle table kobo_error_logs
        logger.error(f"Erreur d'insertion : {e}")
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO kobo_error_logs (payload, error_message) VALUES (%s, %s);",
                    (Json(payload), str(e))
                )
                conn.commit()
            conn.close()
        except Exception as log_err:
            logger.critical(f"Impossible de logger l'erreur : {log_err}")
            
        return {"status": "error", "message": "Données reçues mais erreur lors du traitement."}
