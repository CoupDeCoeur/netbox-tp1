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


def _formater_detail_conteneur(data: dict) -> dict:
    config = data.get("Config") or {}
    labels = config.get("Labels") or {}
    state_obj = data.get("State") or {}
    return {
        "id": data.get("Id"),
        "name": (data.get("Name") or "").lstrip("/"),
        "image": config.get("Image"),
        "state": state_obj.get("Status"),
        "labels": labels,
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/containers")
def lister_containers_etiquetes():
    with requests.Session() as session:
        try:
            response = session.get(f"{DOCKER_API_URL}/containers/json?all=1", timeout=10)
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
            response = session.get(f"{DOCKER_API_URL}/containers/{container_id}/json", timeout=10)
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Conteneur inconnu")
            response.raise_for_status()
            c = response.json()

            labels = c.get("Config") or {}
            labels = labels.get("Labels") or {}
            if labels.get("adminapi.managed") != "true":
                raise HTTPException(status_code=404, detail="Conteneur sans l'étiquette requise")

            return _formater_detail_conteneur(c)
        except HTTPException:
            raise
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=502, detail=f"Erreur API Docker: {e}")


@app.post("/containers", status_code=201)
def creer_container(demande: ConteneurACreer):
    corps = {
        "Image": demande.image,
        "Labels": {"adminapi.managed": "true"},
    }
    try:
        with requests.Session() as session:
            creation = session.post(
                f"{DOCKER_API_URL}/containers/create",
                params={"name": demande.name},
                json=corps,
                timeout=15,
            )
            if creation.status_code == 409:
                raise HTTPException(status_code=409, detail="Un conteneur avec ce nom existe déjà")
            if creation.status_code == 404:
                raise HTTPException(status_code=404, detail="Image introuvable sur l'hôte Docker")
            creation.raise_for_status()

            container_id = creation.json()["Id"]

            demarrage = session.post(
                f"{DOCKER_API_URL}/containers/{container_id}/start",
                timeout=15,
            )
            if demarrage.status_code == 404:
                raise HTTPException(status_code=404, detail="Conteneur introuvable au démarrage")
            if demarrage.status_code not in (204, 304):
                demarrage.raise_for_status()

            inspection = session.get(
                f"{DOCKER_API_URL}/containers/{container_id}/json",
                timeout=10,
            )
            inspection.raise_for_status()
            return _formater_detail_conteneur(inspection.json())
    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Erreur API Docker: {e}")