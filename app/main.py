import os
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import requests

load_dotenv()

app = FastAPI(title="API d'inventaire Docker/NetBox", version="1.0")

DOCKER_API_URL = os.environ.get("DOCKER_API_URL", "http://127.0.0.1:2375")

ImageAutorisee = Literal["nginx:alpine", "redis:alpine", "httpd:alpine"]


class ConteneurACreer(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,30}$", examples=["web2"])
    image: ImageAutorisee


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/containers")
def lister_containers_etiquetes():
    with requests.Session() as session:
        try:
            response = session.get(f"{DOCKER_API_URL}/containers/json?all=1", timeout=5)
            response.raise_for_status()

            containers_filtres = []
            for c in response.json():
                labels = c.get("Labels") or c.get("Config", {}).get("Labels", {}) or {}
                if labels.get("adminapi.managed") == "true":
                    nom = c.get("Names", ["Inconnu"])[0].lstrip("/")
                    containers_filtres.append({
                        "id": c.get("Id"),
                        "name": nom,
                        "image": c.get("Image"),
                        "state": c.get("State"),
                        "labels": labels,
                    })
            return containers_filtres
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=502, detail=f"Erreur API Docker: {e}")


@app.get("/containers/{container_id}")
def obtenir_container_par_id(container_id: str):
    with requests.Session() as session:
        try:
            response = session.get(f"{DOCKER_API_URL}/containers/{container_id}/json", timeout=5)
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Conteneur inconnu")
            response.raise_for_status()
            c = response.json()

            labels = c.get("Config", {}).get("Labels") or {}
            if labels.get("adminapi.managed") != "true":
                raise HTTPException(status_code=404, detail="Conteneur sans l'étiquette requise")

            return {
                "id": c.get("Id"),
                "name": c.get("Name", "").lstrip("/"),
                "image": c.get("Config", {}).get("Image"),
                "state": c.get("State", {}).get("Status"),
                "labels": labels,
            }
        except HTTPException:
            raise
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=502, detail=f"Erreur API Docker: {e}")