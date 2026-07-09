import discord
from discord.ext import commands
from discord import app_commands
from config import ROLE_FAMILY, ROLE_CONTRACT_MANAGER, CHANNEL_CONTRACT_START, ADMIN_ROLE
from utils.database import add_contract, update_contract_status
import logging

logger = logging.getLogger(__name__)

class ContractModal(discord.ui.Modal, title="Новый контракт"):
    name = discord.ui.TextInput(label="Название контракта", required=True)
    participants = discord.ui.TextInput(label="ID участников (через запятую)", required=True, style=discord.TextStyle.paragraph)
    amount = discord.ui.TextInput(label="Кол-во векселей", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Укажите число больше 0.", ephemeral=True)
            return
        contract_id = add_contract(self.name.value, self.participants.value, amount, interaction.user.id)
        embed = discord.Embed(
            title=f"📝 Контракт «{self.name.value}»",
            description=f"**Участники (ID):**\n{self.participants.value}\n\n**Кол-во векселей:** {amount}\n\nID: {contract_id} | Поставьте ✅ для старта",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Создал: {interaction.user}")
        view = ContractStartView(contract_id, self.participants.value)
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"{interaction.user} создал контракт {contract_id}")

class ContractStartView(discord.ui.View):
    def __init__(self, contract_id: int, participants: str):
        super().__init__(timeout=None)
        self.contract_id = contract_id
        self.participants = participants

    @discord.ui.button(label="✅", style=discord.ButtonStyle.success, custom_id="start_contract")
    async def start_contract(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == ROLE_CONTRACT_MANAGER for role in interaction.user.roles) and not any(role.id == ADMIN_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("❌ Только управляющий контрактами или админ может начать.", ephemeral=True)
            return
        update_contract_status(self.contract_id, "started")
        channel = interaction.guild.get_channel(CHANNEL_CONTRACT_START)
        if channel:
            ids = [id.strip() for id in self.participants.split(',') if id.strip().isdigit()]
            mentions = ' '.join([f'<@{uid}>' for uid in ids])
            if mentions:
                content = f"⚠️ Уважаемые {mentions}, ваш контракт начал выполняться!"
            else:
                content = f"⚠️ Уважаемые участники, ваш контракт начал выполняться!"
            await channel.send(content, allowed_mentions=discord.AllowedMentions.all())
        await interaction.response.send_message("✅ Контракт запущен!")
        logger.info(f"{interaction.user} запустил контракт {self.contract_id}")

class ContractsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="вк", description="Создать контракт (через форму)")
    async def create_contract(self, interaction: discord.Interaction):
        if not any(role.id == ROLE_FAMILY for role in interaction.user.roles) and not any(role.id == ADMIN_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        await interaction.response.send_modal(ContractModal())

async def setup(bot: commands.Bot):
    await bot.add_cog(ContractsCog(bot))
