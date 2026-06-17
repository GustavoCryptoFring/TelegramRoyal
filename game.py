"""Battle-royale game engine (pure logic, no Telegram dependencies)."""
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
    death_fraction: float = 0.30       # ~30% of the living fall each round (avg)
    deaths_cap: int = 12               # never more than this many deaths per round
    flavor_max: int = 3                # up to this many harmless events per round


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
class FlavorEvent:
    """Harmless flavor event — does not change the player count."""
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

    # Occasionally revive one dead player (only while a real fight is going).
    if dead and len(alive) >= 2 and rng.random() < cfg.revive_chance:
        revived = rng.choice(dead)
        revived.alive = True
        events.append(ReviveEvent(revived.user_id))

    alive = [p for p in players if p.alive]
    # Deaths this round: ~death_fraction of the living (with some jitter),
    # capped, always >= 1 and never everyone.
    base = len(alive) * cfg.death_fraction
    n_deaths = max(1, round(base * rng.uniform(0.7, 1.3)))
    n_deaths = min(n_deaths, cfg.deaths_cap, len(alive) - 1)

    for _ in range(n_deaths):
        current = [p for p in players if p.alive]
        if len(current) <= 1:
            break

        if rng.random() < cfg.accident_chance:
            victim = rng.choice(current)
            victim.alive = False
            events.append(AccidentEvent(victim.user_id))
            continue

        victim = rng.choice(current)
        killer = rng.choice([p for p in current if p is not victim])
        others = [p for p in current if p is not victim and p is not killer]

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

    # Harmless flavor events for survivors (skip when the game is over).
    survivors = [p for p in players if p.alive]
    if len(survivors) >= 2 and cfg.flavor_max > 0:
        n_flavor = min(len(survivors), rng.randint(1, cfg.flavor_max))
        for p in rng.sample(survivors, n_flavor):
            events.append(FlavorEvent(p.user_id))

    rng.shuffle(events)
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
