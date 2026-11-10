import uuid

from fastapi import APIRouter, HTTPException

from ..mcp.oauth import OAuthClient
from ..mcp.token_store import token_store

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory PKCE state: state -> (server, verifier)
# (Swap for Redis/DB if you run multiple workers.)
_pkce_states: dict[str, tuple[str, str]] = {}


def _oauth_for(server: str) -> OAuthClient:
    meta: dict = {}  # cached at boot (see note below)
    return OAuthClient(server, meta)


@router.get("/{server}/login")
async def login(server: str):
    if server not in ("notion", "linear"):
        raise HTTPException(400, "Unknown server")
    oauth = _oauth_for(server)
    state = uuid.uuid4().hex
    url, verifier = oauth.build_auth_url(state)
    _pkce_states[state] = (server, verifier)
    return {"auth_url": url}


@router.get("/{server}/callback")
async def callback(server: str, code: str, state: str):
    entry = _pkce_states.pop(state, None)
    if not entry or entry[0] != server:
        raise HTTPException(400, "Invalid state")
    _, verifier = entry

    oauth = _oauth_for(server)
    token = await oauth.exchange_code(code, verifier)
    await token_store.save(
        server,
        token,
        {"client_id": oauth.client_id, "client_secret": oauth.client_secret},
    )
    return {
        "status": "connected",
        "server": server,
        "expires_in": token.get("expires_in"),
    }
