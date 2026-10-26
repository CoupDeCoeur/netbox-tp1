import os
import json
from datetime import datetime
import requests

DOCKER_API_URL = os.environ.get("DOCKER_API_URL", "http://127.0.0.1:2375")

def generer_inventaire():
    # Structure de données pour le fichier JSON avec la date du relevé
    inventaire = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "containers": []
    }
    
    with requests.Session() as session:
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
                
                # Si le conteneur tourne, on récupère ses statistiques CPU et RAM
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
            
            # Écriture du dictionnaire dans le fichier inventaire.json
            with open("inventaire.json", "w", encoding="utf-8") as f:
                json.dump(inventaire, f, indent=4, ensure_ascii=False)
            
            # Affichage d'un résumé lisible dans la console
            print(f"=== INVENTAIRE DOCKER ({inventaire['date']}) ===")
            for item in inventaire["containers"]:
                print(f"• Nom : {item['nom']} | État : {item['etat']} | CPU : {item['cpu_pourcent']}% | RAM : {item['memoire_mo']} Mo")
            print("\nFichier 'inventaire.json' généré avec succès !")
            
        except requests.exceptions.RequestException as e:
            print(f"Erreur de connexion à l'API Docker : {e}")

if __name__ == "__main__":
    generer_inventaire()