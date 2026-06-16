@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM === Вставь сюда токен от @BotFather (между кавычек не нужно) ===
set BOT_TOKEN=ВСТАВЬ_ТОКЕН_СЮДА

echo Проверяю зависимости...
pip install -r requirements.txt

echo.
echo Запускаю бота. Чтобы остановить — нажми Ctrl+C или просто закрой окно.
echo.
python bot.py

pause
