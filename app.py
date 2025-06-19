from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, send_file, make_response, jsonify
import pandas as pd
import os
import matplotlib
matplotlib.use('Agg')  # Backend non-interactif pour de meilleures performances
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime, timedelta
import hashlib
from functools import lru_cache, wraps
import json
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Image, PageBreak, Spacer, Frame
from reportlab.lib.units import inch
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate

# Configuration de production
app = Flask(__name__)
app.config.update(
    ENV='production',
    DEBUG=False,
    TESTING=False,
    TEMPLATES_AUTO_RELOAD=False,
    SEND_FILE_MAX_AGE_DEFAULT=31536000  # 1 an en secondes
)
app.secret_key = 'votre_cle_secrete_a_remplacer'  # À personnaliser pour la sécurité

# Définir le chemin absolu du fichier Excel
FICHIER = os.path.abspath(os.path.join(os.path.dirname(__file__), "mesures.xlsx"))
print(f"Chemin du fichier Excel: {FICHIER}")

CACHE_DIR = "cache"
CACHE_DURATION = 3600  # 1 heure en secondes
RAPPORTS_JSON = "rapports.json"
PHOTOS_DIR = "photos_releves"
RELEVES_JSON = "releves_20.json"

# Créer les dossiers nécessaires s'ils n'existent pas
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

# Configuration matplotlib pour de meilleures performances
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 100
plt.rcParams['figure.figsize'] = (10, 5)
plt.rcParams['font.size'] = 10

def get_cache_key(site, parametre, semaine=None, annee=None, type_graph="default"):
    """Génère une clé de cache unique pour un graphique"""
    key_data = f"{site}_{parametre}_{semaine}_{annee}_{type_graph}"
    return hashlib.md5(key_data.encode()).hexdigest()

def get_cache_path(cache_key):
    """Retourne le chemin du fichier de cache"""
    return os.path.join(CACHE_DIR, f"{cache_key}.png")

def is_cache_valid(cache_path):
    """Vérifie si le cache est encore valide"""
    if not os.path.exists(cache_path):
        return False
    file_age = datetime.now().timestamp() - os.path.getmtime(cache_path)
    return file_age < CACHE_DURATION

def save_to_cache(cache_key, image_data):
    """Sauvegarde une image en cache"""
    cache_path = get_cache_path(cache_key)
    with open(cache_path, 'wb') as f:
        f.write(image_data)

def load_from_cache(cache_key):
    """Charge une image depuis le cache"""
    cache_path = get_cache_path(cache_key)
    if is_cache_valid(cache_path):
        with open(cache_path, 'rb') as f:
            return f.read()
    return None

# Définition des mesures pour chaque site
mesures_smp = [
    "Exhaure 1", "Exhaure 2", "Exhaure 3", "Exhaure 4", "Retour dessableur", "Retour Orage",
    "Rejet à l'Arc", "Surpresseur 4 pompes", "Surpresseur 7 pompes", "Entrée STE CAB",
    "Alimentation CAB", "Eau potable", "Forage", "Boue STE", "Boue STE CAB",
    "pH entrée", "pH sortie", "Température entrée", "Température sortie",
    "Conductivité sortie", "MES entrée", "MES sortie", "Coagulant", "Floculant", "CO2"
]

mesures_lpz = [
    "Exhaure 1", "Exhaure 2", "Retour dessableur", "Surpresseur BP", "Surpresseur HP",
    "Rejet à l'Arc", "Entrée STE CAB", "Alimentation CAB", "Eau de montagne", "Boue STE",
    "Boue STE CAB", "pH entrée", "pH sortie", "Température entrée", "Température sortie",
    "Conductivité sortie", "MES entrée", "MES sortie", "Coagulant", "Floculant", "CO2"
]

sites = {"SMP": mesures_smp, "LPZ": mesures_lpz}

parametres_compteurs = {
    "SMP": ["Exhaure 1", "Exhaure 2", "Exhaure 3", "Exhaure 4", "Retour dessableur", "Retour Orage",
            "Rejet à l'Arc", "Surpresseur 4 pompes", "Surpresseur 7 pompes", "Entrée STE CAB",
            "Alimentation CAB", "Eau potable", "Forage"],
    "LPZ": ["Exhaure 1", "Exhaure 2", "Retour dessableur", "Surpresseur BP", "Surpresseur HP",
            "Rejet à l'Arc", "Entrée STE CAB", "Alimentation CAB", "Eau de montagne"]
}

parametres_directs = {
    "SMP": ["Boue STE", "Boue STE CAB", "pH entrée", "pH sortie", "Température entrée", "Température sortie",
            "Conductivité sortie", "MES entrée", "MES sortie", "CO2"],
    "LPZ": ["Boue STE", "Boue STE CAB", "pH entrée", "pH sortie", "Température entrée", "Température sortie",
            "Conductivité sortie", "MES entrée", "MES sortie", "CO2"]
}

# Débitmètres pour le relevé du 20
debitmetres_smp = ["Exhaure 1", "Exhaure 2", "Exhaure 3", "Exhaure 4", "Retour dessableur", "Retour Orage"]
debitmetres_lpz = ["Exhaure 1", "Retour dessableur"]
debitmetres = {"SMP": debitmetres_smp, "LPZ": debitmetres_lpz}

def initialiser_fichier():
    """Initialise le fichier Excel avec les colonnes nécessaires"""
    print(f"Initialisation du fichier {FICHIER}")
    dfs = {}
    
    # Créer un DataFrame pour chaque site avec une ligne exemple
    for site, mesures in sites.items():
        # Créer les colonnes
        columns = ["Date", "Statut"] + mesures
        
        # Créer un DataFrame avec une ligne exemple
        data = {
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Statut": "Validé"
        }
        # Ajouter des valeurs d'exemple pour chaque mesure
        for mesure in mesures:
            data[mesure] = ""
            
        df = pd.DataFrame([data], columns=columns)
        dfs[site] = df
    
    # Sauvegarder dans un nouveau fichier Excel
    try:
        # Créer le répertoire parent si nécessaire
        os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
        
        # Sauvegarder le fichier
        with pd.ExcelWriter(FICHIER, engine='openpyxl', mode='w') as writer:
            for site, df in dfs.items():
                df.to_excel(writer, sheet_name=site, index=False)
        
        # S'assurer que le fichier a les bonnes permissions sous Windows
        try:
            import stat
            # Donner tous les droits à tous les utilisateurs
            os.chmod(FICHIER, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        except Exception as e:
            print(f"Attention: impossible de modifier les permissions du fichier: {str(e)}")
            print("Le fichier a été créé mais pourrait avoir des problèmes de permissions")
        
        print(f"Fichier {FICHIER} créé avec succès")
    except Exception as e:
        print(f"Erreur lors de la création du fichier: {str(e)}")
        raise

@lru_cache(maxsize=10)
def charger_donnees_cached(site, timestamp):
    """Version cachée de charger_donnees avec timestamp pour invalidation"""
    if not os.path.exists(FICHIER):
        initialiser_fichier()
    try:
        return pd.read_excel(FICHIER, sheet_name=site, engine="openpyxl")
    except Exception as e:
        print(f"Erreur lors du chargement des données pour {site}: {e}")
        return pd.DataFrame(columns=["Date", "Statut"] + sites[site])

def charger_donnees(site):
    """Charge les données avec cache intelligent"""
    try:
        # Utiliser le timestamp de modification du fichier pour invalider le cache
        if os.path.exists(FICHIER):
            timestamp = int(os.path.getmtime(FICHIER))
        else:
            timestamp = 0
            print(f"Le fichier {FICHIER} n'existe pas encore")
            initialiser_fichier()
            
        df = charger_donnees_cached(site, timestamp)
        if df is None or df.empty:
            print(f"Aucune donnée trouvée pour le site {site}")
            return pd.DataFrame(columns=["Date", "Statut"] + sites[site])
        return df
        
    except Exception as e:
        print(f"Erreur lors du chargement des données pour {site}: {str(e)}")
        return pd.DataFrame(columns=["Date", "Statut"] + sites[site])

def nettoyer_cache_expire():
    """Nettoie automatiquement les fichiers de cache expirés"""
    try:
        for filename in os.listdir(CACHE_DIR):
            file_path = os.path.join(CACHE_DIR, filename)
            if os.path.isfile(file_path) and not is_cache_valid(file_path):
                os.remove(file_path)
    except Exception as e:
        print(f"Erreur lors du nettoyage automatique du cache: {e}")

def invalider_cache_site(site):
    """Invalide tous les caches liés à un site spécifique"""
    try:
        for filename in os.listdir(CACHE_DIR):
            if filename.startswith(hashlib.md5(site.encode()).hexdigest()[:8]):
                file_path = os.path.join(CACHE_DIR, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
    except Exception as e:
        print(f"Erreur lors de l'invalidation du cache pour {site}: {e}")

def sauvegarder_donnees(df_modifie, site):
    """Sauvegarde les données dans le fichier Excel"""
    try:
        dfs = {}
        if os.path.exists(FICHIER):
            with pd.ExcelFile(FICHIER, engine="openpyxl") as xls:
                for sheet in xls.sheet_names:
                    dfs[sheet] = xls.parse(sheet)
        else:
            initialiser_fichier()
            for s in sites:
                dfs[s] = pd.DataFrame(columns=["Date", "Statut"] + sites[s])

        dfs[site] = df_modifie

        # Sauvegarder le fichier
        with pd.ExcelWriter(FICHIER, engine="openpyxl", mode="w") as writer:
            for sheet, data in dfs.items():
                data.to_excel(writer, sheet_name=sheet, index=False)
        
        # S'assurer que le fichier a les bonnes permissions sous Windows
        try:
            import stat
            # Donner tous les droits à tous les utilisateurs
            os.chmod(FICHIER, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        except Exception as e:
            print(f"Attention: impossible de modifier les permissions du fichier: {str(e)}")
            print("Le fichier a été sauvegardé mais pourrait avoir des problèmes de permissions")
        
        # Invalider le cache après sauvegarde
        charger_donnees_cached.cache_clear()
        invalider_cache_site(site)
        
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des données: {str(e)}")
        raise

def enregistrer_rapport(semaine, annee, site):
    """Enregistre un rapport généré dans un fichier JSON"""
    rapports = []
    if os.path.exists(RAPPORTS_JSON):
        with open(RAPPORTS_JSON, "r", encoding="utf-8") as f:
            try:
                rapports = json.load(f)
            except Exception:
                rapports = []
    # On évite les doublons exacts
    for r in rapports:
        if r["semaine"] == semaine and r["annee"] == annee and r["site"] == site:
            return
    rapports.append({
        "semaine": semaine,
        "annee": annee,
        "site": site,
        "timestamp": datetime.now().isoformat()
    })
    with open(RAPPORTS_JSON, "w", encoding="utf-8") as f:
        json.dump(rapports, f, ensure_ascii=False, indent=2)

def require_access(allowed_codes):
    """
    Décorateur pour vérifier les niveaux d'accès.
    allowed_codes peut être un entier unique ou une liste d'entiers.
    Le niveau 14 (admin) a accès à tout.
    """
    if isinstance(allowed_codes, int):
        allowed_codes = [allowed_codes]
        
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'access_code' not in session:
                return redirect(url_for('login'))
            
            access_code = int(session.get('access_code'))
            
            # L'admin (niveau 14) a accès à tout
            if access_code == 14:
                return f(*args, **kwargs)
                
            # Pour les autres niveaux, vérifier si le code est dans la liste des codes autorisés
            if access_code not in allowed_codes:
                return redirect(url_for('login'))
                
            return f(*args, **kwargs)
        return wrapped
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        code = request.form.get('code')
        if code in ['11', '12', '13', '14']:
            session['access_code'] = int(code)
            return redirect(url_for('index'))
        return render_template('login.html', error="Code d'accès incorrect")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('access_code', None)
    return redirect(url_for('login'))

# Route par défaut - redirige vers login si pas authentifié
@app.route('/')
def root():
    if 'access_code' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('index'))

# Page d'accueil après login
@app.route("/index")
@require_access([11, 12, 13, 14])  # Tous les niveaux ont accès à l'index
def index():
    return render_template("index.html")

@app.route("/saisie/<site>", methods=["GET", "POST"])
@require_access([12, 13, 14])  # Saisie : niveaux 12, 13 et admin
def saisie(site):
    mesures = sites[site]
    df = charger_donnees(site)
    today_date = datetime.now()
    today_str = today_date.strftime("%Y-%m-%d")

    yesterday = (today_date - timedelta(days=1)).strftime("%Y-%m-%d")
    veille = df[(df["Date"] == yesterday) & (df["Statut"] == "Validé")]

    valeurs_veille = {}
    for m in mesures:
        valeurs_veille[m] = ""
        if not veille.empty:
            valeurs_veille[m] = veille[m].iloc[-1]

    brouillon = df[(df["Date"] == today_str) & (df["Statut"] == "Brouillon")]
    valide = df[(df["Date"] == today_str) & (df["Statut"] == "Validé")]

    if request.method == "POST":
        if "choix" in request.form:
            choix = request.form["choix"]
            if choix == "annuler":
                return redirect("/")
            elif choix == "ecraser":
                valid_today = df[(df["Date"] == today_str) & (df["Statut"] == "Validé")]
                if not valid_today.empty:
                    last_idx = valid_today.index[-1]
                    df = df.drop(last_idx)
                sauvegarder_donnees(df, site)
                return redirect(url_for("saisie", site=site))
            elif choix == "nouveau":
                ligne = {"Date": today_str, "Statut": "Brouillon"}
                for m in mesures:
                    ligne[m] = ""
                df.loc[len(df)] = ligne
                sauvegarder_donnees(df, site)
                return redirect(url_for("saisie", site=site))
            elif choix == "modifier":
                valid_today = df[(df["Date"] == today_str) & (df["Statut"] == "Validé")]
                if not valid_today.empty:
                    last_idx = valid_today.index[-1]
                    df.loc[last_idx, "Statut"] = "Brouillon"
                    sauvegarder_donnees(df, site)
                return redirect(url_for("saisie", site=site))

        ligne = {"Date": today_str, "Statut": "Brouillon"}
        for m in mesures:
            if m in ["Coagulant", "Eau potable"] and today_date.weekday() != 0:
                ligne[m] = ""
            else:
                ligne[m] = request.form.get(m) or ""

        if not brouillon.empty:
            idx = brouillon.index[0]
            for k, v in ligne.items():
                if k in ["Coagulant", "Eau potable"] and today_date.weekday() != 0:
                    # Convertir explicitement en string pour éviter les warnings
                    df.loc[idx, k] = str("")
                else:
                    # Convertir explicitement le type selon la colonne
                    if k in ["Date", "Statut"]:
                        df.loc[idx, k] = str(v)
                    elif k in parametres_compteurs.get(site, []):
                        # Pour les compteurs, convertir en float puis en int si possible
                        try:
                            if v == "" or v is None:
                                df.loc[idx, k] = ""
                            else:
                                df.loc[idx, k] = float(v)
                        except (ValueError, TypeError):
                            df.loc[idx, k] = ""
                    else:
                        # Pour les autres paramètres, convertir en float si possible
                        try:
                            if v == "" or v is None:
                                df.loc[idx, k] = ""
                            else:
                                df.loc[idx, k] = float(v)
                        except (ValueError, TypeError):
                            df.loc[idx, k] = str(v)
        else:
            # Pour une nouvelle ligne, convertir les types avant l'ajout
            ligne_converted = {}
            for k, v in ligne.items():
                if k in ["Date", "Statut"]:
                    ligne_converted[k] = str(v)
                elif k in parametres_compteurs.get(site, []):
                    try:
                        if v == "" or v is None:
                            ligne_converted[k] = ""
                        else:
                            ligne_converted[k] = float(v)
                    except (ValueError, TypeError):
                        ligne_converted[k] = ""
                else:
                    try:
                        if v == "" or v is None:
                            ligne_converted[k] = ""
                        else:
                            ligne_converted[k] = float(v)
                    except (ValueError, TypeError):
                        ligne_converted[k] = str(v)
            df.loc[len(df)] = ligne_converted

        if "finaliser" in request.form:
            df.loc[(df["Date"] == today_str) & (df["Statut"] == "Brouillon"), "Statut"] = "Validé"

        sauvegarder_donnees(df, site)
        message = "Mesure validée." if "finaliser" in request.form else "Brouillon sauvegardé."
        return render_template("confirmation.html", message=message)

    valeurs = {}
    if not brouillon.empty:
        valeurs = brouillon.iloc[0].fillna("").to_dict()
    elif not valide.empty:
        n = len(valide) + 1
        return render_template("alerte.html", site=site, n=n)

    valeurs_diff = {}
    for m in mesures:
        try:
            veille_val = float(valeurs_veille.get(m, 0)) or 0
            saisie_val = float(valeurs.get(m, 0)) or 0
            valeurs_diff[m] = saisie_val - veille_val
        except:
            valeurs_diff[m] = ""

    is_monday = today_date.weekday() == 0
    return render_template("saisie.html", site=site, mesures=mesures, valeurs=valeurs,
                           valeurs_veille=valeurs_veille, valeurs_diff=valeurs_diff, is_monday=is_monday)

def enregistrer_releve(site, mois, annee, photos_paths):
    """Enregistre un relevé photo dans le fichier JSON"""
    releves = []
    if os.path.exists(RELEVES_JSON):
        with open(RELEVES_JSON, "r", encoding="utf-8") as f:
            try:
                releves = json.load(f)
            except Exception:
                releves = []
    
    # Vérifier si un relevé existe déjà pour ce site/mois/année
    for r in releves:
        if r["site"] == site and r["mois"] == mois and r["annee"] == annee:
            return False  # Relevé déjà existant
    
    releves.append({
        "site": site,
        "mois": mois,
        "annee": annee,
        "photos": photos_paths,
        "timestamp": datetime.now().isoformat()
    })
    
    with open(RELEVES_JSON, "w", encoding="utf-8") as f:
        json.dump(releves, f, ensure_ascii=False, indent=2)
    return True

def charger_releves():
    """Charge tous les relevés depuis le fichier JSON"""
    if os.path.exists(RELEVES_JSON):
        with open(RELEVES_JSON, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def sauvegarder_photo(photo_file, site, debitmetre, mois, annee):
    """Sauvegarde une photo avec un nom unique dans un sous-dossier spécifique au relevé"""
    if photo_file:
        try:
            # S'assurer que le dossier principal existe avec les bonnes permissions
            if not os.path.exists(PHOTOS_DIR):
                os.makedirs(PHOTOS_DIR, mode=0o755)
                print(f"Dossier principal créé: {PHOTOS_DIR}")
            
            # Créer le nom du sous-dossier au format site_mois_année
            subfolder_name = f"{site.replace(' ', '_')}_{mois}_{annee}"
            subfolder_path = os.path.join(PHOTOS_DIR, subfolder_name)
            print(f"Tentative de création du sous-dossier: {subfolder_path}")
            
            # Créer le sous-dossier s'il n'existe pas
            if not os.path.exists(subfolder_path):
                os.makedirs(subfolder_path, mode=0o755)
                print(f"Sous-dossier créé: {subfolder_path}")
            
            # Créer le nom de fichier unique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{debitmetre.replace(' ', '_')}_{timestamp}.jpg"
            filepath = os.path.join(subfolder_path, filename)
            print(f"Tentative de sauvegarde de la photo: {filepath}")
            
            # Sauvegarder la photo
            photo_file.save(filepath)
            print(f"Photo sauvegardée avec succès: {filepath}")
            
            # Vérifier que le fichier a bien été créé
            if not os.path.exists(filepath):
                raise Exception(f"Le fichier n'a pas été créé: {filepath}")
            
            # Retourner le chemin relatif par rapport à PHOTOS_DIR
            relative_path = os.path.join(subfolder_name, filename)
            print(f"Chemin relatif retourné: {relative_path}")
            return relative_path
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la photo: {str(e)}")
            # En cas d'erreur, on essaie de sauvegarder directement dans le dossier principal
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{site.replace(' ', '_')}_{debitmetre.replace(' ', '_')}_{mois}_{annee}_{timestamp}.jpg"
                filepath = os.path.join(PHOTOS_DIR, filename)
                photo_file.save(filepath)
                print(f"Photo sauvegardée en fallback: {filepath}")
                return filename
            except Exception as e2:
                print(f"Erreur également lors de la sauvegarde de secours: {str(e2)}")
                return None
    return None

@app.route("/releve_20", methods=["GET", "POST"])
@require_access([11, 13, 14])  # Relevé 20 : niveau 11, 13 et admin
def releve_20():
    from datetime import datetime
    now = datetime.now()
    annee_courante = now.year
    mois_courant = now.month
    
    sites_list = list(debitmetres.keys())
    releves = charger_releves()
    
    # Formater les dates pour l'affichage
    for releve in releves:
        if "timestamp" in releve:
            try:
                # Convertir la chaîne ISO en objet datetime
                date_obj = datetime.fromisoformat(releve["timestamp"])
                # Formater la date pour l'affichage
                releve["timestamp"] = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"Erreur lors du formatage de la date: {e}")
                releve["timestamp"] = "Date inconnue"
    
    # Trier par date (plus récent en premier)
    releves = sorted(releves, key=lambda r: (r["annee"], r["mois"]), reverse=True)
    
    if request.method == "POST":
        site = request.form["site"]
        mois = int(request.form["mois"])
        annee = int(request.form["annee"])
        
        # Traitement des photos uploadées
        photos_paths = {}
        photos_uploaded = False  # Flag pour vérifier si des photos ont été sélectionnées
        
        for debitmetre in debitmetres[site]:
            # Vérifier les deux possibilités : fichier ou photo caméra
            photo_key = f"photo_{debitmetre.replace(' ', '_')}"
            photo_key_file = f"{photo_key}_file"
            photo_key_camera = f"{photo_key}_camera"
            
            photo_file = None
            if photo_key_file in request.files:
                photo_file = request.files[photo_key_file]
                if photo_file and photo_file.filename:
                    photos_uploaded = True
            
            if not photos_uploaded and photo_key_camera in request.files:
                photo_file = request.files[photo_key_camera]
                if photo_file and photo_file.filename:
                    photos_uploaded = True
            
            if photo_file and photo_file.filename:
                print(f"Traitement de la photo pour {debitmetre}: {photo_file.filename}")
                filename = sauvegarder_photo(photo_file, site, debitmetre, mois, annee)
                if filename:
                    photos_paths[debitmetre] = filename
                    print(f"Photo sauvegardée: {filename}")
        
        # Vérifier si des photos ont été sélectionnées
        if not photos_uploaded:
            print("Erreur: Aucune photo n'a été sélectionnée")
            return render_template("releve_20.html",
                                 sites=sites_list,
                                 debitmetres=debitmetres,
                                 releves=releves,
                                 selected_site=site,
                                 mois=mois,
                                 annee=annee,
                                 error="Veuillez sélectionner au moins une photo",
                                 just_saved=False)
        
        # Enregistrer le relevé si des photos ont été uploadées avec succès
        if photos_paths:
            print(f"Tentative d'enregistrement du relevé avec {len(photos_paths)} photos")
            success = enregistrer_releve(site, mois, annee, photos_paths)
            if success:
                print("Relevé enregistré avec succès")
                # Recharger les relevés après ajout
                releves = charger_releves()
                # Formater les dates pour l'affichage
                for releve in releves:
                    if "timestamp" in releve:
                        try:
                            date_obj = datetime.fromisoformat(releve["timestamp"])
                            releve["timestamp"] = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception as e:
                            print(f"Erreur lors du formatage de la date: {e}")
                            releve["timestamp"] = "Date inconnue"
                releves = sorted(releves, key=lambda r: (r["annee"], r["mois"]), reverse=True)
                return render_template("releve_20.html",
                                     sites=sites_list,
                                     debitmetres=debitmetres,
                                     releves=releves,
                                     selected_site=site,
                                     mois=mois,
                                     annee=annee,
                                     just_saved=True)
            else:
                print("Erreur: Un relevé existe déjà")
                return render_template("releve_20.html",
                                     sites=sites_list,
                                     debitmetres=debitmetres,
                                     releves=releves,
                                     error="Un relevé existe déjà pour ce site/mois/année",
                                     selected_site=site,
                                     mois=mois,
                                     annee=annee,
                                     just_saved=False)
        else:
            print("Erreur: Problème lors de l'upload des photos")
            return render_template("releve_20.html",
                                 sites=sites_list,
                                 debitmetres=debitmetres,
                                 releves=releves,
                                 error="Une erreur est survenue lors de l'upload des photos",
                                 selected_site=site,
                                 mois=mois,
                                 annee=annee,
                                 just_saved=False)
    
    return render_template("releve_20.html",
                         sites=sites_list,
                         debitmetres=debitmetres,
                         releves=releves,
                         selected_site=request.args.get('site'),
                         mois=request.args.get('mois', mois_courant),  # Utilise le mois courant par défaut
                         annee=request.args.get('annee', annee_courante),  # Utilise l'année courante par défaut
                         error=error if 'error' in locals() else None,
                         just_saved=just_saved if 'just_saved' in locals() else None)

@app.route("/supprimer_releve")
@require_access([13, 14])  # Gestion photos : niveau 13 et admin
def supprimer_releve():
    site = request.args.get("site")
    mois = request.args.get("mois")
    annee = request.args.get("annee")
    if not (site and mois and annee):
        return redirect(url_for("releve_20"))
    
    # Charger et filtrer les relevés
    releves = charger_releves()
    
    # Trouver le relevé à supprimer pour récupérer les noms des fichiers photos
    releve_a_supprimer = None
    for r in releves:
        if str(r["site"]) == str(site) and str(r["mois"]) == str(mois) and str(r["annee"]) == str(annee):
            releve_a_supprimer = r
            break
    
    # Supprimer les fichiers photos et le dossier
    if releve_a_supprimer and "photos" in releve_a_supprimer:
        # Identifier le dossier du relevé
        subfolder_name = f"{site.replace(' ', '_')}_{mois}_{annee}"
        subfolder_path = os.path.join(PHOTOS_DIR, subfolder_name)
        
        try:
            # Supprimer d'abord les fichiers
            for debitmetre, filename in releve_a_supprimer["photos"].items():
                photo_path = os.path.join(PHOTOS_DIR, filename)
                if os.path.exists(photo_path):
                    os.remove(photo_path)
                    print(f"Photo supprimée : {photo_path}")
            
            # Supprimer le dossier s'il est vide
            if os.path.exists(subfolder_path):
                if not os.listdir(subfolder_path):  # Vérifier si le dossier est vide
                    os.rmdir(subfolder_path)
                    print(f"Dossier supprimé : {subfolder_path}")
        except Exception as e:
            print(f"Erreur lors de la suppression des fichiers/dossier : {e}")
    
    # Filtrer le relevé de la liste
    releves = [r for r in releves if not (str(r["site"]) == str(site) and str(r["mois"]) == str(mois) and str(r["annee"]) == str(annee))]
    
    # Sauvegarder la liste mise à jour
    with open(RELEVES_JSON, "w", encoding="utf-8") as f:
        json.dump(releves, f, ensure_ascii=False, indent=2)
    
    return redirect(url_for("releve_20"))

@app.route("/voir_photos")
@require_access([13, 14])  # Gestion photos : niveau 13 et admin
def voir_photos():
    site = request.args.get("site")
    mois = request.args.get("mois")
    annee = request.args.get("annee")
    if not (site and mois and annee):
        return redirect(url_for("releve_20"))
    
    # Trouver le relevé correspondant
    releves = charger_releves()
    releve = next((r for r in releves if str(r["site"]) == str(site) and str(r["mois"]) == str(mois) and str(r["annee"]) == str(annee)), None)
    
    if releve:
        return render_template("voir_photos.html", releve=releve, site=site, mois=mois, annee=annee)
    else:
        return redirect(url_for("releve_20"))

@app.route("/photos_releves/<path:filename>")
def serve_photo(filename):
    """Sert les photos depuis le dossier photos_releves, y compris depuis les sous-dossiers"""
    # La fonction send_from_directory gère automatiquement les sous-dossiers avec le type path
    return send_from_directory(PHOTOS_DIR, filename)

@app.route("/visualisation", methods=["GET", "POST"])
@require_access([11, 13, 14])  # Visualisation : niveaux 11, 13 et admin
def visualisation():
    sites_list = list(sites.keys())
    mesures_par_site = sites
    plot_url = None

    if request.method == "POST":
        site = request.form["site"]
        parametre = request.form["parametre"]
        semaine = request.form.get("semaine")
        annee = request.form.get("annee")

        # Générer une clé de cache unique pour ce graphique
        cache_key = get_cache_key(site, parametre, semaine, annee, "visualisation")
        
        # Vérifier si le graphique est en cache
        cached_image = load_from_cache(cache_key)
        if cached_image:
            plot_url = base64.b64encode(cached_image).decode()
        else:
            df = charger_donnees(site)
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"])
            df = df[df["Statut"] == "Validé"]
            df = df.sort_values("Date")

            # Ajouter l'année et la semaine ISO
            if semaine and annee:
                df["Annee"] = df["Date"].dt.isocalendar().year
                df["Semaine"] = df["Date"].dt.isocalendar().week
                df = df[(df["Annee"] == int(annee)) & (df["Semaine"] == int(semaine))]

            if parametre in ["Coagulant", "Eau potable"]:
                df = df[df["Date"].dt.weekday == 0]
                df["Semaine"] = df["Date"].dt.isocalendar().week
                semaines = df["Semaine"].tolist()
                valeurs = pd.to_numeric(df[parametre], errors="coerce").fillna(0).tolist()
                titre = f"{parametre} hebdomadaire ({site})"

                plt.figure(figsize=(10, 5))
                plt.plot(semaines, valeurs, marker="o")
                plt.title(titre)
                plt.xlabel("Semaine")
                plt.ylabel(parametre)
                plt.xticks(semaines, ["S" + str(s) for s in semaines])
                plt.tight_layout()

            elif parametre == "Floculant":
                df["Semaine"] = df["Date"].dt.isocalendar().week
                df[parametre] = pd.to_numeric(df[parametre], errors="coerce").fillna(0)
                df_semaine = df.groupby("Semaine")[parametre].sum().reset_index()
                semaines = df_semaine["Semaine"].tolist()
                valeurs = df_semaine[parametre].tolist()
                titre = f"Consommation hebdomadaire de {parametre} ({site})"

                plt.figure(figsize=(10, 5))
                plt.plot(semaines, valeurs, marker="o")
                plt.title(titre)
                plt.xlabel("Semaine")
                plt.ylabel("Consommation")
                plt.xticks(semaines, ["S" + str(s) for s in semaines])
                plt.tight_layout()

            elif parametre in parametres_compteurs.get(site, []):
                df[parametre] = pd.to_numeric(df[parametre], errors='coerce').fillna(0)
                df["Delta"] = df[parametre].diff().fillna(0)
                dates = df["Date"].dt.date.tolist()
                valeurs = df["Delta"].tolist()
                titre = f"Variation journalière de {parametre} - {site}"

                plt.figure(figsize=(10, 5))
                plt.plot(dates, valeurs, marker="o")
                plt.title(titre)
                plt.xticks(rotation=45)
                plt.tight_layout()

            else:
                dates = df["Date"].dt.date.tolist()
                valeurs = pd.to_numeric(df[parametre], errors="coerce").fillna(0).tolist()
                titre = f"Mesure de {parametre} - {site}"

                plt.figure(figsize=(10, 5))
                plt.plot(dates, valeurs, marker="o")
                plt.title(titre)
                plt.xticks(rotation=45)
                plt.tight_layout()

            img = io.BytesIO()
            plt.savefig(img, format="png", dpi=100, bbox_inches='tight')
            img.seek(0)
            image_data = img.read()
            
            # Sauvegarder en cache
            save_to_cache(cache_key, image_data)
            
            plot_url = base64.b64encode(image_data).decode()
            plt.close()

    return render_template("visualisation.html", 
                           sites=sites_list, 
                           mesures_par_site=mesures_par_site,
                           plot_url=plot_url)

@app.route("/rapports")
@require_access([14])  # Liste des rapports : admin uniquement
def rapports_liste():
    rapports = []
    if os.path.exists(RAPPORTS_JSON):
        with open(RAPPORTS_JSON, "r", encoding="utf-8") as f:
            try:
                rapports = json.load(f)
            except Exception:
                rapports = []
    # Tri par année, semaine, site
    rapports = sorted(rapports, key=lambda r: (r["annee"], r["semaine"], r["site"]))
    return render_template("rapports.html", rapports=rapports)

@app.route("/supprimer_rapport")
@require_access([14])  # Suppression rapport : admin uniquement
def supprimer_rapport():
    site = request.args.get("site")
    semaine = request.args.get("semaine")
    annee = request.args.get("annee")
    if not (site and semaine and annee):
        return redirect(url_for("rapport"))
    # Charger et filtrer la bibliothèque
    if os.path.exists(RAPPORTS_JSON):
        with open(RAPPORTS_JSON, "r", encoding="utf-8") as f:
            try:
                rapports = json.load(f)
            except Exception:
                rapports = []
        rapports = [r for r in rapports if not (str(r["site"]) == str(site) and str(r["semaine"]) == str(semaine) and str(r["annee"]) == str(annee))]
        with open(RAPPORTS_JSON, "w", encoding="utf-8") as f:
            json.dump(rapports, f, ensure_ascii=False, indent=2)
    # (Optionnel) supprimer le cache associé
    # Rediriger vers la page rapport avec le site sélectionné
    return redirect(url_for("rapport", site=site))

@app.route("/rapport", methods=["GET", "POST"])
@require_access([11, 14])  # Rapport : niveau 11 et admin
def rapport():
    try:
        sites_list = list(sites.keys())
        rapports = []
        all_rapports = []
        
        # Charger les rapports existants
        if os.path.exists(RAPPORTS_JSON):
            with open(RAPPORTS_JSON, "r", encoding="utf-8") as f:
                try:
                    all_rapports = json.load(f)
                except Exception as e:
                    print(f"Erreur lors de la lecture des rapports: {str(e)}")
                    all_rapports = []

        # Construction de la table croisée année/semaine/sites
        index = set()
        for r in all_rapports:
            index.add((int(r["annee"]), int(r["semaine"])))
        index = sorted(index, reverse=True)
        
        # Pour chaque (année, semaine), on regarde si un rapport existe pour chaque site
        table_rapports = []
        for annee, semaine in index:
            ligne = {"annee": annee, "semaine": semaine}
            for site in sites_list:
                found = next((r for r in all_rapports if int(r["annee"]) == annee and int(r["semaine"]) == semaine and r["site"] == site), None)
                ligne[site] = found
            table_rapports.append(ligne)

        # Affichage d'un rapport existant via GET
        if request.method == "GET" and "semaine" in request.args and "annee" in request.args and "site" in request.args:
            try:
                semaine = int(request.args.get("semaine"))
                annee = int(request.args.get("annee"))
                site = request.args.get("site")
                
                if site not in sites:
                    print(f"Site invalide: {site}")
                    return redirect(url_for("rapport"))
                
                rapports_result = []
                df = charger_donnees(site)
                
                if df is not None and not df.empty:
                    # Nettoyage et filtrage
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                    df = df[df["Statut"] == "Validé"]
                    
                    # Calculer l'année et la semaine ISO
                    df["Annee"] = df["Date"].dt.isocalendar().year
                    df["Semaine"] = df["Date"].dt.isocalendar().week
                    
                    # Filtrer la semaine/année demandée
                    df_filtered = df[(df["Annee"] == annee) & (df["Semaine"] == semaine)]
                    
                    if df_filtered.empty:
                        print(f"Aucune donnée pour {site} - S{semaine}/{annee}")
                        return render_template("rapport_resultat.html", rapports=[], semaine=semaine, annee=annee)
                    
                    # Trier par date pour avoir les graphiques dans le bon ordre
                    df_filtered = df_filtered.sort_values("Date")

                    for parametre in sites[site]:
                        cache_key = get_cache_key(site, parametre, semaine, annee, "rapport")
                        cached_image = load_from_cache(cache_key)
                        if cached_image:
                            plot_url = base64.b64encode(cached_image).decode()
                            rapports_result.append({"site": site, "parametre": parametre, "plot": plot_url})
                            continue
                        img = io.BytesIO()
                        plt.figure(figsize=(8, 4))
                        # Cas 1 : Historique annuel pour Eau potable, Coagulant, Floculant
                        if parametre in ["Eau potable", "Coagulant", "Floculant"]:
                            df_annuel = df[(df["Annee"] == annee)]
                            if parametre == "Coagulant" or parametre == "Eau potable":
                                # Afficher uniquement les valeurs du lundi
                                df_annuel = df_annuel[df_annuel["Date"].dt.weekday == 0]
                            df_annuel[parametre] = pd.to_numeric(df_annuel[parametre], errors="coerce").fillna(0)
                            if not df_annuel.empty:
                                plt.plot(df_annuel["Semaine"], df_annuel[parametre], marker="o")
                                plt.title(f"{site} - {parametre} (année {annee})", pad=20)
                                plt.xlabel("Semaine")
                                plt.ylabel("Valeur brute")
                                plt.xticks(df_annuel["Semaine"], ["S" + str(s) for s in df_annuel["Semaine"]], rotation=45)
                        # Cas 2 : Compteurs (delta)
                        elif parametre in parametres_compteurs[site]:
                            df_filtered[parametre] = pd.to_numeric(df_filtered[parametre], errors="coerce")
                            if not df_filtered.empty:
                                valeurs = df_filtered[parametre].diff().fillna(0)
                                dates = df_filtered["Date"].dt.strftime("%d/%m")
                                plt.plot(dates, valeurs, marker="o")
                                plt.title(f"{site} - {parametre} (delta S{semaine})", pad=20)
                                plt.xlabel("Date")
                                plt.ylabel("Delta journalier")
                                plt.xticks(rotation=45)
                        # Cas 3 : Autres paramètres (valeur brute)
                        else:
                            df_filtered[parametre] = pd.to_numeric(df_filtered[parametre], errors="coerce")
                            if not df_filtered.empty:
                                dates = df_filtered["Date"].dt.strftime("%d/%m")
                                plt.plot(dates, df_filtered[parametre], marker="o")
                                plt.title(f"{site} - {parametre} (S{semaine})", pad=20)
                                plt.xlabel("Date")
                                plt.ylabel("Valeur brute")
                                plt.xticks(rotation=45)
                        plt.tight_layout()
                        plt.savefig(img, format="png", dpi=100, bbox_inches='tight')
                        img.seek(0)
                        image_data = img.read()
                        save_to_cache(cache_key, image_data)
                        plot_url = base64.b64encode(image_data).decode()
                        plt.close()
                        rapports_result.append({"site": site, "parametre": parametre, "plot": plot_url})
                return render_template("rapport_resultat.html", rapports=rapports_result, semaine=semaine, annee=annee)
            except Exception as e:
                print(f"Erreur lors de la génération du rapport GET: {str(e)}")
                return redirect(url_for("rapport"))
        # Génération d'un rapport via POST
        if request.method == "POST":
            try:
                semaine = int(request.form["semaine"])
                annee = int(request.form["annee"])
                site = request.form["site"]
                if site not in sites:
                    print(f"Site invalide: {site}")
                    return redirect(url_for("rapport"))
                enregistrer_rapport(semaine, annee, site)
                return redirect(url_for("rapport", semaine=semaine, annee=annee, site=site))
            except Exception as e:
                print(f"Erreur lors de la génération du rapport POST: {str(e)}")
                return render_template("rapport_form.html", table_rapports=table_rapports, sites=sites_list, error="Une erreur est survenue lors de la génération du rapport.")
        return render_template("rapport_form.html", table_rapports=table_rapports, sites=sites_list)
    except Exception as e:
        print(f"Erreur générale dans la route /rapport: {str(e)}")
        return render_template("rapport_form.html", sites=sites_list, error="Une erreur est survenue lors du chargement de la page.")

@app.route("/rapport_pdf")
@require_access([11, 14])  # Rapport PDF : niveau 11 et admin
def rapport_pdf():
    try:
        semaine = int(request.args.get("semaine"))
        annee = int(request.args.get("annee"))
        site = request.args.get("site")
        
        if site not in sites:
            print(f"Site invalide: {site}")
            return redirect(url_for("rapport"))
        
        # Charger les données
        df = charger_donnees(site)
        if df is None or df.empty:
            return "Aucune donnée disponible", 404
            
        # Préparer les données pour le PDF
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df[df["Statut"] == "Validé"]
        df["Annee"] = df["Date"].dt.isocalendar().year
        df["Semaine"] = df["Date"].dt.isocalendar().week
        
        # Créer le document PDF
        buffer = io.BytesIO()
        
        # Définir les marges et la taille de page
        PAGE_HEIGHT = A4[1]
        PAGE_WIDTH = A4[0]
        
        class PDFWithHeader(SimpleDocTemplate):
            def __init__(self, *args, **kwargs):
                self.title = kwargs.pop('title', '')  # Extraire le titre des kwargs
                SimpleDocTemplate.__init__(self, *args, **kwargs)
                self.header_text = ""
            
            def build(self, flowables, **kwargs):
                self._calc()  # Nécessaire pour avoir les dimensions correctes
                frame = Frame(
                    self.leftMargin, self.bottomMargin, 
                    self.width, self.height,
                    id='normal'
                )
                template = PageTemplate(
                    'normal',
                    [frame],
                    onPage=self.add_header
                )
                self.addPageTemplates([template])
                SimpleDocTemplate.build(self, flowables, **kwargs)
            
            def add_header(self, canvas, doc):
                canvas.saveState()
                canvas.setFont('Helvetica', 10)
                # Ajouter le texte d'en-tête en haut à gauche
                canvas.drawString(doc.leftMargin, PAGE_HEIGHT - 20, f"{site} - S{semaine}/{annee}")
                canvas.restoreState()
        
        # Créer le document avec les métadonnées
        doc = PDFWithHeader(
            buffer,
            pagesize=A4,
            topMargin=30,
            title=f"{site}-S{semaine}-{annee}",
            author="Relevés STE",
            subject=f"Rapport de données {site} - Semaine {semaine}/{annee}",
            creator="Relevés STE"
        )
        story = []
        
        # Préparer les graphiques
        graphs = []
        for parametre in sites[site]:
            # Générer et sauvegarder le graphique
            plt.figure(figsize=(8, 4))
            
            if parametre in ["Coagulant", "Eau potable"]:
                df_annuel = df[(df["Date"].dt.year == datetime.now().year) & (df["Date"].dt.weekday == 0)]
                df_annuel["Semaine"] = df_annuel["Date"].dt.isocalendar().week
                valeurs = pd.to_numeric(df_annuel[parametre], errors="coerce").fillna(0)
                semaines = df_annuel["Semaine"]
                plt.plot(semaines, valeurs, marker="o")
                plt.title(f"{parametre}", pad=20)
                plt.xlabel("Semaine")
                plt.xticks(semaines, ["S" + str(s) for s in semaines])
            elif parametre == "Floculant":
                df_floc = df[df["Date"].dt.year == datetime.now().year]
                df_floc["Semaine"] = df_floc["Date"].dt.isocalendar().week
                df_floc[parametre] = pd.to_numeric(df_floc[parametre], errors="coerce").fillna(0)
                df_floc = df_floc.groupby("Semaine")[parametre].sum().reset_index()
                plt.plot(df_floc["Semaine"], df_floc[parametre], marker="o")
                plt.title(f"{site} - Floculant", pad=20)
                plt.xlabel("Semaine")
                plt.xticks(df_floc["Semaine"], ["S" + str(s) for s in df_floc["Semaine"]])
            elif parametre in parametres_compteurs[site]:
                df_semaine = df[(df["Annee"] == annee) & (df["Semaine"] == semaine)]
                valeurs = pd.to_numeric(df_semaine[parametre], errors="coerce").fillna(0).diff().fillna(0)
                dates = df_semaine["Date"].dt.date
                plt.plot(dates, valeurs, marker="o")
                plt.title(f"{site} - {parametre}", pad=20)
                plt.xticks(rotation=45)
            elif parametre in parametres_directs[site]:
                df_semaine = df[(df["Annee"] == annee) & (df["Semaine"] == semaine)]
                valeurs = pd.to_numeric(df_semaine[parametre], errors="coerce").fillna(0)
                dates = df_semaine["Date"].dt.date
                plt.plot(dates, valeurs, marker="o")
                plt.title(f"{site} - {parametre}", pad=20)
                plt.xticks(rotation=45)
            
            plt.tight_layout()
            
            # Sauvegarder le graphique dans un buffer temporaire
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
            img_buffer.seek(0)
            
            # Créer l'image et définir sa taille
            img = Image(img_buffer)
            img.drawHeight = 3.2*inch  # Réduire la hauteur pour avoir 3 graphiques par page
            img.drawWidth = 7*inch
            
            graphs.append(img)
            plt.close()
        
        # Calculer le nombre de pages nécessaires
        nb_graphs = len(graphs)
        nb_pages = (nb_graphs + 2) // 3  # Arrondi supérieur
        
        # Répartir les graphiques sur les pages
        for page in range(nb_pages):
            start_idx = page * 3
            end_idx = min(start_idx + 3, nb_graphs)
            
            # Ajouter les graphiques de cette page
            for i in range(start_idx, end_idx):
                story.append(graphs[i])
            
            # Compléter avec des espaces vides si nécessaire pour maintenir la mise en page
            for i in range(end_idx - start_idx, 3):
                story.append(Spacer(1, 3.2*inch))
            
            # Ajouter un saut de page sauf pour la dernière page
            if page < nb_pages - 1:
                story.append(PageBreak())
        
        # Générer le PDF
        doc.build(story)
        
        # Préparer la réponse
        buffer.seek(0)
        pdf_content = buffer.getvalue()
        pdf_title = f"{site}-S{semaine}-{annee}"
        
        # Créer une réponse HTML qui inclut le PDF avec le bon titre
        html_content = f"""
        <html>
        <head><title>{pdf_title}</title></head>
        <body><embed src="data:application/pdf;base64,{base64.b64encode(pdf_content).decode()}" width="100%" height="100%" type="application/pdf"></body>
        </html>
        """
        
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html'
        return response
        
    except Exception as e:
        print(f"Erreur lors de la génération du PDF: {str(e)}")
        return str(e), 500

@app.route('/telecharger_mesures')
@require_access([11, 14])  # Téléchargement : niveau 11 et admin
def telecharger_mesures():
    """Télécharge directement le fichier Excel sans créer de copie"""
    if os.path.exists(FICHIER):
        return send_file(FICHIER, as_attachment=True, download_name='mesures_export.xlsx')
    else:
        # Si le fichier n'existe pas, retourner une erreur
        return "Fichier non trouvé", 404

@app.route('/gestion_excel', methods=['GET', 'POST'])
@require_access([14])  # Gestion Excel : admin uniquement
def gestion_excel():
    site = request.args.get('site') or list(sites.keys())[0]
    message = None
    
    try:
        # S'assurer que le fichier existe et contient les bonnes colonnes
        if not os.path.exists(FICHIER):
            initialiser_fichier()
        
        # Charger les données
        df = charger_donnees(site)
        print(f"\n=== Chargement des données pour {site} ===")
        
        if df is None or df.empty:
            print(f"Aucune donnée trouvée pour {site}, création d'un DataFrame vide")
            # Créer un DataFrame avec les bonnes colonnes
            columns = ["Date", "Statut"] + sites[site]
            df = pd.DataFrame(columns=columns)
            # Ajouter une ligne exemple
            df.loc[0] = {
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Statut": "Validé",
                **{col: "" for col in sites[site]}
            }
            # Sauvegarder le DataFrame
            sauvegarder_donnees(df, site)
        
        # Convertir les dates en format string pour l'affichage
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        
        # Remplacer les valeurs NaN/None par des chaînes vides pour l'affichage
        df = df.fillna('')
        
        print(f"Dimensions du DataFrame: {df.shape}")
        print("Colonnes:", df.columns.tolist())
        print("\nPremières lignes:")
        print(df.head().to_dict('records'))

        if request.method == 'POST':
            if request.is_json:
                data = request.get_json()
                print("\n=== Données reçues du client ===")
                print(data)
                
                # Créer un nouveau DataFrame à partir des données JSON
                new_df = pd.DataFrame(data['data'], columns=data['headers'])
                
                # Convertir la colonne Date en datetime si elle existe
                if 'Date' in new_df.columns:
                    new_df['Date'] = pd.to_datetime(new_df['Date'])
                
                # Nettoyer les données avant la sauvegarde
                new_df = new_df.replace('', pd.NA)
                
                sauvegarder_donnees(new_df, site)
                return jsonify({'success': True})

    except Exception as e:
        print(f"\n=== ERREUR ===\n{str(e)}")
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)})
        message = f"Erreur : {str(e)}"
        df = pd.DataFrame(columns=["Date", "Statut"] + sites[site])

    return render_template('gestion_excel.html', 
                         df=df,
                         sites=sites.keys(),
                         site=site,
                         message=message)

if __name__ == '__main__':
    # Nettoyer le cache expiré au démarrage
    nettoyer_cache_expire()
    # Lancement du serveur en mode production
    app.run(host='0.0.0.0', port=5000, debug=False)
