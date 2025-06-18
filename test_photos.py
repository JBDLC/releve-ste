#!/usr/bin/env python3
"""
Script de test pour vérifier la logique de création des sous-dossiers de photos
"""

import os
from datetime import datetime

# Configuration
PHOTOS_DIR = "photos_releves"

def test_creation_sous_dossiers():
    """Test de la logique de création des sous-dossiers"""
    
    # Test avec différents sites
    sites_tests = [
        ("SMP", 12, 2024),
        ("LPZ", 1, 2025),
        ("Site avec espaces", 6, 2024)
    ]
    
    print("=== Test de création des sous-dossiers ===")
    
    for site, mois, annee in sites_tests:
        # Créer le nom du sous-dossier au format site_mois_année
        subfolder_name = f"{site.replace(' ', '_')}_{mois}_{annee}"
        subfolder_path = os.path.join(PHOTOS_DIR, subfolder_name)
        
        print(f"\nSite: {site}")
        print(f"Mois: {mois}, Année: {annee}")
        print(f"Nom du sous-dossier: {subfolder_name}")
        print(f"Chemin complet: {subfolder_path}")
        
        # Créer le sous-dossier s'il n'existe pas
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)
            print(f"✅ Dossier créé: {subfolder_path}")
        else:
            print(f"ℹ️  Dossier existe déjà: {subfolder_path}")
        
        # Simuler la création d'un fichier photo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debitmetre = "Débitmètre principal"
        filename = f"{debitmetre.replace(' ', '_')}_{timestamp}.jpg"
        filepath = os.path.join(subfolder_path, filename)
        
        # Créer un fichier de test vide
        with open(filepath, 'w') as f:
            f.write("Fichier de test")
        
        print(f"📸 Fichier de test créé: {filename}")
        print(f"📁 Chemin relatif stocké: {os.path.join(subfolder_name, filename)}")

def afficher_structure():
    """Affiche la structure finale des dossiers"""
    print("\n=== Structure finale des dossiers ===")
    
    def parcourir_dossier(dossier, niveau=0):
        indent = "  " * niveau
        if os.path.isdir(dossier):
            print(f"{indent}📁 {os.path.basename(dossier)}/")
            try:
                for item in sorted(os.listdir(dossier)):
                    item_path = os.path.join(dossier, item)
                    if os.path.isdir(item_path):
                        parcourir_dossier(item_path, niveau + 1)
                    else:
                        print(f"{indent}  📄 {item}")
            except PermissionError:
                print(f"{indent}  ❌ Erreur d'accès")
        else:
            print(f"{indent}📄 {os.path.basename(dossier)}")
    
    parcourir_dossier(PHOTOS_DIR)

if __name__ == "__main__":
    # Créer le dossier principal s'il n'existe pas
    if not os.path.exists(PHOTOS_DIR):
        os.makedirs(PHOTOS_DIR)
        print(f"Dossier principal créé: {PHOTOS_DIR}")
    
    test_creation_sous_dossiers()
    afficher_structure()
    
    print("\n✅ Test terminé !") 