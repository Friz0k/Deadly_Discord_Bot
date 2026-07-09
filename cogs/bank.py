import discord
from discord.ext import commands
from discord import app_commands
from config import ROLE_FAMILY, ROLE_BANK_OWNER, ROLE_BANK_MANAGER, ADMIN_ROLE
from utils.database import get_balance, set_balance, add_transaction
import logging

logger = logging.getLogger(__name__)

class BankCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def has_permission(self, interaction: discord.Interaction, *role_ids) -> bool:
        return any(role.id in role_ids for role in interaction.user.roles) or any(role.id == ADMIN_ROLE for role in interaction.user.roles)

    @app_commands.command(name="банк", description="Проверить свой баланс")
    async def bank(self, interaction: discord.Interaction):
        if not self.has_permission(interaction, ROLE_FAMILY):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        bal = get_balance(interaction.user.id)
        await interaction.response.send_message(f"💰 Ваш баланс: {bal}")

    @app_commands.command(name="пополнить", description="Пополнить баланс (обязателен скриншот)")
    async def topup(self, interaction: discord.Interaction, amount: int, reason: str, attachment: discord.Attachment):
        if not self.has_permission(interaction, ROLE_FAMILY):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ Сумма должна быть положительной.", ephemeral=True)
            return
        proof_url = attachment.url
        user_id = interaction.user.id
        current = get_balance(user_id)
        new_balance = current + amount
        set_balance(user_id, new_balance)
        add_transaction(user_id, amount, reason, proof_url)
        await interaction.response.send_message(f"✅ Баланс пополнен на {amount}. Текущий баланс: {new_balance}", ephemeral=True)
        logger.info(f"{interaction.user} пополнил баланс на {amount} (причина: {reason})")

    @app_commands.command(name="снять", description="Снять с баланса (только для владельцев/менеджеров)")
    async def withdraw(self, interaction: discord.Interaction, user: discord.User, amount: int, reason: str = None):
        if not self.has_permission(interaction, ROLE_BANK_OWNER, ROLE_BANK_MANAGER):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ Сумма должна быть положительной.", ephemeral=True)
            return
        current = get_balance(user.id)
        if current < amount:
            await interaction.response.send_message(f"❌ У пользователя {user.mention} недостаточно средств (есть {current})", ephemeral=True)
            return
        new_balance = current - amount
        set_balance(user.id, new_balance)
        add_transaction(user.id, -amount, reason or "Снятие", "")
        await interaction.response.send_message(f"✅ Снято {amount} с {user.mention}. Новый баланс: {new_balance}", ephemeral=True)
        logger.info(f"{interaction.user} снял {amount} у {user}")

async def setup(bot: commands.Bot):
    await bot.add_cog(BankCog(bot))
