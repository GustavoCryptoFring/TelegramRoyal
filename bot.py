"""Rumble-royale style Telegram bot (aiogram 3).

Flow:
  1. Admin opens a private chat with the bot and sends /start.
  2. Bot lists groups where it is a member AND the user is an admin.
  3. Admin picks a group, then sends the number of minutes for the join phase.
  4. Bot posts an announcement + "Участвовать" button in the group.
  5. When the timer ends, the battle is simulated and narrated round by round.
  6. Final stats are sent to the group and to the admin's private chat.
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (CallbackQuery, ChatMemberUpdated, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import config
import db
import texts
from game import GameConfig, Player, run_game

logging.basicConfig(level=logging.INFO)
router = Router()

PRESENT = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
ADMINS = {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


# --- Game session state (in memory; one active game per chat) ----------------

@dataclass
class Session:
    chat_id: int
    chat_title: str
    admin_id: int
    minutes: int
    message_id: int | None = None
    players: dict[int, Player] = field(default_factory=dict)
    open: bool = True
    task: asyncio.Task | None = None


games: dict[int, Session] = {}


class NewGame(StatesGroup):
    choosing_chat = State()
    entering_minutes = State()


# --- UI text / keyboards -----------------------------------------------------

def welcome_text() -> str:
    return (
        "👋 Привет! Это бот для битвы в стиле <b>Rumble Royale</b>.\n\n"
        "Как запустить игру:\n"
        "1. Добавь меня в свою группу (и желательно сделай админом, чтобы я мог писать).\n"
        "2. Нажми «🎮 Новая игра» ниже.\n"
        "3. Выбери чат и укажи, на сколько минут открыть сбор игроков.\n\n"
        "Я опубликую в чате сообщение с кнопкой «Участвовать», а по таймеру "
        "начнётся бой. Итоги пришлю в чат и тебе в личку."
    )


def kb_newgame() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Новая игра", callback_data="newgame")]
    ])


def join_text(s: Session, finished: bool = False) -> str:
    if s.players:
        plist = "\n".join(f"• {texts.mention(p)}" for p in s.players.values())
    else:
        plist = "<i>Пока никто не присоединился.</i>"
    head = "⚔️ <b>RUMBLE ROYALE</b> ⚔️\n\n"
    if finished:
        status = "🔒 Сбор завершён! Битва начинается...\n\n"
    else:
        status = (f"Жми кнопку ниже, чтобы участвовать!\n\n"
                  f"⏳ Сбор игроков: {s.minutes} мин\n\n")
    return f"{head}{status}👥 Участники ({len(s.players)}):\n{plist}"


def join_kb(s: Session) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⚔️ Участвовать ({len(s.players)})", callback_data="join")],
        [InlineKeyboardButton(text="❌ Отмена (для админов)", callback_data="cancel")],
    ])


# --- Tracking which chats the bot is in --------------------------------------

@router.my_chat_member()
async def on_my_chat_member(ev: ChatMemberUpdated) -> None:
    chat = ev.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    status = ev.new_chat_member.status
    if status in PRESENT:
        db.upsert_chat(config.DB_PATH, chat.id, chat.title or str(chat.id))
        logging.info("Added/updated chat %s (%s)", chat.id, chat.title)
    elif status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
        db.remove_chat(config.DB_PATH, chat.id)
        games.pop(chat.id, None)
        logging.info("Removed chat %s", chat.id)


# --- Admin flow (private chat) -----------------------------------------------

def is_owner(user_id: int) -> bool:
    """Owner-only control. If OWNER_ID is unset (0), the bot is open (so you
    can discover your id on the first /start)."""
    return config.OWNER_ID == 0 or user_id == config.OWNER_ID


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(m: Message, state: FSMContext) -> None:
    if not is_owner(m.from_user.id):
        await m.answer("🔒 Это приватный бот.")
        return
    await state.clear()
    text = welcome_text()
    if config.OWNER_ID == 0:
        text += (f"\n\n🔑 Твой ID: <code>{m.from_user.id}</code>\n"
                 f"Чтобы бот отвечал только тебе, добавь "
                 f"<code>OWNER_ID={m.from_user.id}</code> в файл .env и перезапусти бота.")
    await m.answer(text, reply_markup=kb_newgame())


@router.message(Command("newgame"), F.chat.type == ChatType.PRIVATE)
async def cmd_newgame(m: Message, state: FSMContext, bot: Bot) -> None:
    if not is_owner(m.from_user.id):
        await m.answer("🔒 Это приватный бот.")
        return
    await show_chat_picker(bot, m.from_user.id, m, state)


@router.callback_query(F.data == "newgame", F.message.chat.type == ChatType.PRIVATE)
async def cb_newgame(c: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not is_owner(c.from_user.id):
        await c.answer("🔒 Это приватный бот.", show_alert=True)
        return
    await c.answer()
    await show_chat_picker(bot, c.from_user.id, c.message, state)


async def show_chat_picker(bot: Bot, user_id: int, msg: Message, state: FSMContext) -> None:
    eligible: list[tuple[int, str]] = []
    for chat_id, title in db.list_chats(config.DB_PATH):
        try:
            member = await bot.get_chat_member(chat_id, user_id)
        except TelegramBadRequest:
            db.remove_chat(config.DB_PATH, chat_id)  # bot no longer there
            continue
        if member.status in ADMINS:
            eligible.append((chat_id, title))

    if not eligible:
        await msg.answer(
            "Не нашёл подходящих групп 🤔\n\n"
            "Убедись, что: 1) бот добавлен в группу; 2) ты администратор этой группы. "
            "После этого снова нажми «Новая игра»."
        )
        await state.clear()
        return

    rows = [[InlineKeyboardButton(text=title, callback_data=f"pick:{cid}")]
            for cid, title in eligible]
    await msg.answer("Выбери чат для игры:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await state.set_state(NewGame.choosing_chat)


@router.callback_query(F.data.startswith("pick:"), NewGame.choosing_chat)
async def cb_pick(c: CallbackQuery, state: FSMContext) -> None:
    if not is_owner(c.from_user.id):
        await c.answer("🔒 Это приватный бот.", show_alert=True)
        return
    chat_id = int(c.data.split(":", 1)[1])
    if chat_id in games:
        await c.answer("В этом чате уже идёт игра.", show_alert=True)
        return
    title = db.get_title(config.DB_PATH, chat_id) or str(chat_id)
    await state.update_data(chat_id=chat_id, chat_title=title)
    await state.set_state(NewGame.entering_minutes)
    await c.message.edit_text(
        f"Чат: <b>{texts.esc(title)}</b>\n\n"
        f"На сколько минут открыть сбор игроков? "
        f"Отправь число (1–{config.MAX_MINUTES})."
    )
    await c.answer()


@router.message(NewGame.entering_minutes, F.chat.type == ChatType.PRIVATE)
async def on_minutes(m: Message, state: FSMContext, bot: Bot) -> None:
    if not is_owner(m.from_user.id):
        await m.answer("🔒 Это приватный бот.")
        return
    txt = (m.text or "").strip()
    if not txt.isdigit():
        await m.answer("Нужно целое число минут, например: 5")
        return
    minutes = int(txt)
    if not (1 <= minutes <= config.MAX_MINUTES):
        await m.answer(f"Введи число от 1 до {config.MAX_MINUTES}.")
        return

    data = await state.get_data()
    chat_id, title = data["chat_id"], data["chat_title"]
    await state.clear()

    if chat_id in games:
        await m.answer("В этом чате уже идёт игра.")
        return

    try:
        await launch_game(bot, chat_id, title, m.from_user.id, minutes)
    except TelegramBadRequest as e:
        games.pop(chat_id, None)
        await m.answer(f"Не удалось написать в чат «{texts.esc(title)}». "
                       f"Проверь, что бот там состоит и может отправлять сообщения.\n\n<code>{texts.esc(str(e))}</code>")
        return

    await m.answer(f"✅ Игра запущена в «{texts.esc(title)}». Сбор игроков: {minutes} мин.")


# --- Group interactions ------------------------------------------------------

@router.callback_query(F.data == "join")
async def cb_join(c: CallbackQuery, bot: Bot) -> None:
    s = games.get(c.message.chat.id)
    if not s or not s.open:
        await c.answer("Сейчас присоединиться нельзя.", show_alert=True)
        return
    uid = c.from_user.id
    if uid in s.players:
        await c.answer("Ты уже в игре! ⚔️")
        return
    s.players[uid] = Player(user_id=uid, name=c.from_user.full_name)
    await c.answer("Ты в игре! ⚔️")
    await refresh_join_message(bot, s)


@router.callback_query(F.data == "cancel")
async def cb_cancel(c: CallbackQuery, bot: Bot) -> None:
    s = games.get(c.message.chat.id)
    if not s:
        await c.answer("Активной игры нет.", show_alert=True)
        return
    member = await bot.get_chat_member(s.chat_id, c.from_user.id)
    if c.from_user.id != s.admin_id and member.status not in ADMINS:
        await c.answer("Отменить может только администратор.", show_alert=True)
        return
    await c.answer("Игра отменена.")
    if s.task:
        s.task.cancel()
    games.pop(s.chat_id, None)
    await safe_edit(bot, s.chat_id, s.message_id, "❌ Игра отменена администратором.", None)


# --- Engine wiring -----------------------------------------------------------

async def launch_game(bot: Bot, chat_id: int, title: str, admin_id: int, minutes: int) -> None:
    s = Session(chat_id=chat_id, chat_title=title, admin_id=admin_id, minutes=minutes)
    games[chat_id] = s
    msg = await bot.send_message(chat_id, join_text(s), reply_markup=join_kb(s))
    s.message_id = msg.message_id
    s.task = asyncio.create_task(game_timer(bot, s))


async def game_timer(bot: Bot, s: Session) -> None:
    try:
        await asyncio.sleep(s.minutes * 60)
    except asyncio.CancelledError:
        return

    s.open = False
    if len(s.players) < config.MIN_PLAYERS:
        games.pop(s.chat_id, None)
        await safe_edit(bot, s.chat_id, s.message_id,
                        f"😴 Недостаточно игроков (нужно минимум {config.MIN_PLAYERS}). Игра отменена.", None)
        return

    try:
        await run_and_narrate(bot, s)
    except Exception:
        logging.exception("Game crashed in chat %s", s.chat_id)
    finally:
        games.pop(s.chat_id, None)


async def run_and_narrate(bot: Bot, s: Session) -> None:
    rng = random.Random()
    players = list(s.players.values())
    result = run_game(players, rng, GameConfig())
    by_id = {p.user_id: p for p in players}

    await safe_edit(bot, s.chat_id, s.message_id, join_text(s, finished=True), None)
    await asyncio.sleep(1.5)

    for i, rnd in enumerate(result.rounds, 1):
        lines = [texts.render_event(ev, by_id, rng) for ev in rnd.events]
        body = "\n".join(ln for ln in lines if ln)
        text = f"🩸 <b>Раунд {i}</b> · в живых: {rnd.alive_after}\n\n{body}"
        await send_safe(bot, s.chat_id, text)
        await asyncio.sleep(config.ROUND_DELAY)

    winner = by_id.get(result.winner_id)
    if winner:
        await send_safe(bot, s.chat_id,
                        f"🏆 <b>Победитель:</b> {texts.mention(winner)}!\n\nПоздравляем! 🎉🎉🎉")

    stats = texts.stats_text(players, result)
    await send_safe(bot, s.chat_id, stats)

    # Copy of the stats to the admin's private chat.
    try:
        await bot.send_message(
            s.admin_id,
            f"📊 Итоги игры в «{texts.esc(s.chat_title)}»:\n\n{stats}")
    except TelegramBadRequest:
        pass


# --- Helpers -----------------------------------------------------------------

async def refresh_join_message(bot: Bot, s: Session) -> None:
    try:
        await bot.edit_message_text(join_text(s), chat_id=s.chat_id,
                                    message_id=s.message_id, reply_markup=join_kb(s))
    except (TelegramBadRequest, TelegramRetryAfter):
        pass  # "message not modified" or rate-limited — safe to ignore


async def safe_edit(bot: Bot, chat_id: int, message_id: int | None, text: str, kb) -> None:
    if message_id is None:
        return
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=kb)
    except (TelegramBadRequest, TelegramRetryAfter):
        pass


async def send_safe(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        await bot.send_message(chat_id, text)
    except TelegramBadRequest:
        logging.exception("Failed to send to %s", chat_id)


# --- Entry point -------------------------------------------------------------

async def main() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан. Укажи его в переменной окружения или в .env")
    db.init_db(config.DB_PATH)
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
