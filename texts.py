"""English text: kill/accident/revive phrase pools + rendering helpers.

Phrases use present tense so they read cleanly regardless of the player's
gender. A player is only "tagged" (clickable mention that pings them) when
they die or revive; in all other cases their name is shown in bold without a
ping, to avoid spamming notifications.
"""
from __future__ import annotations

import html
import random

from game import (AccidentEvent, DoubleKillEvent, GameResult, KillEvent,
                  Player, ReviveEvent)


def esc(text: str) -> str:
    return html.escape(text or "")


def tag(p: Player) -> str:
    """Clickable mention — pings the player. Use only for death/revive."""
    return f'<a href="tg://user?id={p.user_id}">{esc(p.name)}</a>'


def plain(p: Player) -> str:
    """Bold name, no ping."""
    return f"<b>{esc(p.name)}</b>"


KILL_PHRASES = [
    "⚔️ {killer} challenges {victim} to a duel and wins.",
    "🗡 {killer} sneaks up and takes out {victim}.",
    "🏹 {killer}'s arrow finds {victim} right on target.",
    "💥 {killer} blows up {victim} with a grenade.",
    "🔥 {killer} sets {victim}'s hideout on fire.",
    "🥊 {killer} knocks out {victim} — for good.",
    "🪓 {killer} splits {victim}'s shield and prevails.",
    "🧨 {killer} plants explosives under {victim}'s chair.",
    "🗿 {killer} drops a giant boulder on {victim}.",
    "❄️ {killer} freezes {victim} and shatters them to pieces.",
    "🐍 {killer} slips a venomous snake to {victim}.",
    "🌪 {killer} sweeps {victim} into a deadly whirlwind.",
    "🍌 {killer} leaves a banana peel — tough luck, {victim}.",
    "⚡️ {killer} calls down lightning on {victim}.",
    "🎯 {killer} leaves {victim} no chance at all.",
    "🦈 {killer} feeds {victim} to a hungry shark.",
    "🛡 {killer} breaks {victim}'s defense and ends the fight.",
    "🤺 {killer} outduels {victim} in close combat.",
]

DOUBLE_PHRASES = [
    "💣 {killer} takes out both {victim1} and {victim2} in one blast!",
    "🔪 {killer} swiftly finishes off both {victim1} and {victim2}!",
    "🎯 Double hit! {killer} drops {victim1} and {victim2} with one shot.",
    "🌀 {killer} causes chaos — {victim1} and {victim2} go down together.",
]

ACCIDENT_PHRASES = [
    "💀 {victim} steps on their own mine.",
    "🕳 {victim} falls into a pit trap.",
    "🍄 {victim} eats a suspicious mushroom and doesn't make it.",
    "🌋 {victim} slips right at the edge of a volcano.",
    "🧊 {victim} falls through the ice.",
    "🐝 {victim} disturbs a swarm of wild bees.",
    "⚰️ {victim} decides to take a shortcut through a minefield.",
    "🌩 A random bolt of lightning strikes {victim}.",
    "🪨 An avalanche buries {victim}.",
    "🤡 {victim} gets caught in their own trap.",
]

REVIVE_PHRASES = [
    "✨ {victim} rises from the dead and returns to the fight!",
    "💉 {victim} finds a medkit and miraculously revives.",
    "🧟 {victim} refuses to die and gets back up!",
    "🔆 A flash of light — and {victim} is back in the game!",
]


def render_event(ev, players: dict[int, Player], rng: random.Random) -> str:
    # Only dying/reviving players get a ping (tag); others are plain bold.
    if isinstance(ev, KillEvent):
        return rng.choice(KILL_PHRASES).format(
            killer=plain(players[ev.killer_id]), victim=tag(players[ev.victim_id]))
    if isinstance(ev, DoubleKillEvent):
        return rng.choice(DOUBLE_PHRASES).format(
            killer=plain(players[ev.killer_id]),
            victim1=tag(players[ev.victim1_id]),
            victim2=tag(players[ev.victim2_id]))
    if isinstance(ev, AccidentEvent):
        return rng.choice(ACCIDENT_PHRASES).format(victim=tag(players[ev.victim_id]))
    if isinstance(ev, ReviveEvent):
        return rng.choice(REVIVE_PHRASES).format(victim=tag(players[ev.player_id]))
    return ""


def stats_text(players: list[Player], result: GameResult) -> str:
    ranking = sorted(
        players,
        key=lambda p: (p.user_id != result.winner_id, -p.kills, p.name.lower()),
    )
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{medals[i]} {plain(p)} — kills: {p.kills}"
             for i, p in enumerate(ranking[:3])]
    header = (
        "📊 <b>Game stats</b>\n"
        f"👥 Players: {len(players)}\n"
        f"🔁 Rounds: {result.total_rounds}\n\n"
        "<b>Top 3:</b>\n"
    )
    return header + "\n".join(lines)
