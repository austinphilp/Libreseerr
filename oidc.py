"""OIDC (OpenID Connect) authentication helpers.

Mirrors the shape of the LDAP integration in app.py: a small set of
module-level functions that the main app calls. The OAuth client is held
on the Flask app's `extensions` dict to avoid a module-level singleton
that would survive across reconfigures.
"""

import logging

import requests
from authlib.integrations.flask_client import OAuth

logger = logging.getLogger(__name__)


# Authlib uses this name to look up the registered client.
PROVIDER_NAME = "oidc"


def get_oidc_defaults():
    return {
        "enabled": False,
        "display_name": "OIDC",
        "issuer_url": "",
        "client_id": "",
        "client_secret": "",
        "scope": "openid profile email",
        "username_claim": "preferred_username",
        "default_role": "user",
        "auto_create_users": False,
        "auto_redirect": False,
    }


def init_oidc(app, config):
    """Configure the OAuth client from config['oidc'].

    Called at startup AND any time config['oidc'] changes (POST /api/oidc).
    Stores the OAuth client on app.extensions['oidc_client'] when enabled,
    or removes it when disabled.
    """
    oidc_cfg = config.get("oidc") or {}
    if not oidc_cfg.get("enabled"):
        app.extensions.pop("oidc_client", None)
        return False

    issuer = (oidc_cfg.get("issuer_url") or "").rstrip("/")
    client_id = oidc_cfg.get("client_id") or ""
    client_secret = oidc_cfg.get("client_secret") or ""
    scope = oidc_cfg.get("scope") or "openid profile email"

    if not issuer or not client_id or not client_secret:
        logger.warning("OIDC enabled but missing issuer_url/client_id/client_secret")
        app.extensions.pop("oidc_client", None)
        return False

    oauth = OAuth(app)
    oauth.register(
        name=PROVIDER_NAME,
        client_id=client_id,
        client_secret=client_secret,
        # Authlib auto-fetches authorization_endpoint, token_endpoint,
        # jwks_uri, userinfo_endpoint, etc. from the discovery document.
        server_metadata_url=f"{issuer}/.well-known/openid-configuration",
        client_kwargs={"scope": scope},
    )
    app.extensions["oidc_client"] = oauth.create_client(PROVIDER_NAME)
    return True


def get_client(app):
    return app.extensions.get("oidc_client")


def fetch_discovery(issuer_url):
    """Fetch the OIDC discovery document. Used by /api/oidc/test.

    Returns the parsed JSON. Raises on HTTP or parse error.
    """
    url = f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def validate_discovery(doc):
    """Basic structural validation of the discovery doc.

    Returns (ok, message). The required claims are per RFC 8414 / OIDC Discovery 1.0.
    """
    required = ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")
    missing = [k for k in required if not doc.get(k)]
    if missing:
        return False, f"Discovery doc missing required fields: {', '.join(missing)}"
    return True, "Discovery document looks valid"


def extract_username(userinfo, claim_name):
    """Pull the chosen claim from userinfo, with sensible fallbacks.

    Order: configured claim, then preferred_username, then sub. Returns
    None only if all three are missing — in which case the IdP is broken
    and there's nothing we can do.
    """
    for k in (claim_name, "preferred_username", "sub"):
        v = userinfo.get(k) if k else None
        if v:
            return str(v).strip()
    return None
