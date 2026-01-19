# Betting Syndicate Manager

A web application to manage a betting syndicate with 12 players. Tracks contributions, bets, winnings, and calculates fair payouts for all members.

## Features

- **Ledger-based accounting** - All values derived from immutable ledger entries
- **Player management** - Track 12 players across seasons
- **Weekly contributions** - £5 per player per week (calculated from Mondays)
- **Bet tracking** - Record bets with odds, stakes, and screenshot uploads
- **Automatic calculations** - Bank balance, profit/loss, payouts per player
- **Week assignments** - Rotate who places bets each week
- **WhatsApp summary** - Screenshot-friendly page for group sharing
- **Season management** - Freeze seasons and manage year-to-year transitions

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone or download the project
cd betting_syndicate

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create upload directories
mkdir -p uploads/screenshots

# Run the application
uvicorn app.main:app --reload
```

Visit `http://localhost:8000` in your browser.

### First Time Setup

1. Create a season at `/seasons/new`
2. Add players at `/players/new`
3. Add players to the season from `/players`
4. Import week assignments at `/import` (optional)
5. Start adding contributions and placing bets!

## Key Formulas

| Metric | Formula |
|--------|---------|
| **Bank Balance** | (Paid In + Bets Won) - Bets Placed - Paid Out |
| **Expected Contribution** | Number of Mondays × £5 |
| **Share Per Player** | Total Winnings ÷ Active Players |
| **Profit/Loss** | Won - Bets Placed |
| **Bet Balance** | ROUNDUP(weeks/6) × 30 - Bets Placed |
| **Payout** | (Balance - Expected) + Share Per Player |

## Project Structure

```
betting_syndicate/
├── app/
│   ├── main.py              # FastAPI application entry
│   ├── database.py          # Database connection
│   ├── models.py            # SQLAlchemy models
│   ├── calculations.py      # Financial calculations
│   ├── ledger.py            # Ledger operations
│   ├── import_data.py       # CSV import utilities
│   ├── routes/
│   │   ├── dashboard.py     # Main dashboard & summary
│   │   ├── bets.py          # Bet management
│   │   ├── players.py       # Player management
│   │   ├── seasons.py       # Season management
│   │   └── ledger_routes.py # Ledger & contributions
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS and static assets
├── uploads/
│   └── screenshots/         # Bet slip images
├── docs/
│   ├── DATABASE.md          # Database schema documentation
│   ├── SEASONS.md           # Season management guide
│   └── DEPLOYMENT.md        # Proxmox deployment guide
└── requirements.txt
```

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard with syndicate overview |
| `/summary` | WhatsApp-friendly screenshot page |
| `/bets` | List and manage bets |
| `/bets/new` | Place a new bet |
| `/players` | Player list with stats |
| `/ledger` | Transaction history |
| `/ledger/contribute` | Add weekly contributions |
| `/ledger/payout` | Record payouts |
| `/seasons` | Manage seasons |
| `/import` | Import CSV data |

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for instructions on deploying to a Proxmox VM.

## Documentation

- [Database Schema](docs/DATABASE.md) - Tables, relationships, and calculated values
- [Season Management](docs/SEASONS.md) - Creating, freezing, and managing seasons
- [Deployment Guide](docs/DEPLOYMENT.md) - Step-by-step Proxmox deployment

## Technology Stack

- **Backend**: Python, FastAPI, SQLAlchemy
- **Database**: SQLite
- **Frontend**: Jinja2 templates, Chart.js
- **Server**: Uvicorn (dev), Nginx + Uvicorn (production)

## License

Private project for syndicate management.
