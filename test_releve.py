#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime

# Constantes
RELEVES_JSON = "releves_20.json"
PHOTOS_DIR = "photos_releves"

def test_enregistrer_releve():
    """Test de la fonction enregistrer_releve"""
    print("=== TEST ENREGISTRER_RELEVE ===")
    
    # Test 1: Créer un relevé
    releve_test = {
        "site": "SMP",
        "mois": 12,
        "annee": 2024,
        "photos": {
            "Exhaure 1": "SMP_12_2024/Exhaure_1_20241201_120000.jpg",
            "Exhaure 2": "SMP_12_2024/Exhaure_2_20241201_120100.jpg"
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # Charger les relevés existants
    releves = []
    if os.path.exists(RELEVES_JSON):
        with open(RELEVES_JSON, "r", encoding="utf-8") as f:
            try:
                releves = json.load(f)
                print(f"Relevés existants chargés: {len(releves)}")
            except Exception as e:
                print(f"Erreur lecture JSON: {e}")
                releves = []
    
    # Ajouter le test
    releves.append(releve_test)
    
    # Sauvegarder
    try:
        with open(RELEVES_JSON, "w", encoding="utf-8") as f:
            json.dump(releves, f, ensure_ascii=False, indent=2)
        print("✅ Relevé test sauvegardé avec succès")
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")
    
    # Vérifier
    if os.path.exists(RELEVES_JSON):
        with open(RELEVES_JSON, "r", encoding="utf-8") as f:
            releves_verif = json.load(f)
            print(f"✅ Vérification: {len(releves_verif)} relevés dans le fichier")
            print(f"   Dernier relevé: {releves_verif[-1] if releves_verif else 'Aucun'}")

def test_creation_dossier():
    """Test de création de dossier photos"""
    print("\n=== TEST CRÉATION DOSSIER ===")
    
    # Créer le dossier principal
    if not os.path.exists(PHOTOS_DIR):
        os.makedirs(PHOTOS_DIR, mode=0o755)
        print(f"✅ Dossier principal créé: {PHOTOS_DIR}")
    else:
        print(f"✅ Dossier principal existe: {PHOTOS_DIR}")
    
    # Créer un sous-dossier test
    subfolder_name = "SMP_12_2024"
    subfolder_path = os.path.join(PHOTOS_DIR, subfolder_name)
    
    if not os.path.exists(subfolder_path):
        os.makedirs(subfolder_path, mode=0o755)
        print(f"✅ Sous-dossier créé: {subfolder_path}")
    else:
        print(f"✅ Sous-dossier existe: {subfolder_path}")
    
    # Vérifier le contenu
    contenu = os.listdir(PHOTOS_DIR)
    print(f"✅ Contenu du dossier principal: {contenu}")

if __name__ == "__main__":
    test_enregistrer_releve()
    test_creation_dossier()
    print("\n=== FIN DES TESTS ===") 