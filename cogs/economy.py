import discord
from discord.ext import commands
from discord import app_commands
from utils.database import get_balance, set_balance

class TopUpModal(discord.ui.Modal, title="Пополнение баланса"):
    amount = discord.ui.TextInput(label="Сумма", placeholder="Введите число", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Введите положительное число.", ephemeral=True)
            return

        user_id = interaction.user.id
        current = get_balance(user_id)
        new_balance = current + amount
        set_balance(user_id, new_balance)

        await interaction.response.send_message(f"✅ Баланс пополнен на {amount}. Текущий баланс: {new_balance}", ephemeral=True)

class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="пополнить", description="Пополнить свой баланс")
    async def topup(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TopUpModal())

    @app_commands.command(name="баланс", description="Проверить свой баланс")
    async def balance(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        bal = get_balance(user_id)
        await interaction.response.send_message(f"💰 Ваш баланс: {bal}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
