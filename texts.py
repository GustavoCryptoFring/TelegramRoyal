"""English text: kill/accident/revive/flavor phrase pools + rendering.

A player is only "tagged" (clickable mention that pings them) when they die or
revive. Killers, survivors and flavor lines use plain bold names — no ping.
"""
from __future__ import annotations

import html
import random

from game import (AccidentEvent, DoubleKillEvent, FlavorEvent, GameResult,
                  KillEvent, Player, ReviveEvent)


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
    "💀 {killer} simply had faster fingers than {victim}.",
    "🌊 {killer} throws {victim} right off a cliff.",
    "😱 {killer} takes out {victim} in a truly shocking way.",
    "🔪 {killer} backstabs {victim} in their sleep.",
    "🍽 {killer} finishes off {victim} and doesn't look back.",
    "🦴 {killer} bludgeons {victim} with someone else's severed leg.",
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
    "🧗 {victim} speedily adventures down a cliff.",
    "🐶 {victim} is killed by a surprisingly vicious puppy.",
    "🐴 {victim} tries to ride a wild horse and breaks their neck.",
    "➗ {victim} tries to divide by zero and reality folds in.",
    "🌊 {victim} misjudges the depth of the water and dives in head-first.",
    "🍲 {victim} dies of food poisoning. That's unfortunate.",
]

REVIVE_PHRASES = [
    "✨ {victim} rises from the dead and returns to the fight!",
    "💉 {victim} finds a medkit and miraculously revives.",
    "🧟 {victim} refuses to die and gets back up!",
    "🔆 A flash of light — and {victim} is back in the game!",
    "💪 {victim} is back in the game and ready to rumble!",
]

FLAVOR_PHRASES = [
    "🌷 {p} stops to smell the flowers.",
    "🫐 {p} finds some edible berries.",
    "🎣 {p} finds a lake and sets up camp.",
    "🦌 {p} successfully hunts a deer!",
    "🪤 {p} sets traps for food, but catches nothing.",
    "🌲 {p} has a calm day wandering through the forest.",
    "🎁 {p} receives food and water from a mysterious sponsor.",
    "🧘 {p} meditates under a waterfall.",
    "🗡 {p} sharpens a piece of bone into a blade.",
    "👂 {p} hears footsteps nearby and freezes.",
    "🔥 {p} builds a campfire and keeps watch.",
    "🌳 {p} climbs a tree to scout the area.",
    "💤 {p} takes a nap in a hidden spot.",
    "📦 {p} discovers an abandoned supply crate.",
    "🌧 {p} waits out the rain under a ledge.",
    "🍞 {p} wakes up to find a small package of food beside them.",
]


def render_event(ev, players: dict[int, Player], rng: random.Random) -> str:
    # Only dying/reviving players get a ping (tag); everyone else is plain bold.
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
    if isinstance(ev, FlavorEvent):
        return rng.choice(FLAVOR_PHRASES).format(p=plain(players[ev.player_id]))
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
