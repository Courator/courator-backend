import logging

from databases import DatabaseURL
from starlette.config import Config
from starlette.datastructures import Secret

from .logging import setup_logging

config = Config(".env")
DEBUG = config("DEBUG", cast=bool, default=False)
DATABASE_URL: DatabaseURL = config("DB_CONNECTION", cast=DatabaseURL)
SECRET_KEY: Secret = config("SECRET_KEY", cast=Secret)
TOKEN_EXPIRATION_DAYS: float = config("TOKEN_EXPIRATION_DAYS", cast=float, default=60.0)
TOKEN_ALGORITHM = "HS256"

setup_logging(
    ("uvicorn.asgi", "uvicorn.access"),
    logging.DEBUG if DEBUG else logging.INFO
)


# import aioredis
# from aioredis import Redis
# REDIS_HOST: str = config("REDIS_HOST")
# REDIS_PORT: int = config("REDIS_PORT", cast=int)
# async def get_redis() -> Redis:
#     pool = await aioredis.create_redis_pool((REDIS_HOST, REDIS_PORT), encoding='utf-8')
#     try:
#         yield pool
#     finally:
#         pool.close()
