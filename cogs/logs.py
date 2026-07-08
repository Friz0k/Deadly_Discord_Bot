import discord
from discord.ext import commands
from discord import app_commands
from config import ROLE_AUTO_MOD, ROLE_AUTO_VIEW, ROLE_BANK_OWNER, ROLE_BANK_MANAGER
from utils.database import get_user_logs
import logging

logger = logging.getLogger(__name__)

class LogsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def has_role(self, interaction: discord.Interaction) -> bool:
        allowed = [ROLE_AUTO_MOD, ROLE_AUTO_VIEW, ROLE_BANK_OWNER, ROLE_BANK_MANAGER]
        return any(role.id in allowed for role in interaction.user.roles)

    @app_commands.command(name="logs", description="Логи пользователя (за 50 последних)")
    async def logs(self, interaction: discord.Interaction, user: discord.User = None):
        if not self.has_role(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        target = user.id if user else interaction.user.id
        logs = get_user_logs(target, 50)
        if not logs:
            await interaction.response.send_message(f"📋 Нет логов для {user.mention if user else 'вас'}")
            return
        embed = discord.Embed(title=f"📋 Логи для {user.display_name if user else interaction.user.display_name}", color=discord.Color.dark_gray())
        for action, ts in logs:
            embed.add_field(name=ts, value=action, inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(LogsCog(bot))
