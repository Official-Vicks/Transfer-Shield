from fastapi import FastAPI
from app import models, schemas,services
from app.api.v1.router import router as api_router
from app.core.config import settings

app = FastAPI(title="Transfer Shield")

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def start_message():
    return ("Api is live")
@app.get("/health")
def get_health():
    return{"status": "ok"}
