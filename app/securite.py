import hmac
import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def _charger_secrets() -> tuple[str, str, str]:
    admin_token = os.environ.get("API_TOKEN_ADMIN", "").strip()
    reader_token = os.environ.get("API_TOKEN_READER", "").strip()
    webhook_secret = os.environ.get("WEBHOOK_SECRET", "").strip()
    return admin_token, reader_token, webhook_secret


def _verifier_jeton_bearer(
    credentials: HTTPAuthorizationCredentials | None,
    roles_autorises: set[str],
) -> str:
    admin_token, reader_token, _ = _charger_secrets()

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification Bearer requise",
        )

    jeton = credentials.credentials.strip()
    if not jeton:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton manquant",
        )

    if admin_token and hmac.compare_digest(jeton, admin_token):
        role = "admin"
    elif reader_token and hmac.compare_digest(jeton, reader_token):
        role = "lecteur"
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton invalide",
        )

    if role not in roles_autorises:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits insuffisants",
        )

    return role


def exiger_lecture(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str:
    return _verifier_jeton_bearer(credentials, {"admin", "lecteur"})


def exiger_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str:
    return _verifier_jeton_bearer(credentials, {"admin"})


def exiger_secret_webhook(
    x_webhook_secret: Annotated[str | None, Header(alias="X-Webhook-Secret")] = None,
) -> None:
    _, _, webhook_secret = _charger_secrets()

    if not webhook_secret or not x_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Webhook-Secret manquant",
        )

    if not hmac.compare_digest(x_webhook_secret, webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Webhook-Secret invalide",
        )