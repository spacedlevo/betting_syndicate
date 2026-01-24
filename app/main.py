"""
FastAPI main application entry point for the Betting Syndicate Manager.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.database import init_db
from app.routes import dashboard, players, bets, ledger_routes, seasons, import_routes

# Initialize FastAPI app
app = FastAPI(
    title="Betting Syndicate Manager",
    description="A ledger-based betting syndicate management system",
    version="1.0.0"
)

# Get the app directory path
APP_DIR = Path(__file__).parent
BASE_DIR = APP_DIR.parent

# Mount static files
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=BASE_DIR / "uploads"), name="uploads")

# Set up templates
templates = Jinja2Templates(directory=APP_DIR / "templates")

# Register routes
app.include_router(dashboard.router, prefix="", tags=["Dashboard"])
app.include_router(seasons.router, prefix="/seasons", tags=["Seasons"])
app.include_router(players.router, prefix="/players", tags=["Players"])
app.include_router(bets.router, prefix="/bets", tags=["Bets"])
app.include_router(ledger_routes.router, prefix="/ledger", tags=["Ledger"])
app.include_router(import_routes.router, prefix="/import", tags=["Import"])


@app.on_event("startup")
async def startup_event():
    """Initialize the database on startup."""
    init_db()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
