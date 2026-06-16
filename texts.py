"""Russian text: kill/accident/revive phrase pools + rendering helpers.

Phrases use present tense so they stay grammatically clean regardless of the
player's gender. Names are rendered as clickable mentions (HTML parse mode).
"""
from __future__ import annotations

import html
import random

from game import (AccidentEvent, DoubleKillEvent, GameResult, KillEvent,
                  Player, ReviveEvent)


def esc(text: str) -> str:
    return html.escape(text or "")


def mention(p: Player) -> str:
    return f'<a href="tg://user?id={p.user_id}">{esc(p.name)}</a>'


KILL_PHRASES = [
    "⚔️ {killer} вызывает {victim} на дуэль и выходит победителем.",
    "🗡 {killer} подкрадывается сзади и устраняет {victim}.",
    "🏹 Стрела {killer} находит {victim} точно в цель.",
    "💥 {killer} подрывает {victim} гранатой.",
    "🔥 {killer} поджигает укрытие {victim}.",
    "🥊 {killer} отправляет {victim} в нокаут — навсегда.",
    "🪓 {killer} раскалывает щит {victim} и берёт верх.",
    "🧨 {killer} подкладывает {victim} взрывчатку под стул.",
    "🗿 {killer} роняет на {victim} огромный камень.",
    "❄️ {killer} замораживает {victim} и разбивает на осколки.",
    "🐍 {killer} подбрасывает {victim} ядовитую змею.",
    "🌪 {killer} закручивает {victim} в смертельный вихрь.",
    "🍌 {killer} подкидывает банановую кожуру — {victim} не повезло.",
    "⚡️ {killer} призывает молнию на голову {victim}.",
    "🎯 {killer} не оставляет {victim} ни единого шанса.",
    "🦈 {killer} скармливает {victim} голодной акуле.",
    "🛡 {killer} пробивает оборону {victim} и заканчивает бой.",
    "🤺 {killer} переигрывает {victim} в ближнем бою.",
]

DOUBLE_PHRASES = [
    "💣 {killer} одним взрывом устраняет сразу двоих: {victim1} и {victim2}!",
    "🔪 {killer} молниеносно расправляется и с {victim1}, и с {victim2}!",
    "🎯 Двойное попадание! {killer} снимает {victim1} и {victim2} одним выстрелом.",
    "🌀 {killer} устраивает хаос — {victim1} и {victim2} выбывают вместе.",
]

ACCIDENT_PHRASES = [
    "💀 {victim} наступает на собственную мину.",
    "🕳 {victim} проваливается в яму-ловушку.",
    "🍄 {victim} съедает подозрительный гриб и не выживает.",
    "🌋 {victim} оступается у самого края вулкана.",
    "🧊 {victim} проваливается под лёд.",
    "🐝 {victim} тревожит рой диких пчёл.",
    "⚰️ {victim} решает срезать путь через минное поле.",
    "🌩 В {victim} бьёт случайная молния.",
    "🪨 На {victim} сходит лавина.",
    "🤡 {victim} запутывается в собственной ловушке.",
]

REVIVE_PHRASES = [
    "✨ {victim} восстаёт из мёртвых и возвращается в бой!",
    "💉 {victim} находит аптечку и чудом оживает.",
    "🧟 {victim} отказывается умирать и поднимается снова!",
    "🔆 Вспышка света — и {victim} снова в строю!",
]


def render_event(ev, players: dict[int, Player], rng: random.Random) -> str:
    if isinstance(ev, KillEvent):
        return rng.choice(KILL_PHRASES).format(
            killer=mention(players[ev.killer_id]), victim=mention(players[ev.victim_id]))
    if isinstance(ev, DoubleKillEvent):
        return rng.choice(DOUBLE_PHRASES).format(
            killer=mention(players[ev.killer_id]),
            victim1=mention(players[ev.victim1_id]),
            victim2=mention(players[ev.victim2_id]))
    if isinstance(ev, AccidentEvent):
        return rng.choice(ACCIDENT_PHRASES).format(victim=mention(players[ev.victim_id]))
    if isinstance(ev, ReviveEvent):
        return rng.choice(REVIVE_PHRASES).format(victim=mention(players[ev.player_id]))
    return ""


def stats_text(players: list[Player], result: GameResult) -> str:
    ranking = sorted(
        players,
        key=lambda p: (p.user_id != result.winner_id, -p.kills, p.name.lower()),
    )
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, p in enumerate(ranking):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{prefix} {mention(p)} — убийств: {p.kills}")
    header = (
        "📊 <b>Статистика игры</b>\n"
        f"👥 Игроков: {len(players)}\n"
        f"🔁 Раундов: {result.total_rounds}\n\n"
    )
    return header + "\n".join(lines)
