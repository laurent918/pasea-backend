from fastapi import FastAPI, HTTPException, Request
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
import socket
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PASEA Backend API", version="1.6")

# Récupération de l'URL
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    # 1. On force la résolution DNS uniquement en IPv4
    # db.bcfenwnaqljwiplfyvoi.supabase.co
    host = "db.bcfenwnaqljwiplfyvoi.supabase.co"
    port = 5432
    
    # getaddrinfo avec AF_INET force le retour d'une adresse IPv4 (ex: 35.x.x.x)
    addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    ipv4_only = addr_info[0][4][0]
    
    logger.info(f"Connexion forcée en IPv4 sur l'adresse : {ipv4_only}")

    return psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="MBLjcmk@2026", 
        host=ipv4_only, 
        port=port,
        sslmode='require',
        connect_timeout=30,
        cursor_factory=RealDictCursor
    )

@app.api_route("/webhooks/kobo-menages/", methods=["POST"])
async def receive_kobo_menage(request: Request):
    try:
        payload = await request.json()
        data = payload.get("data", payload)
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # ... (votre logique d'insertion reste identique)
            cursor.execute("INSERT INTO menages (code_menage) VALUES (%s) ON CONFLICT DO NOTHING;", (data.get("code_menage"),))
            conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        raise HTTPException(status_code=500, detail=str(e))
