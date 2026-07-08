import discord
from discord.ext import commands
from discord import app_commands
from config import ROLE_FAMILY, ROLE_AUTO_MOD, ROLE_AUTO_VIEW
from utils.database import add_auto, remove_auto, get_auto, get_all_autos
import logging

logger = logging.getLogger(__name__)

class AutosCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def has_role(self, interaction: discord.Interaction, role_id: int) -> bool:
        return any(role.id == role_id for role in interaction.user.roles)

    @app_commands.command(name="давто", description="Добавить авто (модель, госномер)")
    async def add_auto(self, interaction: discord.Interaction, model: str, plate: str):
        if not (self.has_role(interaction, ROLE_AUTO_MOD) or self.has_role(interaction, ROLE_AUTO_VIEW) or self.has_role(interaction, ROLE_FAMILY)):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if get_auto(plate):
            await interaction.response.send_message("❌ Авто с таким номером уже есть.", ephemeral=True)
            return
        add_auto(plate, model, interaction.user.id)
        await interaction.response.send_message(f"✅ Авто {model} (госномер {plate}) добавлено.")
        logger.info(f"{interaction.user} добавил авто {plate}")

    @app_commands.command(name="уавто", description="Удалить авто по госномеру")
    async def remove_auto(self, interaction: discord.Interaction, plate: str):
        if not (self.has_role(interaction, ROLE_AUTO_MOD) or self.has_role(interaction, ROLE_AUTO_VIEW) or self.has_role(interaction, ROLE_FAMILY)):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if not get_auto(plate):
            await interaction.response.send_message("❌ Авто с таким номером не найдено.", ephemeral=True)
            return
        remove_auto(plate)
        await interaction.response.send_message(f"✅ Авто с госномером {plate} удалено.")
        logger.info(f"{interaction.user} удалил авто {plate}")

    @app_commands.command(name="авто", description="Список всех авто")
    async def list_autos(self, interaction: discord.Interaction):
        if not (self.has_role(interaction, ROLE_AUTO_MOD) or self.has_role(interaction, ROLE_AUTO_VIEW) or self.has_role(interaction, ROLE_FAMILY)):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        autos = get_all_autos()
        if not autos:
            await interaction.response.send_message("🚗 Авто нет.")
            return
        embed = discord.Embed(title="🚗 Список авто", color=discord.Color.blue())
        for plate, model, owner_id in autos:
            embed.add_field(name=model, value=f"Номер: {plate}\nВладелец: <@{owner_id}>", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="взавто", description="Выдать авто на часы (номер, часы)")
    async def rent_auto(self, interaction: discord.Interaction, plate: str, hours: int):
        if not self.has_role(interaction, ROLE_FAMILY):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if hours <= 0:
            await interaction.response.send_message("❌ Часы должны быть положительным числом.", ephemeral=True)
            return
        auto = get_auto(plate)
        if not auto:
            await interaction.response.send_message("❌ Авто не найдено.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ Авто {auto[1]} (госномер {plate}) выдано на {hours} час(ов) пользователю {interaction.user.mention}.")
        logger.info(f"{interaction.user} выдал авто {plate} на {hours} ч.")

    @app_commands.command(name="веавто", description="Вернуть авто (номер)")
    async def return_auto(self, interaction: discord.Interaction, plate: str):
        if not self.has_role(interaction, ROLE_FAMILY):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        auto = get_auto(plate)
        if not auto:
            await interaction.response.send_message("❌ Авто не найдено.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ Авто {auto[1]} (госномер {plate}) возвращено.")
        logger.info(f"{interaction.user} вернул авто {plate}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AutosCog(bot))
