from typing import Tuple

from databases import Database
from fastapi import FastAPI

from courator.config import DATABASE_URL, DEBUG

app = FastAPI()
db = Database(DATABASE_URL)


def setup_globals():
    app.on_event("startup")(db.connect)
    app.on_event("shutdown")(db.disconnect)
    from .routes import router
    app.include_router(router)


setup_globals()
