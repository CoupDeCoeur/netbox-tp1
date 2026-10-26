import os
from fastapi import FastAPI
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

app = FastAPI(title="API d'inventaire Docker/NetBox", version="1.0")

@app.get("/health")
def health_check():
    """Route de santé pour vérifier que l'API est en ligne."""
    return {"status": "ok"}