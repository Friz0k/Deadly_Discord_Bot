import discord
from discord.ext import commands, tasks
from discord import app_commands
from config import ROLE_FAMILY
from utils.database import add_family_member, get_family_members

class FamilyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sync_family_nicknames.start()

    def cog_unload(self):
        self.sync_family_nicknames.cancel()

    @tasks.loop(minutes=10)
    async def sync_family_nicknames(self):
        guild = self.bot.get_guild(self.bot.guilds[0].id)
        if not guild:
            return
        role = guild.get_role(ROLE_FAMILY)
        if not role:
            return
        for member in role.members:
            add_family_member(member.id, member.display_name)

    @app_commands.command(name="семья", description="Показать список семьи")
    async def family(self, interaction: discord.Interaction):
        members = get_family_members()
        if not members:
            await interaction.response.send_message("❌ В семье пока нет участников.")
            return
        embed = discord.Embed(title="👨‍👩‍👧‍👦 Семья", color=discord.Color.green())
        for user_id, nick in members:
            embed.add_field(name=nick, value=f"<@{user_id}>", inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(FamilyCog(bot))
