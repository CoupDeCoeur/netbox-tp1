import os
from fastapi import FastAPI, HTTPException
import requests
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="API d'inventaire Docker/NetBox", version="1.0")

DOCKER_API_URL = os.environ.get("DOCKER_API_URL", "http://127.0.0.1:2375")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/containers")
def lister_containers_etiquetes():
    """Récupère uniquement les conteneurs possédant des étiquettes (labels)."""
    with requests.Session() as session:
        try:
            response = session.get(f"{DOCKER_API_URL}/containers/json?all=1", timeout=5)
            response.raise_for_status()
            
            containers_filtres = []
            for c in response.json():
                # On vérifie la présence de labels
                labels = c.get("Labels") or c.get("Config", {}).get("Labels", {})
                
                # Si le conteneur a des étiquettes, on l'ajoute
                if labels:
                    nom = c.get('Names', ['Inconnu'])[0].lstrip('/')
                    containers_filtres.append({
                        "id": c.get("Id"),
                        "name": nom,
                        "image": c.get("Image"),
                        "state": c.get("State"),
                        "labels": labels
                    })
                    
            return containers_filtres
            
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Erreur de communication avec l'API Docker: {e}")