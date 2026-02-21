from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import init_db
from app.services.candidate_loader import load_candidates
from app.routers import chat, conversations, candidates, costs

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await load_candidates()
    yield


app = FastAPI(title="CVbot", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(candidates.router)
app.include_router(costs.router)
