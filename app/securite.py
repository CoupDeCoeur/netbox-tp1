import os
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

API_TOKEN_ADMIN = os.environ["API_TOKEN_ADMIN"]
API_TOKEN_READER = os.environ["API_TOKEN_READER"]

bearer = HTTPBearer(auto_error=False)


def role_de(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        recu = credentials.credentials.encode()
        if secrets.compare_digest(recu, API_TOKEN_ADMIN.encode()):
            return "admin"
        if secrets.compare_digest(recu, API_TOKEN_READER.encode()):
            return "lecteur"
    raise HTTPException(
        status_code=401,
        detail="Token absent ou inconnu",
        headers={"WWW-Authenticate": "Bearer"},
    )


def exiger_lecture(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    return role_de(credentials)


def exiger_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    role = role_de(credentials)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Action réservée au rôle admin")
    return role