import os
import requests

DOCKER_API_URL = os.environ.get("DOCKER_API_URL", "http://127.0.0.1:2375")

def lister_conteneurs_et_stats():
    with requests.Session() as session:
        try:
            # Récupération de tous les conteneurs
            response = session.get(f"{DOCKER_API_URL}/containers/json?all=1", timeout=5)
            response.raise_for_status()
            
            for c in response.json():
                nom = c['Names'][0].lstrip('/')
                image = c['Image']
                etat = c['State']
                container_id = c['Id']
                
                print(f"\nNom : {nom} | Image : {image} | État : {etat}")
                
                #Si le conteneur est démarré, on récupère ses stats
                if etat == "running":
                    stats_url = f"{DOCKER_API_URL}/containers/{container_id}/stats?stream=false"
                    try:
                        stats_resp = session.get(stats_url, timeout=5)
                        stats_resp.raise_for_status()
                        stats = stats_resp.json()
                        
                        # Calculs du CPU et de la mémoire
                        cpu = stats.get("cpu_stats", {})
                        precpu = stats.get("precpu_stats", {})
                        delta_cpu = cpu.get("cpu_usage", {}).get("total_usage", 0) - precpu.get("cpu_usage", {}).get("total_usage", 0)
                        delta_systeme = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
                        online_cpus = cpu.get("online_cpus", 1)
                        
                        pourcent_cpu = (delta_cpu / delta_systeme) * online_cpus * 100 if delta_systeme > 0 else 0.0
                        memoire_mo = stats.get("memory_stats", {}).get("usage", 0) / 1024 / 1024
                        
                        print(f"   -> CPU : {pourcent_cpu:.2f}% | Mémoire : {memoire_mo:.2f} Mo")
                        
                    except requests.exceptions.RequestException as e:
                        print(f"   -> Erreur lors de la récupération des stats : {e}")
                        
        except requests.exceptions.RequestException as e:
            print(f"Erreur de connexion à l'API Docker : {e}")

if __name__ == "__main__":
    lister_conteneurs_et_stats()