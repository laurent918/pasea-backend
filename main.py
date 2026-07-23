from fastapi import FastAPI, Request, HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PASEA Backend API - Core Engine")

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
        # Récupération sécurisée des données démographiques
        g5_17 = int(data.get("garcons_5_17", 0))
        f5_17 = int(data.get("filles_5_17", 0))
        g_inf5 = int(data.get("garcons_moins_5", 0))
        f_inf5 = int(data.get("filles_moins_5", 0))
        
        # Calcul automatique du total si non fourni ou pour vérification
        total_membres = g5_17 + f5_17 + g_inf5 + f_inf5
        taille_menage = int(data.get("taille_menages", total_membres))

        # Extraction intelligente du GPS (gère le format texte Kobo "lat lon alt acc" ou champs séparés)
        lat, lon, alt = None, None, None
        geopoint = data.get("geopoint")
        if geopoint and isinstance(geopoint, str):
            parts = geopoint.split()
            if len(parts) >= 2:
                lat, lon = float(parts[0]), float(parts[1])
            if len(parts) >= 3:
                alt = float(parts[2])
        else:
            lat = data.get("latitude")
            lon = data.get("longitude")

        query = """
            INSERT INTO menages (
                code_menage, code_village, nom_chef_menage, 
                taille_menage, garcons_5_17, filles_5_17, garcons_moins_5, filles_moins_5, total_membres_menage,
                nbre_latrines, nbre_latrines_hygieniques, latrines_briques, latrines_dalle_beton, 
                latrines_toiture_tole, lave_mains_fonctionnel, trous_ordures, 
                environnement_propre, presence_caca, latitude, longitude, altitude
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code_menage) DO UPDATE SET 
                nom_chef_menage = EXCLUDED.nom_chef_menage,
                taille_menage = EXCLUDED.taille_menage,
                garcons_5_17 = EXCLUDED.garcons_5_17,
                filles_5_17 = EXCLUDED.filles_5_17,
                garcons_moins_5 = EXCLUDED.garcons_moins_5,
                filles_moins_5 = EXCLUDED.filles_moins_5,
                total_membres_menage = EXCLUDED.total_membres_menage,
                nbre_latrines = EXCLUDED.nbre_latrines,
                nbre_latrines_hygieniques = EXCLUDED.nbre_latrines_hygieniques,
                latrines_briques = EXCLUDED.latrines_briques,
                latrines_dalle_beton = EXCLUDED.latrines_dalle_beton,
                latrines_toiture_tole = EXCLUDED.latrines_toiture_tole,
                lave_mains_fonctionnel = EXCLUDED.lave_mains_fonctionnel,
                trous_ordures = EXCLUDED.trous_ordures,
                environnement_propre = EXCLUDED.environnement_propre,
                presence_caca = EXCLUDED.presence_caca,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                altitude = EXCLUDED.altitude;
        """
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, (
                data.get("code_menage"), data.get("village"), data.get("nom_chef_menage"),
                taille_menage, g5_17, f5_17, g_inf5, f_inf5, total_membres,
                data.get("nbre_latrines", 0), data.get("nbre_latrines_hygieniques", 0),
                data.get("latrines_briques", 0), data.get("latrines_dalle_beton", 0),
                data.get("latrines_toiture_tole", 0), data.get("lave_mains_fonctionnel", 0),
                data.get("trous_ordures", 0), data.get("environnement_propre"),
                data.get("presence_caca"), lat, lon, alt
            ))
            conn.commit()
        conn.close()
        
        logger.info(f"Ménage {data.get('code_menage')} enregistré avec succès.")
        return {"status": "success", "message": "Données du ménage synchronisées avec succès."}

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
            
        return {"status": "error", "message": "Erreur de traitement interne enregistrée dans les logs."}

# Routes utilitaires pour s'assurer que l'API répond bien
@app.get("/")
def read_root():
    return {"status": "online", "message": "PASEA Backend API est opérationnelle."}
