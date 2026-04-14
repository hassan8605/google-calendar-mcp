from fastapi import APIRouter

api_router = APIRouter()

from src.nlp.router import router as nlp_router

api_router.include_router(nlp_router)