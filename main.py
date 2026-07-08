import discord
from discord.ext import commands
import asyncio
import config

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен!")
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} слеш-команд")
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

async def load_extensions():
    await bot.load_extension("cogs.wiki")
    await bot.load_extension("cogs.rules")
    await bot.load_extension("cogs.penalties")
    await bot.load_extension("cogs.economy")

async def main():
    await load_extensions()
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
