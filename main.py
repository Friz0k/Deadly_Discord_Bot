import discord
from discord.ext import commands
import asyncio
import config
from flask import Flask
import threading
import logging
import sys

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
        synced = await bot.tree.sync()
        logger.info(f"Синхронизировано {len(synced)} слеш-команд")
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")

async def load_extensions():
    await bot.load_extension("cogs.wiki")
    await bot.load_extension("cogs.rules")
    await bot.load_extension("cogs.family")
    await bot.load_extension("cogs.autos")
    await bot.load_extension("cogs.warehouse")
    await bot.load_extension("cogs.bank")
    await bot.load_extension("cogs.contracts")
    await bot.load_extension("cogs.discipline")
    await bot.load_extension("cogs.logs")
    await bot.load_extension("cogs.backup")

async def main():
    await load_extensions()
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    if not config.TOKEN:
        logger.error("❌ Токен не найден! Установи переменную окружения TOKEN")
        sys.exit(1)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
