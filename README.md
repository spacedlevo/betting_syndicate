# Betting Syndicate Manager

A web application to manage a betting syndicate. Tracks contributions, bets, winnings, and calculates fair payouts for all members.

## Features

- **Ledger-based accounting** - All values derived from immutable ledger entries
- **Player management** - Track players across seasons
- **Weekly contributions** - Configurable per-player weekly contribution (default £5)
- **Bet tracking** - Record bets with odds, stakes, sport, and screenshot uploads
- **Automatic calculations** - Bank balance, profit/loss, payouts per player
- **Round-robin schedule** - Auto-generate a fair rotation for who places bets each week, supports odd player counts (solo weeks)
- **Sports management** - Categorise bets by sport
- **WhatsApp summary** - Screenshot-friendly page for group sharing
- **Season management** - Per-season contribution and betting budget config; freeze completed seasons
- **Bank statement import** - Import CSV exports from Monzo, TSB, and PayPal
- **Audit page** - Reconcile bank transactions against ledger entries (auto-match, manual link, disregard)
- **Dark/light theme** - Toggle via the UI

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

1. Create a season at `/seasons/new` (set weekly contribution and betting budget)
2. Add players at `/players/new`
3. Add players to the season from `/players`
4. Generate a round-robin schedule at `/seasons/{id}/schedule/generate`
5. Start adding contributions and placing bets!

## Key Formulas

| Metric | Formula |
|--------|---------|
| **Bank Balance** | (Paid In + Bets Won) - Bets Placed - Paid Out |
| **Expected Contribution** | Number of Mondays × weekly contribution |
| **Share Per Player** | Total Winnings ÷ Active Players |
| **Profit/Loss** | Won - Bets Placed |
| **Bet Balance** | (weekly_contribution × total_scheduled_weeks) - Bets Placed |
| **Payout** | (Balance - Expected) + Share Per Player |

## Project Structure

```
betting_syndicate/
├── app/
│   ├── main.py              # FastAPI application entry
│   ├── database.py          # Database connection
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── calculations.py      # Financial calculations
│   ├── ledger.py            # Ledger operations
│   ├── round_robin.py       # Round-robin schedule generation
│   ├── bank_import.py       # Bank statement CSV import logic
│   ├── flash.py             # Flash message middleware
│   ├── import_data.py       # Legacy CSV import utilities
│   ├── routes/
│   │   ├── dashboard.py     # Main dashboard & summary
│   │   ├── bets.py          # Bet management
│   │   ├── players.py       # Player management
│   │   ├── seasons.py       # Season management & schedule generation
│   │   ├── sports.py        # Sport category management
│   │   ├── ledger_routes.py # Ledger & contributions
│   │   ├── import_routes.py # Bank statement import
│   │   └── audit.py         # Bank transaction reconciliation
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS (theme toggle)
├── uploads/
│   └── screenshots/         # Bet slip images
├── bank statements/         # Raw CSV exports (Monzo, TSB, PayPal)
├── docs/
│   ├── DATABASE.md          # Database schema documentation
│   ├── SEASONS.md           # Season management and schedule generation
│   ├── BETS.md              # Bet lifecycle and winnings calculations
│   ├── BANK_IMPORT.md       # Bank statement import and audit
│   ├── DEPLOYMENT.md        # Proxmox deployment guide
│   ├── CHANGELOG.md         # History of notable changes
│   └── UX_REVIEW.md         # UX review notes
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
| `/seasons/{id}/schedule` | View week assignment schedule |
| `/seasons/{id}/schedule/generate` | Generate round-robin schedule |
| `/sports` | Manage sport categories |
| `/import` | Import bank statement CSVs |
| `/audit` | Reconcile bank transactions with ledger |

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for instructions on deploying to a Proxmox VM.

## Documentation

- [Database Schema](docs/DATABASE.md) - Tables, relationships, and calculated values
- [Season Management](docs/SEASONS.md) - Creating, freezing, managing seasons, and round-robin schedule generation
- [Bets and Winnings](docs/BETS.md) - Bet lifecycle, free bets, pot bets, payout calculations
- [Bank Import and Audit](docs/BANK_IMPORT.md) - Importing bank statement CSVs and reconciling contributions
- [Deployment Guide](docs/DEPLOYMENT.md) - Step-by-step Proxmox deployment
- [UX Review](docs/UX_REVIEW.md) - UX notes and improvement history
- [Changelog](docs/CHANGELOG.md) - History of notable changes

## Technology Stack

- **Backend**: Python, FastAPI, SQLAlchemy
- **Database**: SQLite
- **Frontend**: Jinja2 templates, Chart.js, vanilla JS (theme toggle)
- **Server**: Uvicorn (dev), Nginx + Uvicorn (production)

## License

Private project for syndicate management.
