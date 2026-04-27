import httpx

from .config import settings


async def get_gender(name: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.GENDERIZE_BASE_URL, params={"name": name})
        response.raise_for_status()
        return response.json()


async def get_age(name: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.AGIFY_BASE_URL, params={"name": name})
        response.raise_for_status()
        return response.json()


async def get_nationality(name: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            settings.NATIONALIZE_BASE_URL, params={"name": name}
        )
        response.raise_for_status()
        return response.json()
