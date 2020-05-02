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

