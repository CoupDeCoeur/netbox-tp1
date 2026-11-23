import os
from fastapi import HTTPException
import requests

NETBOX_URL = os.environ.get("NETBOX_URL", "http://netbox:8080").rstrip("/")
NETBOX_TOKEN = os.environ["NETBOX_TOKEN"]
CLUSTER_NAME = "docker-local"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Token {NETBOX_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    return s


def obtenir_id_cluster(session: requests.Session, nom_cluster: str = CLUSTER_NAME) -> int:
    # Les URL NetBox finissent obligatoirement par /
    r = session.get(
        f"{NETBOX_URL}/api/virtualization/clusters/",
        params={"name": nom_cluster},
        timeout=10,
    )
    r.raise_for_status()
    resultats = r.json().get("results") or []
    if not resultats:
        raise RuntimeError(f"Cluster NetBox '{nom_cluster}' introuvable")
    return resultats[0]["id"]


def rechercher_vm(session: requests.Session, nom: str, cluster_id: int) -> dict | None:
    r = session.get(
        f"{NETBOX_URL}/api/virtualization/virtual-machines/",
        params={"name": nom, "cluster_id": cluster_id},
        timeout=10,
    )
    r.raise_for_status()
    resultats = r.json().get("results") or []
    return resultats[0] if resultats else None


def creer_vm_active(nom: str) -> None:
    try:
        with _session() as s:
            cluster_id = obtenir_id_cluster(s)
            existante = rechercher_vm(s, nom, cluster_id)
            if existante:
                r = s.patch(
                    f"{NETBOX_URL}/api/virtualization/virtual-machines/{existante['id']}/",
                    json={"status": "active"},
                    timeout=10,
                )
                r.raise_for_status()
                return
            r = s.post(
                f"{NETBOX_URL}/api/virtualization/virtual-machines/",
                json={"name": nom, "cluster": cluster_id, "status": "active"},
                timeout=10,
            )
            r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur NetBox lors de la création : {e}")


def definir_statut_vm(nom: str, statut: str) -> None:
    try:
        with _session() as s:
            cluster_id = obtenir_id_cluster(s)
            vm = rechercher_vm(s, nom, cluster_id)
            if vm:
                r = s.patch(
                    f"{NETBOX_URL}/api/virtualization/virtual-machines/{vm['id']}/",
                    json={"status": statut},
                    timeout=10,
                )
                r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur NetBox lors de la mise à jour : {e}")


def supprimer_vm(nom: str) -> None:
    try:
        with _session() as s:
            cluster_id = obtenir_id_cluster(s)
            vm = rechercher_vm(s, nom, cluster_id)
            if vm:
                r = s.delete(
                    f"{NETBOX_URL}/api/virtualization/virtual-machines/{vm['id']}/",
                    timeout=10,
                )
                if r.status_code not in (204, 404):
                    r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur NetBox lors de la suppression : {e}")