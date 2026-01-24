"""
Season management routes.
"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import date
from typing import Optional

from app.database import get_db
from app.models import Season, Player, PlayerSeason

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def is_season_frozen(season: Season) -> bool:
    """Check if a season is frozen (end date has passed)."""
    if not season or not season.end_date:
        return False
    return date.today() > season.end_date


@router.get("/", response_class=HTMLResponse)
async def list_seasons(request: Request, db: Session = Depends(get_db)):
    """List all seasons."""
    seasons = db.query(Season).order_by(Season.start_date.desc()).all()

    # Add frozen status to each season
    season_data = []
    for season in seasons:
        season_data.append({
            'season': season,
            'is_frozen': is_season_frozen(season)
        })

    return templates.TemplateResponse("seasons/list.html", {
        "request": request,
        "season_data": season_data
    })


@router.get("/new", response_class=HTMLResponse)
async def new_season_form(request: Request, db: Session = Depends(get_db)):
    """Show form to create a new season."""
    players = db.query(Player).filter(Player.is_active == True).order_by(Player.name).all()
    return templates.TemplateResponse("seasons/form.html", {
        "request": request,
        "season": None,
        "players": players
    })


@router.post("/")
async def create_season(
    request: Request,
    name: str = Form(...),
    start_date: date = Form(...),
    end_date: Optional[date] = Form(None),
    db: Session = Depends(get_db)
):
    """Create a new season."""
    # Get selected player IDs from form
    form_data = await request.form()
    selected_player_ids = [int(pid) for pid in form_data.getlist("players")]

    # Deactivate all other seasons
    db.query(Season).update({Season.is_active: False})

    season = Season(
        name=name,
        start_date=start_date,
        end_date=end_date,
        is_active=True
    )
    db.add(season)
    db.commit()
    db.refresh(season)

    # Add selected players to the season
    for player_id in selected_player_ids:
        ps = PlayerSeason(
            player_id=player_id,
            season_id=season.id,
            joined_date=start_date,
            is_active=True
        )
        db.add(ps)
    db.commit()

    return RedirectResponse(url="/seasons", status_code=303)


@router.post("/{season_id}/activate")
async def activate_season(season_id: int, db: Session = Depends(get_db)):
    """Set a season as active."""
    # Deactivate all seasons
    db.query(Season).update({Season.is_active: False})

    # Activate the selected season
    season = db.query(Season).filter(Season.id == season_id).first()
    if season:
        season.is_active = True
        db.commit()

    return RedirectResponse(url="/seasons", status_code=303)


@router.get("/{season_id}/edit", response_class=HTMLResponse)
async def edit_season_form(season_id: int, request: Request, db: Session = Depends(get_db)):
    """Show form to edit a season (set end date)."""
    season = db.query(Season).filter(Season.id == season_id).first()
    if not season:
        return RedirectResponse(url="/seasons", status_code=303)

    return templates.TemplateResponse("seasons/edit.html", {
        "request": request,
        "season": season,
        "is_frozen": is_season_frozen(season)
    })


@router.post("/{season_id}/edit")
async def update_season(
    season_id: int,
    end_date: Optional[date] = Form(None),
    db: Session = Depends(get_db)
):
    """Update a season's end date."""
    season = db.query(Season).filter(Season.id == season_id).first()
    if season:
        season.end_date = end_date
        db.commit()

    return RedirectResponse(url="/seasons", status_code=303)
