import base64
import hashlib
import logging
import secrets
from urllib.parse import urlencode

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class OAuthClient:
    """Handles dynamic client registration + PKCE + token lifecycle for an MCP server."""

    def __init__(self, server: str, metadata: dict):
        self.server = server
        self.metadata = metadata
        self.client_id = None
        self.client_secret = None

    # ---- RFC 7591 dynamic registration (once, at boot) ----
    async def register(self) -> dict:
        logger.debug("OAUTH: Registering OAuth client for '%s'", self.server)
        payload = {
            "client_name": f"myagent-{self.server}",
            "redirect_uris": [settings.oauth_redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(self.metadata["registration_endpoint"], json=payload)
        r.raise_for_status()
        reg = r.json()
        self.client_id = reg["client_id"]
        self.client_secret = reg.get("client_secret", "")
        logger.debug(
            "OAUTH: Registration successful for '%s', client_id=%s",
            self.server,
            self.client_id,
        )
        return reg

    # ---- Build authorization URL with PKCE ----
    def build_auth_url(self, state: str) -> tuple[str, str]:
        """Returns (auth_url, code_verifier). Store verifier per state."""
        logger.debug(
            "OAUTH: Building auth URL for server '%s', state=%s", self.server, state
        )
        verifier = (
            base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        )
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        params = {
            "client_id": self.client_id,
            "redirect_uri": settings.oauth_redirect_uri,
            "response_type": "code",
            "scope": "",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return (
            f"{self.metadata['authorization_endpoint']}?{urlencode(params)}",
            verifier,
        )

    # ---- Exchange code for tokens ----
    async def exchange_code(self, code: str, verifier: str) -> dict:
        logger.debug("OAUTH: Exchanging code for token for server '%s'", self.server)
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.oauth_redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code_verifier": verifier,
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(self.metadata["token_endpoint"], data=data)
        r.raise_for_status()
        logger.debug("OAUTH: Token exchange successful for '%s'", self.server)
        return r.json()

    # ---- Refresh ----
    async def refresh(self, refresh_token: str) -> dict:
        logger.debug("OAUTH: Refreshing token for server '%s'", self.server)
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(self.metadata["token_endpoint"], data=data)
        r.raise_for_status()
        logger.debug("OAUTH: Token refresh successful for '%s'", self.server)
        return r.json()


# ---- Metadata discovery for each server ----
SERVERS = {
    "notion": "https://mcp.notion.com/.well-known/oauth-authorization-server",
    "linear": "https://mcp.linear.app/.well-known/oauth-authorization-server",
}


async def discover(server: str) -> dict:
    logger.debug("OAUTH: Discovering metadata for server '%s'", server)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(SERVERS[server])
    r.raise_for_status()
    logger.debug("OAUTH: Metadata discovered for '%s'", server)
    return r.json()
