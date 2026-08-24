from fastapi import FastAPI

from martevi.api import item_router

app = FastAPI()


app.include_router(item_router)