import asyncio
import logging
import time

from langchain_mcp_adapters.client import MultiServerMCPClient

from ..config import settings
from .oauth import OAuthClient, discover
from .token_store import token_store

logger = logging.getLogger(__name__)


class MCPManager:
    def __init__(self):
        self._client = None
        self._tools = {}
        self._lock = asyncio.Lock()
        self._mcp_servers: dict[str, dict] = {}
        self._server_names: set[str] = set()

    async def start(self):
        logger.debug("MCP: Starting MCP connection manager")
        # Skip if already started
        if self._client is not None:
            logger.debug("MCP: Already started, skipping")
            return
        async with self._lock:
            if self._client is not None:
                logger.debug("MCP: Already started (lock recheck), skipping")
                return

            logger.debug("MCP: Acquired lock, initializing servers")
            # ---- Notion & Linear: Tier B OAuth ----
            servers = {}
            for name in ("notion", "linear"):
                logger.debug("MCP: Discovering OAuth metadata for '%s'", name)
                try:
                    meta = await discover(name)
                    logger.debug("MCP: Discovered metadata for '%s'", name)
                    stored = await token_store.load(name)
                    logger.debug(
                        "MCP: Loaded stored tokens for '%s': %s",
                        name,
                        "present" if stored else "none",
                    )
                    oauth = OAuthClient(name, meta)
                    if stored and stored.get("client_id"):
                        logger.debug("MCP: Using stored client_id for '%s'", name)
                        oauth.client_id = stored["client_id"]
                        oauth.client_secret = stored.get("client_secret", "")
                    else:
                        logger.debug("MCP: Registering new OAuth client for '%s'", name)
                        reg = await oauth.register()
                        await token_store.save(
                            name, {"access_token": "", "expires_in": 0}, reg
                        )
                        logger.debug(
                            "MCP: Registered and saved credentials for '%s'", name
                        )
                    token = await self._ensure_token(name, oauth, stored)
                    logger.debug("MCP: Obtained token for '%s'", name)
                    servers[name] = {
                        "transport": "http",
                        "url": meta["protected_resources"][0],
                        "headers": {"Authorization": f"Bearer {token}"},
                    }
                    logger.debug("MCP: Configured server entry for '%s'", name)
                except Exception as e:  # noqa: BLE001
                    # Skip servers that aren't authenticated yet or have network issues
                    # User can login later for auth issues; network issues may work on retry
                    logger.warning("MCP: Failed to set up '%s': %s", name, e)
            self._mcp_servers = servers.copy()
            self._server_names = set(servers.keys())
            logger.debug("MCP: OAuth servers configured: %s", list(servers.keys()))

            # ---- Tavily: API key (default) OR OAuth ----
            tavily_headers = {}
            if settings.tavily_api_key.get_secret_value():
                logger.debug("MCP: Using Tavily API key for authentication")
                tavily_headers["Authorization"] = (
                    f"Bearer {settings.tavily_api_key.get_secret_value()}"
                )
            else:
                stored = await token_store.load("tavily")
                if stored and stored.get("access_token"):
                    logger.debug("MCP: Using stored Tavily access token")
                    tavily_headers["Authorization"] = f"Bearer {stored['access_token']}"
                # keyless dev fallback
                elif settings.tavily_keyless:
                    logger.debug("MCP: Using Tavily keyless mode (dev)")
                    tavily_headers["X-Tavily-Access-Mode"] = "keyless"

            # Only add Tavily if we have headers (API key or keyless mode)
            if tavily_headers:
                servers["tavily"] = {
                    "transport": "http",
                    "url": "https://mcp.tavily.com/mcp/",
                    "headers": tavily_headers,
                }
                logger.debug("MCP: Added tavily server configuration")

            if not servers:
                # No MCP servers available - skip initialization
                logger.warning(
                    "MCP: No MCP servers available, skipping client creation"
                )
                self._client = None
                return

            logger.debug(
                "MCP: Connecting to MultiServerMCPClient with servers: %s",
                list(servers.keys()),
            )
            try:
                self._client = MultiServerMCPClient(servers)
                tools = await self._client.get_tools()
                for t in tools:
                    self._tools[t.name] = t
                logger.debug("MCP: Retrieved %d tools from MCP servers", len(tools))
            except Exception as e:  # noqa: BLE001
                # Failed to connect to MCP servers - tools will be unavailable
                logger.warning("MCP tools unavailable: %s", e)
                self._client = None

    async def get_tool(self, name: str):
        logger.debug("MCP: Requesting tool '%s'", name)
        await self.start()
        if name not in self._tools:
            raise RuntimeError(
                f"MCP tool '{name}' not found. Available: {list(self._tools)}"
            )
        logger.debug("MCP: Returning tool '%s'", name)
        return self._tools[name]

    async def _ensure_token(self, name, oauth, stored) -> str:
        logger.debug("MCP: Ensuring token for '%s'", name)
        if (
            stored
            and stored.get("access_token")
            and stored.get("expires_at", 0) > time.time() + 300
        ):
            logger.debug("MCP: Using existing valid token for '%s'", name)
            return stored["access_token"]
        if stored and stored.get("refresh_token"):
            logger.debug("MCP: Refreshing token for '%s'", name)
            new = await oauth.refresh(stored["refresh_token"])
            await token_store.save(name, new, stored)
            return new["access_token"]
        raise RuntimeError(
            f"{name} not authorized yet. Visit /auth/{name}/login first."
        )

    async def aclose(self):
        logger.debug("MCP: Closing MCP client and token store")
        await token_store.aclose()


mcp = MCPManager()
