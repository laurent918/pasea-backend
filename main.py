from fastapi import FastAPI, Request
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PASEA Backend API")

def get_db_connection():
    """
    Connexion simplifiée utilisant la variable d'environnement DATABASE_URL.
    Cette variable contient déjà le host, le port, l'utilisateur et le mot de passe.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise Exception("La variable DATABASE_URL n'est pas configurée.")
        
    return psycopg2.connect(
        database_url, 
        sslmode='require', 
        connect_timeout=20, 
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
