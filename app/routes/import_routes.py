"""
Data import routes for importing historical data from CSV files.
"""

from fastapi import APIRouter, Request, Depends, Form, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import date
from typing import Optional
import tempfile
import os

from app.database import get_db
from app.models import Season, Player
from app.import_data import (
    import_season,
    import_players,
    assign_players_to_season,
    import_transactions_from_csv,
    import_week_assignments
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def import_page(request: Request, db: Session = Depends(get_db)):
    """Show import page with options."""
    seasons = db.query(Season).order_by(Season.start_date.desc()).all()

    return templates.TemplateResponse("import/index.html", {
        "request": request,
        "seasons": seasons,
        "result": None
    })


@router.post("/transactions", response_class=HTMLResponse)
async def import_transactions(
    request: Request,
    season_name: str = Form(...),
    start_date: date = Form(...),
    end_date: Optional[date] = Form(None),
    is_active: bool = Form(False),
    csv_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import transactions from CSV file."""
    result = {
        'success': False,
        'message': '',
        'details': {}
    }

    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp:
            contents = await csv_file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            # Read CSV to get unique player names
            import csv
            player_names = set()
            with open(tmp_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('Player'):
                        player_names.add(row['Player'].strip())

            player_names = sorted(player_names)

            # If creating as active, deactivate other seasons
            if is_active:
                db.query(Season).update({Season.is_active: False})

            # Create or get season
            season = import_season(db, season_name, start_date, end_date)
            if not is_active:
                season.is_active = False
                db.commit()

            # Create players
            players = import_players(db, player_names)

            # Assign players to season
            assign_players_to_season(db, players, season, start_date)

            # Import transactions
            counts = import_transactions_from_csv(db, tmp_path, season, players)

            result['success'] = True
            result['message'] = f"Successfully imported data into season '{season_name}'"
            result['details'] = {
                'season': season_name,
                'players': len(players),
                'contributions': counts['contributions'],
                'bets_placed': counts['bets_placed'],
                'winnings': counts['winnings'],
                'payouts': counts['payouts'],
                'errors': counts['errors']
            }

        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except Exception as e:
        result['success'] = False
        result['message'] = f"Import failed: {str(e)}"

    seasons = db.query(Season).order_by(Season.start_date.desc()).all()

    return templates.TemplateResponse("import/index.html", {
        "request": request,
        "seasons": seasons,
        "result": result
    })


@router.post("/weeks", response_class=HTMLResponse)
async def import_weeks(
    request: Request,
    season_id: int = Form(...),
    csv_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import week assignments from CSV file."""
    result = {
        'success': False,
        'message': '',
        'details': {}
    }

    try:
        # Get season
        season = db.query(Season).filter(Season.id == season_id).first()
        if not season:
            result['message'] = "Season not found"
            return templates.TemplateResponse("import/index.html", {
                "request": request,
                "seasons": db.query(Season).order_by(Season.start_date.desc()).all(),
                "result": result
            })

        # Get players for this season (build name -> Player dict)
        players = {}
        for player in db.query(Player).all():
            players[player.name] = player

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp:
            contents = await csv_file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            # Import week assignments
            weeks_imported = import_week_assignments(db, tmp_path, season, players)

            result['success'] = True
            result['message'] = f"Successfully imported {weeks_imported} weeks into season '{season.name}'"
            result['details'] = {
                'season': season.name,
                'weeks_imported': weeks_imported
            }

        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except Exception as e:
        result['success'] = False
        result['message'] = f"Import failed: {str(e)}"

    seasons = db.query(Season).order_by(Season.start_date.desc()).all()

    return templates.TemplateResponse("import/index.html", {
        "request": request,
        "seasons": seasons,
        "result": result
    })
