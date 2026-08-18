"""
Season management routes.
"""

from decimal import Decimal

from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import date
from typing import Optional

from app.database import get_db
from app.models import Season, Player, PlayerSeason, Week, WeekAssignment
from app.round_robin import generate_season_schedule

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
    weekly_contribution: Decimal = Form(Decimal('5.00')),
    weekly_betting_budget: Decimal = Form(Decimal('27.50')),
    db: Session = Depends(get_db)
):
    """Create a new season."""
    form_data = await request.form()
    selected_player_ids = [int(pid) for pid in form_data.getlist("players")]

    db.query(Season).update({Season.is_active: False})

    season = Season(
        name=name,
        start_date=start_date,
        end_date=end_date,
        is_active=True,
        weekly_contribution=weekly_contribution,
        weekly_betting_budget=weekly_betting_budget,
    )
    db.add(season)
    db.commit()
    db.refresh(season)

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


@router.get("/{season_id}/schedule/generate", response_class=HTMLResponse)
async def generate_schedule_form(season_id: int, request: Request, db: Session = Depends(get_db)):
    """Show form to generate a round-robin schedule for a season."""
    season = db.query(Season).filter(Season.id == season_id).first()
    if not season:
        return RedirectResponse(url="/seasons", status_code=303)

    player_seasons = db.query(PlayerSeason).filter(
        PlayerSeason.season_id == season_id,
        PlayerSeason.is_active == True
    ).all()

    existing_weeks = db.query(Week).filter(Week.season_id == season_id).count()

    return templates.TemplateResponse("seasons/generate_schedule.html", {
        "request": request,
        "season": season,
        "player_count": len(player_seasons),
        "existing_weeks": existing_weeks,
    })


@router.post("/{season_id}/schedule/generate")
async def generate_schedule(
    season_id: int,
    schedule_start: date = Form(...),
    num_weeks: int = Form(...),
    db: Session = Depends(get_db)
):
    """Generate a round-robin schedule, replacing any existing weeks."""
    season = db.query(Season).filter(Season.id == season_id).first()
    if not season:
        return RedirectResponse(url="/seasons", status_code=303)

    # Get active players in season
    player_seasons = db.query(PlayerSeason).filter(
        PlayerSeason.season_id == season_id,
        PlayerSeason.is_active == True
    ).order_by(PlayerSeason.id).all()

    player_ids = [ps.player_id for ps in player_seasons]

    if len(player_ids) < 2:
        return RedirectResponse(url=f"/seasons/{season_id}/schedule/generate", status_code=303)

    # Clear existing weeks and assignments for this season
    existing_weeks = db.query(Week).filter(Week.season_id == season_id).all()
    for week in existing_weeks:
        db.query(WeekAssignment).filter(WeekAssignment.week_id == week.id).delete()
    db.query(Week).filter(Week.season_id == season_id).delete()
    db.commit()

    # Generate schedule
    slots = generate_season_schedule(player_ids, schedule_start, num_weeks)

    for slot in slots:
        week = Week(
            season_id=season_id,
            week_number=slot.week_number,
            start_date=slot.start_date,
            end_date=slot.end_date,
        )
        db.add(week)
        db.flush()

        db.add(WeekAssignment(week_id=week.id, player_id=slot.player1_id, assignment_order=1))
        if slot.player2_id is not None:
            db.add(WeekAssignment(week_id=week.id, player_id=slot.player2_id, assignment_order=2))

    db.commit()
    return RedirectResponse(url="/schedule", status_code=303)
