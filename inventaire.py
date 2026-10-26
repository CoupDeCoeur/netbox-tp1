import os
import requests

# Chargement de l'URL Docker depuis l'environnement (avec valeur par défaut)
DOCKER_API_URL = os.environ.get("DOCKER_API_URL", "http://127.0.0.1:2375")

def lister_conteneurs():
    #Utilisation d'une Session pour optimiser les connexions réseau
    session = requests.Session()
    
    #Endpoint pour lister tous les conteneurs (all=1 pour inclure les arrêtés)
    url = f"{DOCKER_API_URL}/containers/json?all=1"
    
    try:
        #Requête GET avec un timeout de 5 secondes (sécurité anti-blocage)
        response = session.get(url, timeout=5)
        response.raise_for_status() # Lève une exception si le statut HTTP n'est pas 200
        
        conteneurs = response.json()
        
        #Affichage des informations demandées pour chaque conteneur
        for c in conteneurs:
            nom = c.get('Names', ['Inconnu'])[0].lstrip('/')
            image = c.get('Image', 'Inconnue')
            etat = c.get('State', 'Inconnu')
            
            print(f"Nom: {nom}, Image: {image}, État: {etat}")
            
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la connexion à l'API Docker : {e}")

if __name__ == "__main__":
    lister_conteneurs()