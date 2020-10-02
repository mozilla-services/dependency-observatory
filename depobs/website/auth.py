import logging
from typing import Optional

from flask import current_app
from flask_httpauth import HTTPTokenAuth


log = logging.getLogger(__name__)

auth = HTTPTokenAuth(scheme="Bearer")


@auth.verify_token
def verify_token(token: str) -> Optional[str]:
    """
    Returns the user object
    """
    if token in current_app.config["API_TOKENS"]:
        user = current_app.config["API_TOKENS"][token]
        log.info(f"verified token for user {user}")
        return user
    return None
