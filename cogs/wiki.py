import discord
from discord.ext import commands
from discord import app_commands
from utils.api import search_wiki

class WikiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="вики", description="Найти статью на вики")
    async def wiki(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        results = await search_wiki(query)
        if not results:
            await interaction.followup.send(f"❌ Ничего не найдено по запросу **{query}**")
            return
        title, desc, url = results[0]
        embed = discord.Embed(title=title, description=desc or "Нет описания", url=url)
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(WikiCog(bot))
