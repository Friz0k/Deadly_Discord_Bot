import discord
from discord.ext import commands
from discord import app_commands

class RulesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="правила", description="Показать правила сервера")
    async def rules(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📜 Правила сервера",
            description="1. Не нарушать\n2. Уважать других\n3. Следовать указаниям администрации",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(RulesCog(bot))
