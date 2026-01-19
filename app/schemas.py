"""
Pydantic schemas for request/response validation in FastAPI.

These schemas define the structure of data for API endpoints.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


# Season Schemas
class SeasonBase(BaseModel):
    name: str = Field(..., max_length=100)
    start_date: date
    end_date: Optional[date] = None
    is_active: bool = True


class SeasonCreate(SeasonBase):
    pass


class SeasonUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    end_date: Optional[date] = None
    is_active: Optional[bool] = None


class SeasonResponse(SeasonBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Player Schemas
class PlayerBase(BaseModel):
    name: str = Field(..., max_length=100)
    email: Optional[EmailStr] = None
    is_active: bool = True


class PlayerCreate(PlayerBase):
    pass


class PlayerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class PlayerResponse(PlayerBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# PlayerSeason Schemas
class PlayerSeasonBase(BaseModel):
    player_id: int
    season_id: int
    joined_date: date
    is_active: bool = True


class PlayerSeasonCreate(PlayerSeasonBase):
    pass


class PlayerSeasonResponse(PlayerSeasonBase):
    id: int

    class Config:
        from_attributes = True


# Week Schemas
class WeekBase(BaseModel):
    season_id: int
    week_number: int
    start_date: date
    end_date: date


class WeekCreate(WeekBase):
    pass


class WeekResponse(WeekBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# WeekAssignment Schemas
class WeekAssignmentBase(BaseModel):
    week_id: int
    player_id: int
    assignment_order: int = Field(..., ge=1, le=2)


class WeekAssignmentCreate(WeekAssignmentBase):
    pass


class WeekAssignmentResponse(WeekAssignmentBase):
    id: int

    class Config:
        from_attributes = True


# LedgerEntry Schemas
class LedgerEntryBase(BaseModel):
    entry_date: date
    entry_type: str = Field(..., pattern="^(contribution|bet_placed|winnings_share|bet_void|payout)$")
    player_id: int
    season_id: int
    week_id: Optional[int] = None
    amount: Decimal = Field(..., decimal_places=2)
    description: Optional[str] = None
    bet_id: Optional[int] = None
    created_by: Optional[str] = Field(None, max_length=100)


class LedgerEntryCreate(LedgerEntryBase):
    pass


class LedgerEntryResponse(LedgerEntryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Bet Schemas
class BetBase(BaseModel):
    week_id: int
    placed_by_player_id: int
    stake: Decimal = Field(..., gt=0, decimal_places=2)
    description: str
    odds: Optional[str] = Field(None, max_length=50)
    bet_date: date
    notes: Optional[str] = None


class BetCreate(BetBase):
    pass


class BetUpdate(BaseModel):
    description: Optional[str] = None
    odds: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class BetResultUpdate(BaseModel):
    status: str = Field(..., pattern="^(won|lost|void)$")
    result_date: date
    winnings: Optional[Decimal] = Field(None, decimal_places=2)

    @validator('winnings')
    def validate_winnings(cls, v, values):
        if values.get('status') == 'won' and not v:
            raise ValueError("Winnings must be provided when status is 'won'")
        if values.get('status') in ['lost', 'void'] and v:
            raise ValueError(f"Winnings should not be provided when status is '{values.get('status')}'")
        return v


class BetResponse(BetBase):
    id: int
    status: str
    result_date: Optional[date] = None
    winnings: Optional[Decimal] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Contribution Schemas
class ContributionCreate(BaseModel):
    player_id: int
    season_id: int
    week_id: Optional[int] = None
    amount: Decimal = Field(default=Decimal('5.00'), gt=0, decimal_places=2)
    entry_date: date


# Payout Schemas
class PayoutCreate(BaseModel):
    player_id: int
    season_id: int
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    entry_date: date
    description: Optional[str] = None
