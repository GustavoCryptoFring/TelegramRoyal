"""Offline sanity test for the engine + renderer (no Telegram needed)."""
import random
import re

from game import Player, run_game
import texts


def strip_html(t: str) -> str:
    return re.sub(r"<[^>]+>", "", t)


def run_once(n: int, seed: int, verbose: bool = False) -> None:
    players = [Player(user_id=i, name=f"Игрок{i}") for i in range(1, n + 1)]
    rng = random.Random(seed)
    result = run_game(players, rng, None)
    by_id = {p.user_id: p for p in players}

    alive = [p for p in players if p.alive]
    assert len(alive) == 1, f"expected 1 winner, got {len(alive)}"
    assert result.winner_id == alive[0].user_id
    assert result.total_rounds == len(result.rounds)
    # Every round must make progress (>=1 event) and never wipe everyone.
    for rnd in result.rounds:
        assert rnd.alive_after >= 1
        assert len(rnd.events) >= 1
    assert result.rounds[-1].alive_after == 1

    if verbose:
        for i, rnd in enumerate(result.rounds, 1):
            print(f"\n--- Раунд {i} (в живых: {rnd.alive_after}) ---")
            for ev in rnd.events:
                print("  " + strip_html(texts.render_event(ev, by_id, rng)))
        print("\n" + strip_html(texts.stats_text(players, result)))


if __name__ == "__main__":
    # Show one full sample game.
    run_once(12, seed=7, verbose=True)

    # Stress: many sizes/seeds must always terminate with exactly one winner.
    for n in (2, 3, 5, 10, 25, 50, 100):
        for seed in range(40):
            run_once(n, seed)
    print("\n\nВсе проверки пройдены ✅")
