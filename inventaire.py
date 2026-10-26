import os
import json
from datetime import datetime
import requests

# Récupération des configurations depuis l'environnement
DOCKER_API_URL = os.environ.get("DOCKER_API_URL", "http://127.0.0.1:2375")
NETBOX_URL = os.environ.get("NETBOX_URL", "http://127.0.0.1:8080")
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN", "")

def generer_inventaire():
    inventaire = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "containers": [],
        "netbox": {
            "version": None,
            "object_types_count": 0
        }
    }
    
    # Headers d'authentification pour NetBox
    headers = {
        "Authorization": f"Token {NETBOX_TOKEN}",
        "Accept": "application/json"
    }
    
    with requests.Session() as session:
        # --- PARTIE DOCKER ---
        try:
            response = session.get(f"{DOCKER_API_URL}/containers/json?all=1", timeout=5)
            response.raise_for_status()
            
            for c in response.json():
                nom = c['Names'][0].lstrip('/')
                image = c['Image']
                etat = c['State']
                container_id = c['Id']
                
                container_info = {
                    "nom": nom,
                    "image": image,
                    "etat": etat,
                    "cpu_pourcent": 0.0,
                    "memoire_mo": 0.0
                }
                
                if etat == "running":
                    stats_url = f"{DOCKER_API_URL}/containers/{container_id}/stats?stream=false"
                    try:
                        stats_resp = session.get(stats_url, timeout=5)
                        stats_resp.raise_for_status()
                        stats = stats_resp.json()
                        
                        cpu = stats.get("cpu_stats", {})
                        precpu = stats.get("precpu_stats", {})
                        delta_cpu = cpu.get("cpu_usage", {}).get("total_usage", 0) - precpu.get("cpu_usage", {}).get("total_usage", 0)
                        delta_systeme = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
                        online_cpus = cpu.get("online_cpus", 1)
                        
                        pourcent_cpu = (delta_cpu / delta_systeme) * online_cpus * 100 if delta_systeme > 0 else 0.0
                        memoire_mo = stats.get("memory_stats", {}).get("usage", 0) / 1024 / 1024
                        
                        container_info["cpu_pourcent"] = round(pourcent_cpu, 2)
                        container_info["memoire_mo"] = round(memoire_mo, 2)
                    except requests.exceptions.RequestException:
                        pass
                
                inventaire["containers"].append(container_info)
        except requests.exceptions.RequestException as e:
            print(f"Erreur de connexion à l'API Docker : {e}")

        # ---PARTIE NETBOX (VERSION ET PAGINATION) ---
        try:
            status_resp = session.get(f"{NETBOX_URL}/api/status/", headers=headers, timeout=5)
            status_resp.raise_for_status()
            # Récupération de la version NetBox
            inventaire["netbox"]["version"] = status_resp.json().get("netbox-version") or status_resp.json().get("django-version")
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération du statut NetBox : {e}")

        try:
            # Pagination sur les object-types de NetBox jusqu'à ce que 'next' soit None
            nb_url = f"{NETBOX_URL}/api/core/object-types/?limit=50"
            total_types = 0
            
            while nb_url:
                nb_resp = session.get(nb_url, headers=headers, timeout=5)
                nb_resp.raise_for_status()
                data = nb_resp.json()
                
                total_types += len(data.get("results", []))
                nb_url = data.get("next")  # Passe à la page suivante (ou None si fin)
                
            inventaire["netbox"]["object_types_count"] = total_types
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la pagination NetBox : {e}")

        # --- ÉCRITURE DANS LE JSON ET AFFICHAGE ---
        with open("inventaire.json", "w", encoding="utf-8") as f:
            json.dump(inventaire, f, indent=4, ensure_ascii=False)
        
        print(f"=== INVENTAIRE GLOBAL ({inventaire['date']}) ===")
        print(f"NetBox Version : {inventaire['netbox']['version']} | Types d'objets : {inventaire['netbox']['object_types_count']}")
        print(f"Nombre de conteneurs : {len(inventaire['containers'])}")
        print("\nFichier 'inventaire.json' généré et mis à jour avec succès !")

if __name__ == "__main__":
    generer_inventaire()