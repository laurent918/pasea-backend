from fastapi import FastAPI, HTTPException, Request
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PASEA Backend API", version="1.5")

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=30, # On augmente le timeout à 30 secondes
        cursor_factory=RealDictCursor
    )

@app.get("/")
def read_root():
    return {"status": "online", "project": "PASEA - RDC"}

@app.api_route("/webhooks/kobo-menages/", methods=["GET", "POST"])
async def receive_kobo_menage(request: Request):
    if request.method == "GET":
        return {"status": "ok", "message": "Webhook prêt."}
    
    try:
        payload = await request.json()
        data = payload.get("data", payload)
        
        code_menage = data.get("code_menage")
        if not code_menage:
            raise ValueError("Champ 'code_menage' manquant.")

        # Calculs simples
        total_membres = (
            int(data.get("garcons_5_17", 0)) + int(data.get("filles_5_17", 0)) + 
            int(data.get("garcons_moins_5", 0)) + int(data.get("filles_moins_5", 0))
        )

        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                INSERT INTO menages (
                    code_menage, code_village, nom_chef_menage, total_membres_menage
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (code_menage) DO UPDATE SET 
                    nom_chef_menage = EXCLUDED.nom_chef_menage;
            """
            cursor.execute(query, (
                code_menage, data.get("village"), data.get("nom_chef_menage"), total_membres
            ))
            conn.commit()
        
        conn.close()
        return {"status": "success", "message": "Données traitées."}
        
    except Exception as e:
        logger.error(f"Erreur: {e}")
        raise HTTPException(status_code=500, detail=str(e))
