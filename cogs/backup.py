import discord
from discord.ext import commands
from discord import app_commands
from config import ROLE_BACKUP
from utils.database import DB_PATH
import shutil
import os
import logging

logger = logging.getLogger(__name__)

class BackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def has_role(self, interaction: discord.Interaction) -> bool:
        return any(role.id == ROLE_BACKUP for role in interaction.user.roles)

    @app_commands.command(name="backup", description="Выгрузить бэкап базы данных")
    async def backup(self, interaction: discord.Interaction):
        if not self.has_role(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if not DB_PATH.exists():
            await interaction.response.send_message("❌ База данных не найдена.", ephemeral=True)
            return
        backup_path = DB_PATH.parent / "backup_data.db"
        shutil.copy(DB_PATH, backup_path)
        await interaction.response.send_message("✅ Бэкап создан.", ephemeral=True)
        logger.info(f"{interaction.user} создал бэкап")

    @app_commands.command(name="restore", description="Восстановить базу данных из бэкапа")
    async def restore(self, interaction: discord.Interaction):
        if not self.has_role(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        backup_path = DB_PATH.parent / "backup_data.db"
        if not backup_path.exists():
            await interaction.response.send_message("❌ Бэкап не найден.", ephemeral=True)
            return
        shutil.copy(backup_path, DB_PATH)
        await interaction.response.send_message("✅ База данных восстановлена из бэкапа.", ephemeral=True)
        logger.info(f"{interaction.user} восстановил БД")

async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
