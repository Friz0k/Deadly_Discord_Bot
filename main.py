import discord
from discord.ext import commands
import asyncio
import config
from flask import Flask
import threading
import logging
import sys
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Бот работает!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f"✅ Бот {bot.user} запущен!")
    try:
        logger.info("Очищаем старые команды...")
        bot.tree.clear_commands(guild=None)
        for guild in bot.guilds:
            bot.tree.clear_commands(guild=guild)
        await asyncio.sleep(1)
        synced = await bot.tree.sync()
        logger.info(f"Синхронизировано {len(synced)} слеш-команд")
        if synced:
            cmd_names = [cmd.name for cmd in synced]
            logger.info(f"Активные команды: {', '.join(cmd_names)}")
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")

async def load_extensions():
    extensions = [
        "cogs.wiki",
        "cogs.rules",
        "cogs.family",
        "cogs.autos",
        "cogs.warehouse",
        "cogs.bank",
        "cogs.contracts",
        "cogs.discipline",
        "cogs.logs",
        "cogs.backup"
    ]
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            logger.info(f"✅ Загружен {ext}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки {ext}: {e}")
            traceback.print_exc()

async def main():
    logger.info("Начинаем загрузку расширений...")
    await load_extensions()
    logger.info("Все расширения загружены, запускаем бота...")
    try:
        await bot.start(config.TOKEN)
    except discord.LoginFailure as e:
        logger.error(f"Ошибка логина: {e} – проверь токен")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    if not config.TOKEN:
        logger.error("❌ Токен не найден! Установи переменную окружения TOKEN")
        sys.exit(1)

    logger.info("Запускаем Flask...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask запущен, запускаем бота...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        traceback.print_exc()
