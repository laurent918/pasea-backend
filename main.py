from fastapi import FastAPI, Request, HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PASEA Backend API - Dashboard & SIG")

def get_db_connection():
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
        
        # Extraction des coordonnées GPS (Kobo envoie souvent un format texte "lat lon alt accuracy" ou des champs séparés)
        lat, lon = None, None
        geopoint = data.get("geopoint") # Exemple format Kobo: "lat lon alt acc"
        if geopoint and isinstance(geopoint, str):
            parts = geopoint.split()
            if len(parts) >= 2:
                lat, lon = float(parts[0]), float(parts[1])
        else:
            lat = data.get("latitude")
            lon = data.get("longitude")

        query = """
            INSERT INTO menages (
                code_menage, code_village, nom_chef_menage, total_membres_menage,
                nbre_latrines, nbre_latrines_hygieniques, environnement_propre, presence_caca,
                latitude, longitude
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code_menage) DO UPDATE SET 
                nom_chef_menage = EXCLUDED.nom_chef_menage,
                total_membres_menage = EXCLUDED.total_membres_menage,
                nbre_latrines = EXCLUDED.nbre_latrines,
                nbre_latrines_hygieniques = EXCLUDED.nbre_latrines_hygieniques,
                environnement_propre = EXCLUDED.environnement_propre,
                presence_caca = EXCLUDED.presence_caca,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude;
        """
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, (
                data.get("code_menage"), data.get("village"), data.get("nom_chef_menage"), 
                total_membres, data.get("nbre_latrines", 0), 
                data.get("nbre_latrines_hygieniques", 0), 
                data.get("environnement_propre"), data.get("presence_caca"),
                lat, lon
            ))
            conn.commit()
        conn.close()
        return {"status": "success", "message": "Ménage et coordonnées GPS enregistrés avec succès."}

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

# --- NOUVELLES ROUTES POUR LE DASHBOARD ET LES CARTES ---

@app.get("/api/stats/globales")
def get_global_stats():
    """Fournit les indicateurs clés pour les bailleurs et l'État"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_menages,
                    SUM(total_membres_menage) as total_beneficiaires,
                    SUM(CASE WHEN nbre_latrines_hygieniques > 0 THEN 1 ELSE 0 END) as menages_avec_latrines_hygieniques,
                    SUM(CASE WHEN environnement_propre = 'oui' OR environnement_propre = '1' THEN 1 ELSE 0 END) as menages_environnement_propre
                FROM menages;
            """)
            stats = cursor.fetchone()
        conn.close()
        return {"status": "success", "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cartographie/menages")
def get_menages_gps():
    """Renvoie la liste des ménages avec leurs coordonnées GPS pour alimenter la carte"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT code_menage, code_village, nom_chef_menage, latitude, longitude, nbre_latrines_hygieniques, presence_caca
                FROM menages
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
            """)
            menages = cursor.fetchall()
        conn.close()
        return {"status": "success", "count": len(menages), "data": menages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
