import asyncio

import httpx
from fastapi import status
from httpx import ASGITransport

from app.main import app


async def test_health_endpoint() -> None:
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_health_sync() -> None:
    asyncio.run(test_health_endpoint())
