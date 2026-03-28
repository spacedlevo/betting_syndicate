"""
Sports management routes.
"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app.models import Sport

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def list_sports(request: Request, db: Session = Depends(get_db)):
    """List all sports."""
    sports = db.query(Sport).order_by(Sport.name).all()
    
    return templates.TemplateResponse("sports/list.html", {
        "request": request,
        "sports": sports
    })


@router.get("/new", response_class=HTMLResponse)
async def new_sport_form(request: Request):
    """Show form to create a new sport."""
    return templates.TemplateResponse("sports/form.html", {
        "request": request,
        "sport": None
    })


@router.post("/")
async def create_sport(
    name: str = Form(...),
    db: Session = Depends(get_db)
):
    """Create a new sport."""
    # Check if sport already exists
    existing_sport = db.query(Sport).filter(Sport.name == name.strip()).first()
    if existing_sport:
        return RedirectResponse(url="/sports?error=Sport already exists", status_code=303)
    
    # Create new sport
    sport = Sport(name=name.strip())
    db.add(sport)
    db.commit()
    
    return RedirectResponse(url="/sports", status_code=303)


@router.get("/{sport_id}", response_class=HTMLResponse)
async def sport_detail(sport_id: int, request: Request, db: Session = Depends(get_db)):
    """Show sport details."""
    sport = db.query(Sport).filter(Sport.id == sport_id).first()
    if not sport:
        return RedirectResponse(url="/sports", status_code=303)
    
    return templates.TemplateResponse("sports/detail.html", {
        "request": request,
        "sport": sport
    })