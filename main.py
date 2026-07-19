from fastapi import FastAPI, HTTPException, Request
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configuration simplifiée
DB_HOST = "104.18.38.10" # L'IP Cloudflare
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "MBLjcmk@2026" 
DB_PORT = "5432"

def get_db_connection():
    # Connexion avec un timeout plus court pour ne pas faire attendre Kobo
    return psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASS, 
        host=DB_HOST, port=DB_PORT, sslmode='require',
        connect_timeout=10 
    )

@app.api_route("/webhooks/kobo-menages/", methods=["POST"])
async def receive_kobo_menage(request: Request):
    try:
        payload = await request.json()
        data = payload.get("data", payload)
        code_menage = data.get("code_menage")

        # Connexion et exécution rapide
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO menages (code_menage, code_village) VALUES (%s, %s) ON CONFLICT (code_menage) DO NOTHING;",
                (code_menage, data.get("village"))
            )
            conn.commit()
        conn.close()
        
        return {"status": "success"} # Réponse immédiate
        
    except Exception as e:
        logger.error(f"Erreur: {e}")
        # On renvoie 200 même en cas d'erreur pour éviter que Kobo ne réessaie en boucle
        # et sature votre Render avec des timeouts
        return {"status": "error", "detail": str(e)}
