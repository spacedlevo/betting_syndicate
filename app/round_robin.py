from datetime import date, timedelta
from typing import Optional
from dataclasses import dataclass
from random import shuffle


@dataclass
class WeekSlot:
    week_number: int
    start_date: date
    end_date: date
    player1_id: int
    player2_id: Optional[int]  # None = solo week


def generate_round_robin(player_ids: list) -> list:
    """
    Generate one full rotation cycle using the circle method.

    For even N: N-1 rounds, N/2 pairs each = N(N-1)/2 total weeks.
    For odd N: add a dummy player (None), N rounds, with one solo per round.
    Returns list of (player1_id, player2_id_or_None) tuples.
    """
    player_ids = list(player_ids)
    shuffle(player_ids)
    n = len(player_ids)
    if n < 2:
        raise ValueError("Need at least 2 players to generate a schedule")

    is_odd = n % 2 == 1
    sched = list(player_ids) + ([None] if is_odd else [])
    m = len(sched)

    fixed = sched[0]
    rotating = list(sched[1:])  # m-1 elements
    print(rotating)
    matches = []

    for _ in range(m - 1):
        round_pairs = [(fixed, rotating[-1])] + [
            (rotating[i], rotating[m - 3 - i]) for i in range(m // 2 - 1)
        ]
        if is_odd:
            round_pairs = [p for p in round_pairs if p[0] is not None and p[1] is not None] + \
                          [p for p in round_pairs if p[0] is None or p[1] is None]
        for p1, p2 in round_pairs:
            if p1 is None:
                matches.append((p2, None))
            elif p2 is None:
                matches.append((p1, None))
            else:
                matches.append((p1, p2))
        rotating = [rotating[-1]] + rotating[:-1]

    return matches


def generate_season_schedule(
    player_ids: list,
    season_start: date,
    num_weeks: int,
) -> list:
    """
    Generate a full season schedule, cycling the round-robin pattern.

    Returns list of WeekSlot objects with week numbers and dates.
    """
    cycle = generate_round_robin(player_ids)
    cycle_len = len(cycle)
    slots = []

    for i in range(num_weeks):
        p1, p2 = cycle[i % cycle_len]
        start = season_start + timedelta(weeks=i)
        end = start + timedelta(days=6)
        slots.append(WeekSlot(
            week_number=i + 1,
            start_date=start,
            end_date=end,
            player1_id=p1,
            player2_id=p2,
        ))

    return slots
