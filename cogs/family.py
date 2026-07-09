import discord
from discord.ext import commands, tasks
from discord import app_commands
from config import ROLE_FAMILY, ADMIN_ROLE
from utils.database import add_family_member, get_family_members

class FamilyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sync_task_started = False

    def has_permission(self, interaction: discord.Interaction) -> bool:
        return any(role.id == ADMIN_ROLE for role in interaction.user.roles)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.sync_task_started:
            self.sync_family_nicknames.start()
            self.sync_task_started = True

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles:
            if any(role.id == ROLE_FAMILY for role in after.roles) and not any(role.id == ROLE_FAMILY for role in before.roles):
                add_family_member(after.id, after.display_name)

    def cog_unload(self):
        self.sync_family_nicknames.cancel()

    @tasks.loop(minutes=10)
    async def sync_family_nicknames(self):
        if not self.bot.guilds:
            return
        guild = self.bot.guilds[0]
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

        lines = []
        for user_id, nick in members:
            lines.append(f"{nick} (<@{user_id}>)")

        chunk_size = 20
        chunks = [lines[i:i+chunk_size] for i in range(0, len(lines), chunk_size)]

        if len(chunks) == 1:
            embed = discord.Embed(
                title="👨‍👩‍👧‍👦 Семья",
                description="\n".join(chunks[0]),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.defer()
            for i, chunk in enumerate(chunks, start=1):
                embed = discord.Embed(
                    title=f"👨‍👩‍👧‍👦 Семья (часть {i}/{len(chunks)})",
                    description="\n".join(chunk),
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            await interaction.followup.send(f"✅ Всего {len(members)} участников.")

async def setup(bot: commands.Bot):
    await bot.add_cog(FamilyCog(bot))
