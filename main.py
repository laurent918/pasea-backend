from fastapi import FastAPI, HTTPException, Request
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PASEA Backend API", version="1.7")

# On utilise les variables pour le mot de passe, mais l'IP est fixée en dur
DB_USER = "postgres"
DB_PASS = "MBLjcmk@2026"  # Votre mot de passe
DB_NAME = "postgres"
DB_HOST = "104.18.38.10"  # L'adresse IP Cloudflare trouvée précédemment
DB_PORT = "5432"

def get_db_connection():
    # Connexion directe sans passer par le DNS
    conn_str = f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port={DB_PORT} sslmode=require"
    return psycopg2.connect(conn_str, connect_timeout=30, cursor_factory=RealDictCursor)

@app.api_route("/webhooks/kobo-menages/", methods=["GET", "POST"])
async def receive_kobo_menage(request: Request):
    if request.method == "GET": return {"status": "ok"}
    try:
        payload = await request.json()
        data = payload.get("data", payload)
        code_menage = data.get("code_menage")
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = "INSERT INTO menages (code_menage, code_village) VALUES (%s, %s) ON CONFLICT (code_menage) DO NOTHING;"
            cursor.execute(query, (code_menage, data.get("village")))
            conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Erreur: {e}")
        raise HTTPException(status_code=500, detail=str(e))
