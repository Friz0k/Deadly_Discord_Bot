import discord
from discord.ext import commands
from discord import app_commands
from config import ROLE_BACKUP, ADMIN_ROLE
from utils.database import DB_PATH
import shutil
import os
import logging

logger = logging.getLogger(__name__)

class BackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def has_permission(self, interaction: discord.Interaction) -> bool:
        return any(role.id == ROLE_BACKUP for role in interaction.user.roles) or any(role.id == ADMIN_ROLE for role in interaction.user.roles)

    @app_commands.command(name="backup", description="Выгрузить бэкап базы данных (отправляет в личку)")
    async def backup(self, interaction: discord.Interaction):
        if not self.has_permission(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if not DB_PATH.exists():
            await interaction.response.send_message("❌ База данных не найдена.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        backup_path = DB_PATH.parent / "backup_data.db"
        shutil.copy(DB_PATH, backup_path)

        try:
            await interaction.user.send(file=discord.File(backup_path))
            await interaction.followup.send(f"✅ {interaction.user.mention} бэкап создан и отправлен в личные сообщения.", ephemeral=True)
            logger.info(f"{interaction.user} создал и отправил бэкап в DM")
        except discord.Forbidden:
            await interaction.followup.send("❌ Не удалось отправить файл в личные сообщения. Проверьте настройки приватности.", ephemeral=True)
            logger.warning(f"Не удалось отправить бэкап в DM для {interaction.user}")
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка при отправке: {e}", ephemeral=True)
            logger.error(f"Ошибка отправки бэкапа: {e}")

        try:
            os.remove(backup_path)
        except:
            pass

    @app_commands.command(name="restore", description="Восстановить базу из загруженного файла бэкапа")
    async def restore(self, interaction: discord.Interaction, file: discord.Attachment):
        if not self.has_permission(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if not file.filename.endswith('.db'):
            await interaction.response.send_message("❌ Загрузите файл с расширением .db", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        backup_path = DB_PATH.parent / "restore_temp.db"
        await file.save(backup_path)
        shutil.copy(backup_path, DB_PATH)
        os.remove(backup_path)
        await interaction.followup.send(f"✅ {interaction.user.mention} восстановил базу данных из файла {file.filename}.", ephemeral=True)
        logger.info(f"{interaction.user} восстановил БД из файла {file.filename}")

async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
