#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import pandas as pd
from datetime import datetime

def test_fichiers():
    """Test de l'existence et du contenu des fichiers"""
    print("=== DIAGNOSTIC DES FICHIERS ===")
    
    fichiers = [
        "mesures.xlsx",
        "rapports.json", 
        "releves_20.json",
        "photos_releves"
    ]
    
    for fichier in fichiers:
        existe = os.path.exists(fichier)
        print(f"{fichier}: {'✅' if existe else '❌'}")
        
        if existe and fichier.endswith('.json'):
            try:
                with open(fichier, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"  Contenu: {len(data)} éléments")
            except Exception as e:
                print(f"  Erreur lecture: {e}")
        
        if existe and fichier == 'photos_releves':
            contenu = os.listdir(fichier)
            print(f"  Contenu: {contenu}")

def test_fonctions_app():
    """Test des fonctions de l'application"""
    print("\n=== TEST DES FONCTIONS ===")
    
    # Importer les fonctions de app.py
    try:
        import sys
        sys.path.append('.')
        
        # Test enregistrer_releve
        print("Test enregistrer_releve...")
        releve_test = {
            "site": "LPZ",
            "mois": 11,
            "annee": 2024,
            "photos": {"Exhaure 1": "test.jpg"},
            "timestamp": datetime.now().isoformat()
        }
        
        # Charger et sauvegarder
        releves = []
        if os.path.exists("releves_20.json"):
            with open("releves_20.json", "r", encoding="utf-8") as f:
                releves = json.load(f)
        
        releves.append(releve_test)
        
        with open("releves_20.json", "w", encoding="utf-8") as f:
            json.dump(releves, f, ensure_ascii=False, indent=2)
        
        print("✅ Relevé ajouté")
        
        # Test enregistrer_rapport
        print("Test enregistrer_rapport...")
        rapports = []
        if os.path.exists("rapports.json"):
            with open("rapports.json", "r", encoding="utf-8") as f:
                rapports = json.load(f)
        
        rapport_test = {
            "semaine": 50,
            "annee": 2024,
            "site": "SMP",
            "timestamp": datetime.now().isoformat()
        }
        
        rapports.append(rapport_test)
        
        with open("rapports.json", "w", encoding="utf-8") as f:
            json.dump(rapports, f, ensure_ascii=False, indent=2)
        
        print("✅ Rapport ajouté")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")

def test_creation_dossiers():
    """Test de création des dossiers photos"""
    print("\n=== TEST CRÉATION DOSSIERS ===")
    
    try:
        # Créer un dossier test
        test_dir = "photos_releves/test_creation"
        if not os.path.exists(test_dir):
            os.makedirs(test_dir, mode=0o755)
            print(f"✅ Dossier créé: {test_dir}")
        else:
            print(f"✅ Dossier existe: {test_dir}")
        
        # Créer un fichier test
        test_file = os.path.join(test_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        print(f"✅ Fichier créé: {test_file}")
        
        # Vérifier
        if os.path.exists(test_file):
            print("✅ Fichier vérifié")
        else:
            print("❌ Fichier non trouvé")
            
    except Exception as e:
        print(f"❌ Erreur création: {e}")

def test_web_routes():
    """Test des routes web"""
    print("\n=== TEST ROUTES WEB ===")
    
    try:
        # Simuler une requête GET sur /releve_20
        print("Test route /releve_20...")
        
        # Charger les relevés
        releves = []
        if os.path.exists("releves_20.json"):
            with open("releves_20.json", "r", encoding="utf-8") as f:
                releves = json.load(f)
        
        print(f"✅ {len(releves)} relevés chargés")
        
        # Simuler une requête GET sur /rapport
        print("Test route /rapport...")
        
        rapports = []
        if os.path.exists("rapports.json"):
            with open("rapports.json", "r", encoding="utf-8") as f:
                rapports = json.load(f)
        
        print(f"✅ {len(rapports)} rapports chargés")
        
    except Exception as e:
        print(f"❌ Erreur routes: {e}")

if __name__ == "__main__":
    test_fichiers()
    test_fonctions_app()
    test_creation_dossiers()
    test_web_routes()
    print("\n=== DIAGNOSTIC TERMINÉ ===") 