import discord
from discord.ext import commands
from discord import app_commands
from config import ROLE_DISCIPLINE_MOD, ROLE_DISCIPLINE_VIEW, ADMIN_ROLE
from utils.database import add_discipline
import logging

logger = logging.getLogger(__name__)

class DisciplineModal(discord.ui.Modal, title="Новое дисциплинарное взыскание"):
    user = discord.ui.TextInput(label="ID пользователя", required=True)
    type = discord.ui.TextInput(label="Тип (выговор/предупреждение и т.д.)", required=True)
    reason = discord.ui.TextInput(label="Причина", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, proof_url: str):
        super().__init__()
        self.proof_url = proof_url

    async def on_submit(self, interaction: discord.Interaction):
        if not any(role.id in (ROLE_DISCIPLINE_MOD, ROLE_DISCIPLINE_VIEW) for role in interaction.user.roles) and not any(role.id == ADMIN_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        try:
            target_id = int(self.user.value)
        except ValueError:
            await interaction.response.send_message("❌ ID должен быть числом.", ephemeral=True)
            return
        add_discipline(target_id, self.type.value, self.reason.value, self.proof_url, interaction.user.id)
        await interaction.response.send_message(f"✅ Взыскание для <@{target_id}> оформлено.", ephemeral=True)
        logger.info(f"{interaction.user} выдал взыскание {target_id}")

class RemoveDisciplineModal(discord.ui.Modal, title="Снятие взыскания"):
    user = discord.ui.TextInput(label="ID пользователя", required=True)
    reason = discord.ui.TextInput(label="Причина снятия", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, proof_url: str):
        super().__init__()
        self.proof_url = proof_url

    async def on_submit(self, interaction: discord.Interaction):
        if not any(role.id in (ROLE_DISCIPLINE_MOD, ROLE_DISCIPLINE_VIEW) for role in interaction.user.roles) and not any(role.id == ADMIN_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        try:
            target_id = int(self.user.value)
        except ValueError:
            await interaction.response.send_message("❌ ID должен быть числом.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ Взыскание с <@{target_id}> снято. Причина: {self.reason.value}", ephemeral=True)
        logger.info(f"{interaction.user} снял взыскание с {target_id}")

class DisciplineCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="дв", description="Выдать взыскание (обязателен скриншот)")
    async def issue_discipline(self, interaction: discord.Interaction, attachment: discord.Attachment):
        if not any(role.id in (ROLE_DISCIPLINE_MOD, ROLE_DISCIPLINE_VIEW) for role in interaction.user.roles) and not any(role.id == ADMIN_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        proof_url = attachment.url
        await interaction.response.send_modal(DisciplineModal(proof_url))

    @app_commands.command(name="снятьдв", description="Снять взыскание (обязателен скриншот)")
    async def remove_discipline(self, interaction: discord.Interaction, attachment: discord.Attachment):
        if not any(role.id in (ROLE_DISCIPLINE_MOD, ROLE_DISCIPLINE_VIEW) for role in interaction.user.roles) and not any(role.id == ADMIN_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        proof_url = attachment.url
        await interaction.response.send_modal(RemoveDisciplineModal(proof_url))

async def setup(bot: commands.Bot):
    await bot.add_cog(DisciplineCog(bot))
