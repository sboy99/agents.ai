import asyncio
import logging
import time

import aiosqlite

from ..config import TOKENS_DB

logger = logging.getLogger(__name__)


class TokenStore:
    def __init__(self, path=TOKENS_DB):
        self.path = str(path)
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def start(self):
        logger.debug("TOKEN_STORE: Opening database at %s", self.path)
        async with self._lock:
            if self._db:
                logger.debug("TOKEN_STORE: Database already open, skipping")
                return
            self._db = await aiosqlite.connect(self.path)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    server TEXT PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    expires_at REAL,
                    scope TEXT,
                    client_id TEXT,
                    client_secret TEXT
                )""")
            await self._db.commit()
            logger.debug("TOKEN_STORE: Database initialized with oauth_tokens table")

    async def save(self, server: str, token: dict, client: dict):
        logger.debug("TOKEN_STORE: Saving token for server '%s'", server)
        await self.start()
        assert self._db is not None
        await self._db.execute(
            "INSERT OR REPLACE INTO oauth_tokens VALUES (?,?,?,?,?,?,?)",
            (
                server,
                token.get("access_token", ""),
                token.get("refresh_token", ""),
                time.time() + token.get("expires_in", 3600),
                token.get("scope", ""),
                client.get("client_id", ""),
                client.get("client_secret", ""),
            ),
        )
        await self._db.commit()
        logger.debug("TOKEN_STORE: Token saved for '%s'", server)

    async def load(self, server: str) -> dict | None:
        logger.debug("TOKEN_STORE: Loading token for server '%s'", server)
        await self.start()
        assert self._db is not None
        cur = await self._db.execute(
            "SELECT * FROM oauth_tokens WHERE server=?", (server,)
        )
        row = await cur.fetchone()
        if not row:
            logger.debug("TOKEN_STORE: No token found for '%s'", server)
            return None
        result = {
            "access_token": row[1],
            "refresh_token": row[2],
            "expires_at": row[3],
            "scope": row[4],
            "client_id": row[5],
            "client_secret": row[6],
        }
        logger.debug("TOKEN_STORE: Token loaded for '%s'", server)
        return result

    async def aclose(self):
        logger.debug("TOKEN_STORE: Closing database connection")
        async with self._lock:
            if self._db:
                await self._db.close()
                self._db = None


token_store = TokenStore()
