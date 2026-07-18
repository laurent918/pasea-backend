from fastapi import FastAPI, HTTPException, Request
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
import logging

# Configuration des logs pour suivre les erreurs sur Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PASEA Backend API", version="1.0")

# Connexion à la base de données via la variable d'environnement définie sur Render
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

@app.get("/")
def read_root():
    return {"status": "online", "project": "PASEA - RDC"}

# Route de secours pour éviter les erreurs 405 lors des vérifications de Kobo
@app.get("/webhooks/kobo-menages")
def get_webhook():
    return {"status": "ok", "message": "API active. Envoyez vos données en POST."}

@app.post("/webhooks/kobo-menages")
async def receive_kobo_menage(request: Request):
    try:
        payload = await request.json()
        data = payload.get("data", payload)
        
        # 1. Extraction et nettoyage
        code_menage = data.get("code_menage")
        code_village = data.get("village")
        
        # Gestion GPS (Kobo renvoie "lat long alt acc")
        gps_raw = data.get("coordonnees_gps", "").split()
        lat = float(gps_raw[0]) if len(gps_raw) > 0 else None
        lon = float(gps_raw[1]) if len(gps_raw) > 1 else None
        
        # 2. Calculs et préparation
        total_membres = (
            int(data.get("garcons_5_17", 0)) + 
            int(data.get("filles_5_17", 0)) + 
            int(data.get("garcons_moins_5", 0)) + 
            int(data.get("filles_moins_5", 0))
        )

        # 3. Préparation du JSON pour les colonnes flexibles
        standard_keys = ["code_menage", "village", "coordonnees_gps", "garcons_5_17", 
                         "filles_5_17", "garcons_moins_5", "filles_moins_5"]
        extras = {k: v for k, v in data.items() if k not in standard_keys}

        # 4. Insertion SQL
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO menages (
                code_menage, code_village, nom_chef_menage, latitude, longitude,
                garcons_5_17, filles_5_17, garcons_moins_5, filles_moins_5, total_membres_menage,
                nbre_latrines_cabinet, nbre_latrines_hygieniques, nbre_latrines_briques, 
                nbre_latrines_dalle_beton_plastique, nbre_latrines_toiture_toles, 
                latrine_avec_lave_mains_fonctionnel, nbre_trous_ordures, 
                menage_avec_environnement_propre, presence_caca_dans_parcelle, donnees_additionnelles
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code_menage) DO UPDATE SET 
                nom_chef_menage = EXCLUDED.nom_chef_menage,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                donnees_additionnelles = EXCLUDED.donnees_additionnelles;
        """
        
        cursor.execute(query, (
            code_menage, code_village, data.get("nom_chef_menage"), lat, lon,
            data.get("garcons_5_17", 0), data.get("filles_5_17", 0), 
            data.get("garcons_moins_5", 0), data.get("filles_moins_5", 0), 
            total_membres,
            data.get("nbre_latrines", 0), data.get("nbre_latrines_hygieniques", 0), 
            data.get("nbre_latrines_briques", 0), data.get("nbre_dalle_beton", 0), 
            data.get("nbre_toiture_tole", 0), data.get("dispositif_lave_mains"), 
            data.get("nbre_trous_ordures", 0), data.get("environnement_propre"), 
            data.get("presence_caca"), Json(extras)
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"status": "success", "message": f"Ménage {code_menage} traité."}
        
    except Exception as e:
        logger.error(f"Erreur Webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
