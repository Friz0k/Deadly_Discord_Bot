import aiohttp
import asyncio
from config import WIKI_API

async def search_wiki(query: str):
    params = {
        "action": "opensearch",
        "search": query,
        "limit": 5,
        "format": "json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(WIKI_API, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                if len(data) >= 4 and data[1]:
                    return list(zip(data[1], data[2], data[3]))
                return []
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return []
