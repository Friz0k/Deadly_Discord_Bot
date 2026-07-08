import discord
from discord.ext import commands
from discord import app_commands
from config import ROLE_MODERATOR, CHANNEL_LOGS
from utils.database import add_penalty

class PenaltyModal(discord.ui.Modal, title="Выдача выговора"):
    user = discord.ui.TextInput(label="ID пользователя", placeholder="Введите числовой ID", required=True)
    reason = discord.ui.TextInput(label="Причина", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, proof_url: str):
        super().__init__()
        self.proof_url = proof_url

    async def on_submit(self, interaction: discord.Interaction):
        if not any(role.id == ROLE_MODERATOR for role in interaction.user.roles):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        try:
            target_id = int(self.user.value)
        except ValueError:
            await interaction.response.send_message("❌ ID должен быть числом.", ephemeral=True)
            return

        add_penalty(target_id, self.reason.value, self.proof_url, interaction.user.id)

        log_channel = interaction.guild.get_channel(CHANNEL_LOGS)
        if log_channel:
            embed = discord.Embed(
                title="📌 Выговор",
                description=f"**Пользователь:** <@{target_id}>\n**Причина:** {self.reason.value}",
                color=discord.Color.red()
            )
            embed.set_image(url=self.proof_url)
            embed.set_footer(text=f"Выдал: {interaction.user}")
            await log_channel.send(embed=embed)

        await interaction.response.send_message(f"✅ Выговор для <@{target_id}> оформлен.", ephemeral=True)

class PenaltiesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="выговор", description="Выдать выговор (фото обязательно)")
    async def penalty(self, interaction: discord.Interaction):
        if not any(role.id == ROLE_MODERATOR for role in interaction.user.roles):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if not interaction.attachments:
            await interaction.response.send_message("❌ Прикрепите фото к команде.", ephemeral=True)
            return
        proof_url = interaction.attachments[0].url
        await interaction.response.send_modal(PenaltyModal(proof_url))

async def setup(bot: commands.Bot):
    await bot.add_cog(PenaltiesCog(bot))
