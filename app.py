from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, send_file
import pandas as pd
import os
import matplotlib
matplotlib.use('Agg')  # Backend non-interactif pour de meilleures performances
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime, timedelta
import hashlib
import pickle
from functools import lru_cache, wraps
import json

app = Flask(__name__)
app.secret_key = 'votre_cle_secrete_a_remplacer'  # À personnaliser pour la sécurité

FICHIER = "https://vincic.sharepoint.com/sites/TELT-LOT-2/_layouts/15/download.aspx?SourceUrl=/sites/TELT-LOT-2/DEX/04-LOGISTIQUE%20%26%20MATERIEL/STE/APP/Relev%C3%A9s%20STE/mesures.xlsx"  # Lecture seule depuis SharePoint
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
    if not os.path.exists(FICHIER):
        print(f"Création du fichier {FICHIER}")
        dfs = {}
        for site, mesures in sites.items():
            # Créer un DataFrame vide avec les bonnes colonnes
            columns = ["Date", "Statut"] + mesures
            dfs[site] = pd.DataFrame(columns=columns)
        
        # Sauvegarder dans un nouveau fichier Excel
        with pd.ExcelWriter(FICHIER, engine='openpyxl') as writer:
            for site, df in dfs.items():
                df.to_excel(writer, sheet_name=site, index=False)
        print(f"Fichier {FICHIER} créé avec succès")

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
        # Retourner un DataFrame vide mais avec les bonnes colonnes
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

    with pd.ExcelWriter(FICHIER, engine="openpyxl", mode="w") as writer:
        for sheet, data in dfs.items():
            data.to_excel(writer, sheet_name=sheet, index=False)
    
    # Invalider le cache après sauvegarde
    charger_donnees_cached.cache_clear()
    invalider_cache_site(site)

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

# Page de connexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        code = request.form.get('code')
        if code in ['12', '13', '14']:
            session['access_code'] = int(code)
            return redirect(url_for('index'))
        else:
            error = "Code d'accès incorrect."
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Décorateur pour protéger les routes
def require_access(min_code):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'access_code' not in session or session['access_code'] < min_code:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Protéger les routes selon le niveau d'accès
@app.route("/")
@require_access(12)
def index():
    return render_template("index.html")

@app.route("/saisie/<site>", methods=["GET", "POST"])
@require_access(12)
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
                    df.loc[idx, k] = ""
                else:
                    df.loc[idx, k] = v
        else:
            df.loc[len(df)] = ligne

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

@app.route("/visualisation", methods=["GET", "POST"])
@require_access(12)
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

            # Filtrer par année si spécifiée, sinon utiliser l'année courante
            if annee:
                df = df[df["Date"].dt.year == int(annee)]
            else:
                current_year = datetime.now().year
                df = df[df["Date"].dt.year == current_year]

            # Filtrer par semaine si spécifiée
            if semaine and parametre not in ["Coagulant", "Eau potable", "Floculant"]:
                df["Semaine"] = df["Date"].dt.isocalendar().week
                df = df[df["Semaine"] == int(semaine)]

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
@require_access(14)
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
@require_access(14)
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
@require_access(13)
def releve_20():
    sites_list = list(debitmetres.keys())
    releves = charger_releves()
    # Trier par date (plus récent en premier)
    releves = sorted(releves, key=lambda r: (r["annee"], r["mois"]), reverse=True)
    
    if request.method == "POST":
        site = request.form["site"]
        mois = int(request.form["mois"])
        annee = int(request.form["annee"])
        
        # Traitement des photos uploadées
        photos_paths = {}
        for debitmetre in debitmetres[site]:
            # Vérifier les deux possibilités : fichier ou photo caméra
            photo_key = f"photo_{debitmetre.replace(' ', '_')}"
            photo_key_camera = f"{photo_key}_camera"
            
            photo_file = None
            if photo_key in request.files:
                photo_file = request.files[photo_key]
            elif photo_key_camera in request.files:
                photo_file = request.files[photo_key_camera]
            
            if photo_file and photo_file.filename:
                print(f"Traitement de la photo pour {debitmetre}: {photo_file.filename}")
                filename = sauvegarder_photo(photo_file, site, debitmetre, mois, annee)
                if filename:
                    photos_paths[debitmetre] = filename
                    print(f"Photo sauvegardée: {filename}")
        
        # Enregistrer le relevé
        if photos_paths:
            print(f"Tentative d'enregistrement du relevé avec {len(photos_paths)} photos")
            success = enregistrer_releve(site, mois, annee, photos_paths)
            if success:
                print("Relevé enregistré avec succès")
                # Recharger les relevés après ajout
                releves = charger_releves()
                releves = sorted(releves, key=lambda r: (r["annee"], r["mois"]), reverse=True)
                return render_template("releve_20.html", sites=sites_list, debitmetres=debitmetres, 
                                     releves=releves, selected_site=site, just_saved=True, mois=mois, annee=annee)
            else:
                print("Erreur: Un relevé existe déjà")
                return render_template("releve_20.html", sites=sites_list, debitmetres=debitmetres, 
                                     releves=releves, error="Un relevé existe déjà pour ce site/mois/année")
        else:
            print("Erreur: Aucune photo n'a été uploadée")
            return render_template("releve_20.html", sites=sites_list, debitmetres=debitmetres, 
                                 releves=releves, error="Veuillez sélectionner au moins une photo")
    
    return render_template("releve_20.html", sites=sites_list, debitmetres=debitmetres, releves=releves)

@app.route("/supprimer_releve")
@require_access(13)
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
@require_access(13)
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

@app.route("/rapport", methods=["GET", "POST"])
@require_access(14)
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
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                    df = df[df["Statut"] == "Validé"]
                    df["Annee"] = df["Date"].dt.year
                    df["Semaine"] = df["Date"].dt.isocalendar().week
                    
                    for parametre in sites[site]:
                        cache_key = get_cache_key(site, parametre, semaine, annee, "rapport")
                        cached_image = load_from_cache(cache_key)
                        if cached_image:
                            plot_url = base64.b64encode(cached_image).decode()
                            rapports_result.append({"site": site, "parametre": parametre, "plot": plot_url})
                            continue
                        
                        # Si pas en cache, on régénère le graphique
                        img = io.BytesIO()
                        plt.figure(figsize=(8, 4))
                        
                        if parametre in ["Coagulant", "Eau potable"]:
                            df_annuel = df[(df["Date"].dt.year == datetime.now().year) & (df["Date"].dt.weekday == 0)]
                            df_annuel["Semaine"] = df_annuel["Date"].dt.isocalendar().week
                            valeurs = pd.to_numeric(df_annuel[parametre], errors="coerce").fillna(0)
                            semaines = df_annuel["Semaine"]
                            plt.plot(semaines, valeurs, marker="o")
                            plt.title(f"{site} - {parametre} (année en cours)")
                            plt.xlabel("Semaine")
                            plt.xticks(semaines, ["S" + str(s) for s in semaines])
                        elif parametre == "Floculant":
                            df_floc = df[df["Date"].dt.year == datetime.now().year]
                            df_floc["Semaine"] = df_floc["Date"].dt.isocalendar().week
                            df_floc[parametre] = pd.to_numeric(df_floc[parametre], errors="coerce").fillna(0)
                            df_floc = df_floc.groupby("Semaine")[parametre].sum().reset_index()
                            plt.plot(df_floc["Semaine"], df_floc[parametre], marker="o")
                            plt.title(f"{site} - Floculant hebdo (année en cours)")
                            plt.xlabel("Semaine")
                            plt.xticks(df_floc["Semaine"], ["S" + str(s) for s in df_floc["Semaine"]])
                        elif parametre in parametres_compteurs[site]:
                            df_semaine = df[(df["Annee"] == annee) & (df["Semaine"] == semaine)]
                            valeurs = pd.to_numeric(df_semaine[parametre], errors="coerce").fillna(0).diff().fillna(0)
                            dates = df_semaine["Date"].dt.date
                            plt.plot(dates, valeurs, marker="o")
                            plt.title(f"{site} - Delta {parametre}")
                            plt.xticks(rotation=45)
                        elif parametre in parametres_directs[site]:
                            df_semaine = df[(df["Annee"] == annee) & (df["Semaine"] == semaine)]
                            valeurs = pd.to_numeric(df_semaine[parametre], errors="coerce").fillna(0)
                            dates = df_semaine["Date"].dt.date
                            plt.plot(dates, valeurs, marker="o")
                            plt.title(f"{site} - {parametre}")
                            plt.xticks(rotation=45)
                        else:
                            plt.close()
                            continue
                            
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
                
                rapports_result = []
                df = charger_donnees(site)
                
                if df is not None and not df.empty:
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                    df = df[df["Statut"] == "Validé"]
                    df["Annee"] = df["Date"].dt.year
                    df["Semaine"] = df["Date"].dt.isocalendar().week
                    
                    for parametre in sites[site]:
                        cache_key = get_cache_key(site, parametre, semaine, annee, "rapport")
                        cached_image = load_from_cache(cache_key)
                        if cached_image:
                            plot_url = base64.b64encode(cached_image).decode()
                            rapports_result.append({"site": site, "parametre": parametre, "plot": plot_url})
                            continue
                        
                        img = io.BytesIO()
                        plt.figure(figsize=(8, 4))
                        
                        if parametre in ["Coagulant", "Eau potable"]:
                            df_annuel = df[(df["Date"].dt.year == datetime.now().year) & (df["Date"].dt.weekday == 0)]
                            df_annuel["Semaine"] = df_annuel["Date"].dt.isocalendar().week
                            valeurs = pd.to_numeric(df_annuel[parametre], errors="coerce").fillna(0)
                            semaines = df_annuel["Semaine"]
                            plt.plot(semaines, valeurs, marker="o")
                            plt.title(f"{site} - {parametre} (année en cours)")
                            plt.xlabel("Semaine")
                            plt.xticks(semaines, ["S" + str(s) for s in semaines])
                        elif parametre == "Floculant":
                            df_floc = df[df["Date"].dt.year == datetime.now().year]
                            df_floc["Semaine"] = df_floc["Date"].dt.isocalendar().week
                            df_floc[parametre] = pd.to_numeric(df_floc[parametre], errors="coerce").fillna(0)
                            df_floc = df_floc.groupby("Semaine")[parametre].sum().reset_index()
                            plt.plot(df_floc["Semaine"], df_floc[parametre], marker="o")
                            plt.title(f"{site} - Floculant hebdo (année en cours)")
                            plt.xlabel("Semaine")
                            plt.xticks(df_floc["Semaine"], ["S" + str(s) for s in df_floc["Semaine"]])
                        elif parametre in parametres_compteurs[site]:
                            df_semaine = df[(df["Annee"] == annee) & (df["Semaine"] == semaine)]
                            valeurs = pd.to_numeric(df_semaine[parametre], errors="coerce").fillna(0).diff().fillna(0)
                            dates = df_semaine["Date"].dt.date
                            plt.plot(dates, valeurs, marker="o")
                            plt.title(f"{site} - Delta {parametre}")
                            plt.xticks(rotation=45)
                        elif parametre in parametres_directs[site]:
                            df_semaine = df[(df["Annee"] == annee) & (df["Semaine"] == semaine)]
                            valeurs = pd.to_numeric(df_semaine[parametre], errors="coerce").fillna(0)
                            dates = df_semaine["Date"].dt.date
                            plt.plot(dates, valeurs, marker="o")
                            plt.title(f"{site} - {parametre}")
                            plt.xticks(rotation=45)
                        else:
                            plt.close()
                            continue
                            
                        plt.tight_layout()
                        plt.savefig(img, format="png", dpi=100, bbox_inches='tight')
                        img.seek(0)
                        image_data = img.read()
                        save_to_cache(cache_key, image_data)
                        plot_url = base64.b64encode(image_data).decode()
                        plt.close()
                        rapports_result.append({"site": site, "parametre": parametre, "plot": plot_url})
                    
                    enregistrer_rapport(semaine, annee, site)
                    
                    # Après génération, recharger la table croisée
                    if os.path.exists(RAPPORTS_JSON):
                        with open(RAPPORTS_JSON, "r", encoding="utf-8") as f:
                            try:
                                all_rapports = json.load(f)
                            except Exception:
                                all_rapports = []
                        index = set()
                        for r in all_rapports:
                            index.add((int(r["annee"]), int(r["semaine"])))
                        index = sorted(index, reverse=True)
                        table_rapports = []
                        for annee_, semaine_ in index:
                            ligne = {"annee": annee_, "semaine": semaine_}
                            for site_ in sites_list:
                                found = next((r for r in all_rapports if int(r["annee"]) == annee_ and int(r["semaine"]) == semaine_ and r["site"] == site_), None)
                                ligne[site_] = found
                            table_rapports.append(ligne)
                
                return render_template("rapport_form.html", table_rapports=table_rapports, sites=sites_list, just_generated=True, semaine=semaine, annee=annee)
            except Exception as e:
                print(f"Erreur lors de la génération du rapport POST: {str(e)}")
                return render_template("rapport_form.html", table_rapports=table_rapports, sites=sites_list, error="Une erreur est survenue lors de la génération du rapport.")
        
        # Affichage du formulaire par défaut
        return render_template("rapport_form.html", table_rapports=table_rapports, sites=sites_list)
        
    except Exception as e:
        print(f"Erreur générale dans la route /rapport: {str(e)}")
        return render_template("rapport_form.html", sites=sites_list, error="Une erreur est survenue lors du chargement de la page.")

@app.route('/telecharger_mesures')
@require_access(14)
def telecharger_mesures():
    """Télécharge directement le fichier Excel sans créer de copie"""
    if os.path.exists(FICHIER):
        return send_file(FICHIER, as_attachment=True, download_name='mesures_export.xlsx')
    else:
        # Si le fichier n'existe pas, retourner une erreur
        return "Fichier non trouvé", 404

@app.route('/gestion_excel', methods=['GET', 'POST'])
@require_access(14)
def gestion_excel():
    site = request.args.get('site') or list(sites.keys())[0]
    message = None
    df = charger_donnees(site)
    if request.method == 'POST':
        # Récupérer les données du formulaire et mettre à jour le DataFrame
        for i in range(len(df)):
            for col in df.columns:
                form_key = f"cell_{i}_{col}"
                if form_key in request.form:
                    value = request.form[form_key]
                    # Gestion des types : laisser vide si vide, sinon essayer de caster
                    if value == '':
                        df.at[i, col] = ''
                    else:
                        df.at[i, col] = value
        sauvegarder_donnees(df, site)
        message = "Modifications enregistrées !"
    # Rafraîchir les données après sauvegarde
    df = charger_donnees(site)
    return render_template('gestion_excel.html', sites=list(sites.keys()), site=site, df=df, message=message)

if __name__ == "__main__":
    # Nettoyer le cache expiré au démarrage
    nettoyer_cache_expire()
    
    # Configuration pour la production
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600  # Cache statique 1 heure
    
    app.run(debug=True, host='0.0.0.0', port=5000)
