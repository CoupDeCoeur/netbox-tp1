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
                labels = c.get("Labels") or c.get("Config", {}).get("Labels", {})
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
            raise HTTPException(status_code=500, detail=f"Erreur Docker: {e}")

@app.get("/containers/{container_id}")
def obtenir_container_par_id(container_id: str):
    """Récupère un conteneur par son ID. Renvoie 404 si inconnu ou sans label."""
    with requests.Session() as session:
        try:
            # Appel de l'endpoint d'inspection d'un conteneur unique de l'API Docker
            response = session.get(f"{DOCKER_API_URL}/containers/{container_id}/json", timeout=5)
            
            # Si le conteneur n'existe pas, Docker renvoie 404
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Conteneur inconnu")
            
            response.raise_for_status()
            c = response.json()
            
            # Vérification des labels (attention, c'um dict ou None)
            labels = c.get("Config", {}).get("Labels") or {}
            
            # Si pas de labels, on renvoie aussi 404 selon les règles du TP
            if not labels:
                raise HTTPException(status_code=404, detail="Conteneur sans étiquette")
                
            return {
                "id": c.get("Id"),
                "name": c.get("Name", "").lstrip('/'),
                "image": c.get("Config", {}).get("Image"),
                "state": c.get("State", {}).get("Status"),
                "labels": labels
            }
            
        except requests.exceptions.RequestException:
            raise HTTPException(status_code=404, detail="Conteneur inconnu ou injoignable")