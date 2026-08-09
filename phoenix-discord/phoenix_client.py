"""
Phoenix Chat API Client
Lightweight async HTTP client for the Phoenix Chat API.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from config import (
    PHOENIX_API_BASE,
    PHOENIX_API_SECRET,
    REQUEST_TIMEOUT,
)

log = logging.getLogger("phoenix_client")


class PhoenixClient:
    """Async client for Phoenix Chat API."""

    def __init__(self):
        self.base = PHOENIX_API_BASE
        self.headers = {
            "Authorization": f"Bearer {PHOENIX_API_SECRET}",
            "Content-Type": "application/json",
        }
        self._client_session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._client_session is None or self._client_session.closed:
            self._client_session = aiohttp.ClientSession(headers=self.headers)
        return self._client_session

    async def close(self):
        if self._client_session and not self._client_session.closed:
            await self._client_session.close()
            self._client_session = None

    async def _post(self, path: str, payload: Dict) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        session = await self._get_session()
        try:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    log.error(f"Phoenix API error {resp.status}: {body}")
                    raise RuntimeError(f"Phoenix API {resp.status}: {body.get('error', 'unknown')}")
                return body
        except aiohttp.ClientError as e:
            log.error(f"Phoenix API connection error: {e}")
            raise

    async def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        session = await self._get_session()
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    log.error(f"Phoenix API error {resp.status}: {body}")
                    raise RuntimeError(f"Phoenix API {resp.status}: {body.get('error', 'unknown')}")
                return body
        except aiohttp.ClientError as e:
            log.error(f"Phoenix API connection error: {e}")
            raise

    async def dm(self, agent: str, message: str, history: Optional[List[Dict]] = None) -> str:
        """Send a direct message to an agent. Returns the agent's response text."""
        payload = {
            "agent": agent,
            "message": message,
            "history": history or [],
        }
        result = await self._post("/chat/dm", payload)
        return result.get("response", "")

    async def list_agents(self) -> List[Dict[str, Any]]:
        """List available agents."""
        result = await self._get("/chat/agents")
        return result.get("agents", [])

    async def append_memory(self, agent: str, line: str) -> bool:
        """Append a line to the agent's MEMORY.md."""
        payload = {"agent": agent, "line": line}
        try:
            await self._post("/chat/memory", payload)
            return True
        except Exception as e:
            log.error(f"Failed to append memory: {e}")
            return False

    async def health_check(self) -> bool:
        """Quick health check."""
        try:
            await self._get("/chat/agents")
            return True
        except Exception:
            return False
