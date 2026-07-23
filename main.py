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

@app.get("/api/stats/globales")
def get_global_stats():
    """Fournit les indicateurs clés (KPIs) pour les bailleurs et l'État"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_menages,
                    SUM(total_membres_menage) as total_beneficiaires,
                    SUM(garcons_moins_5 + filles_moins_5) as total_enfants_moins_5,
                    SUM(CASE WHEN nbre_latrines_hygieniques > 0 THEN 1 ELSE 0 END) as menages_avec_latrines_hygieniques,
                    SUM(CASE WHEN lave_mains_fonctionnel > 0 THEN 1 ELSE 0 END) as menages_avec_lave_mains,
                    SUM(CASE WHEN environnement_propre ILIKE 'oui' OR environnement_propre ILIKE '1' THEN 1 ELSE 0 END) as menages_environnement_propre
                FROM menages;
            """)
            stats = cursor.fetchone()
        conn.close()
        return {"status": "success", "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cartographie/menages")
def get_menages_gps():
    """Renvoie la liste des ménages avec leurs coordonnées GPS pour la carte interactive"""
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

@app.api_route("/webhooks/kobo-generales/", methods=["POST"])
async def receive_kobo_generales(request: Request):
    payload = await request.json()
    data = payload.get("data", payload)
    
    try:
        query = """
            INSERT INTO donnees_generales (
                code_village, province, zone_sante, aire_sante, nom_village, bailleur, partenaires,
                date_pre_declenchement, nbre_menages_village, ecoles_existantes, ecoles_latrines,
                eglises_existantes, eglises_latrines, date_declenchement, marche_honte, 
                comite_assainissement, plan_action, carte_parlante, nbre_hommes, nbre_femmes,
                filles_moins_18, garcons_moins_18, enfants_moins_5, sensibilise_odf,
                date_suivi_post, latrines_construites, latrines_lave_mains, parcelles_propres,
                trous_ordures, date_certification, est_certifie_odf
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code_village) DO UPDATE SET 
                bailleur = EXCLUDED.bailleur,
                partenaires = EXCLUDED.partenaires,
                date_pre_declenchement = EXCLUDED.date_pre_declenchement,
                nbre_menages_village = EXCLUDED.nbre_menages_village,
                date_declenchement = EXCLUDED.date_declenchement,
                marche_honte = EXCLUDED.marche_honte,
                comite_assainissement = EXCLUDED.comite_assainissement,
                plan_action = EXCLUDED.plan_action,
                carte_parlante = EXCLUDED.carte_parlante,
                date_suivi_post = EXCLUDED.date_suivi_post,
                latrines_construites = EXCLUDED.latrines_construites,
                latrines_lave_mains = EXCLUDED.latrines_lave_mains,
                parcelles_propres = EXCLUDED.parcelles_propres,
                trous_ordures = EXCLUDED.trous_ordures,
                date_certification = EXCLUDED.date_certification,
                est_certifie_odf = EXCLUDED.est_certifie_odf;
        """
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, (
                data.get("code_village"), data.get("province"), data.get("zone_sante"), 
                data.get("aire_sante"), data.get("nom_village"), data.get("bailleur"), data.get("partenaires"),
                data.get("date_pre_declenchement"), data.get("nbre_menages_village", 0),
                data.get("ecoles_existantes", 0), data.get("ecoles_latrines", 0),
                data.get("eglises_existantes", 0), data.get("eglises_latrines", 0),
                data.get("date_declenchement"), data.get("marche_honte"), data.get("comite_assainissement"),
                data.get("plan_action"), data.get("carte_parlante"), data.get("nbre_hommes", 0),
                data.get("nbre_femmes", 0), data.get("filles_moins_18", 0), data.get("garcons_moins_18", 0),
                data.get("enfants_moins_5", 0), data.get("sensibilise_odf"), data.get("date_suivi_post"),
                data.get("latrines_construites", 0), data.get("latrines_lave_mains", 0),
                data.get("parcelles_propres", 0), data.get("trous_ordures", 0),
                data.get("date_certification"), data.get("est_certifie_odf", 0)
            ))
            conn.commit()
        conn.close()
        return {"status": "success", "message": "Données générales du village enregistrées."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/generales")
def get_stats_generales():
    """Renvoie les données globales de déclenchement et certification par village"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM donnees_generales;")
            rows = cursor.fetchall()
        conn.close()
        return {"status": "success", "data": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
