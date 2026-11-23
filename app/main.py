import os
from typing import Literal
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
import requests

from app import netbox_client
from app.securite import exiger_admin, exiger_lecture

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


def _verifier_et_recuperer_gere(session: requests.Session, container_id: str) -> dict:
    response = session.get(f"{DOCKER_API_URL}/containers/{container_id}/json", timeout=10)
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Conteneur inconnu")
    response.raise_for_status()
    data = response.json()
    labels = (data.get("Config") or {}).get("Labels") or {}
    if labels.get("adminapi.managed") != "true":
        raise HTTPException(status_code=404, detail="Conteneur non géré")
    return data


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/containers")
def lister_containers_etiquetes(_: str = Depends(exiger_lecture)):
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
        except HTTPException:
            raise
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=502, detail=f"Erreur API Docker: {e}")


@app.get("/containers/{container_id}")
def obtenir_container_par_id(container_id: str, _: str = Depends(exiger_lecture)):
    with requests.Session() as session:
        try:
            data = _verifier_et_recuperer_gere(session, container_id)
            return _formater_detail_conteneur(data)
        except HTTPException:
            raise
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=502, detail=f"Erreur API Docker: {e}")


@app.post("/containers", status_code=201)
def creer_container(demande: ConteneurACreer, _: str = Depends(exiger_admin)):
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

            data = _verifier_et_recuperer_gere(session, container_id)
            detail = _formater_detail_conteneur(data)
            netbox_client.creer_vm_active(detail["name"])
            return detail
    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Erreur API Docker: {e}")


@app.post("/containers/{container_id}/stop")
def arreter_container(container_id: str, _: str = Depends(exiger_admin)):
    try:
        with requests.Session() as session:
            _verifier_et_recuperer_gere(session, container_id)

            stop_resp = session.post(
                f"{DOCKER_API_URL}/containers/{container_id}/stop",
                params={"t": 2},
                timeout=30,
            )
            if stop_resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Conteneur inconnu")
            if stop_resp.status_code == 304:
                raise HTTPException(status_code=409, detail="Le conteneur est déjà arrêté")
            stop_resp.raise_for_status()

            data = _verifier_et_recuperer_gere(session, container_id)
            detail = _formater_detail_conteneur(data)
            netbox_client.definir_statut_vm(detail["name"], "offline")
            return detail
    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Erreur API Docker: {e}")


@app.post("/containers/{container_id}/start")
def demarrer_container(container_id: str, _: str = Depends(exiger_admin)):
    try:
        with requests.Session() as session:
            _verifier_et_recuperer_gere(session, container_id)

            start_resp = session.post(
                f"{DOCKER_API_URL}/containers/{container_id}/start",
                timeout=15,
            )
            if start_resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Conteneur inconnu")
            if start_resp.status_code == 304:
                raise HTTPException(status_code=409, detail="Le conteneur est déjà démarré")
            start_resp.raise_for_status()

            data = _verifier_et_recuperer_gere(session, container_id)
            detail = _formater_detail_conteneur(data)
            netbox_client.definir_statut_vm(detail["name"], "active")
            return detail
    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Erreur API Docker: {e}")


@app.delete("/containers/{container_id}", status_code=204)
def supprimer_container(container_id: str, _: str = Depends(exiger_admin)):
    try:
        with requests.Session() as session:
            data = _verifier_et_recuperer_gere(session, container_id)
            detail = _formater_detail_conteneur(data)

            del_resp = session.delete(
                f"{DOCKER_API_URL}/containers/{container_id}",
                params={"force": "true"},
                timeout=30,
            )
            if del_resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Conteneur inconnu")
            del_resp.raise_for_status()

            netbox_client.supprimer_vm(detail["name"])
            return Response(status_code=204)
    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Erreur API Docker: {e}")