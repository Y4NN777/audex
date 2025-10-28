import httpx
from fastapi import status
from httpx import ASGITransport
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
