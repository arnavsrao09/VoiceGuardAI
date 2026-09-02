import asyncio
from app.main import lifespan
from fastapi import FastAPI

async def test():
    print("Testing lifespan")
    async with lifespan(FastAPI()):
        print("Lifespan initialized successfully")

asyncio.run(test())
