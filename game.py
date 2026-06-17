"""Battle-royale game engine (pure logic, no Telegram dependencies).

The engine simulates a full game up-front and records, round by round, what
happened (as structured events) and how many players are left alive. The bot
then "narrates" those rounds one at a time with delays for suspense.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Player:
    user_id: int
    name: str
    alive: bool = True
    kills: int = 0


@dataclass
class GameConfig:
    accident_chance: float = 0.15      # chance a death is an "accident" (no killer)
    double_kill_chance: float = 0.12   # chance a kill becomes a double kill
    revive_chance: float = 0.08        # chance a dead player is revived in a round


# ---- Structured events -----------------------------------------------------

@dataclass
class KillEvent:
    killer_id: int
    victim_id: int


@dataclass
class DoubleKillEvent:
    killer_id: int
    victim1_id: int
    victim2_id: int


@dataclass
class AccidentEvent:
    victim_id: int


@dataclass
class ReviveEvent:
    player_id: int


@dataclass
class RoundResult:
    events: list
    alive_after: int


@dataclass
class GameResult:
    rounds: list           # list[RoundResult]
    winner_id: int | None
    total_rounds: int


# ---- Simulation ------------------------------------------------------------

def _simulate_round(players: list[Player], rng: random.Random, cfg: GameConfig) -> list:
    events: list = []
    alive = [p for p in players if p.alive]
    dead = [p for p in players if not p.alive]

    # Occasionally revive one dead player (only if a real fight is still going).
    if dead and len(alive) >= 2 and rng.random() < cfg.revive_chance:
        revived = rng.choice(dead)
        revived.alive = True
        events.append(ReviveEvent(revived.user_id))

    alive = [p for p in players if p.alive]
    # How many die this round (always >= 1 so the game progresses, never all).
    # ~1/5 of the living can fall in a round, so games run a bit longer.
    max_deaths = max(1, len(alive) // 5)
    n_deaths = min(rng.randint(1, max_deaths), len(alive) - 1)

    for _ in range(n_deaths):
        current = [p for p in players if p.alive]
        if len(current) <= 1:
            break

        accident = rng.random() < cfg.accident_chance
        if accident:
            victim = rng.choice(current)
            victim.alive = False
            events.append(AccidentEvent(victim.user_id))
            continue

        victim = rng.choice(current)
        killers = [p for p in current if p is not victim]
        killer = rng.choice(killers)
        others = [p for p in current if p is not victim and p is not killer]

        # Double kill: only if at least one player would remain afterwards.
        if others and rng.random() < cfg.double_kill_chance and len(current) - 2 >= 1:
            victim2 = rng.choice(others)
            victim.alive = False
            victim2.alive = False
            killer.kills += 2
            events.append(DoubleKillEvent(killer.user_id, victim.user_id, victim2.user_id))
        else:
            victim.alive = False
            killer.kills += 1
            events.append(KillEvent(killer.user_id, victim.user_id))

    return events


def run_game(players: list[Player], rng: random.Random | None = None,
             cfg: GameConfig | None = None) -> GameResult:
    """Run a full game. Mutates ``players`` (sets .alive / .kills)."""
    rng = rng or random.Random()
    cfg = cfg or GameConfig()

    rounds: list[RoundResult] = []
    round_no = 0
    while sum(1 for p in players if p.alive) > 1 and round_no < 5000:
        round_no += 1
        events = _simulate_round(players, rng, cfg)
        alive_after = sum(1 for p in players if p.alive)
        rounds.append(RoundResult(events=events, alive_after=alive_after))

    winner = next((p for p in players if p.alive), None)
    return GameResult(rounds=rounds, winner_id=winner.user_id if winner else None,
                      total_rounds=round_no)
