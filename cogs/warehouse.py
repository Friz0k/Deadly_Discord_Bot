import discord
from discord.ext import commands
from discord import app_commands
from config import ROLE_FAMILY
from utils.database import get_warehouse_item, set_warehouse_item, get_all_warehouse
import logging

logger = logging.getLogger(__name__)

class WarehouseCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def has_role(self, interaction: discord.Interaction):
        return any(role.id == ROLE_FAMILY for role in interaction.user.roles)

    @app_commands.command(name="склад", description="Показать склад по категории")
    async def warehouse(self, interaction: discord.Interaction, category: str = None):
        if not self.has_role(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        items = get_all_warehouse()
        if not items:
            await interaction.response.send_message("📦 Склад пуст.")
            return
        embed = discord.Embed(title="📦 Склад", color=discord.Color.gold())
        if category:
            filtered = [it for it in items if it[0].lower() == category.lower()]
            if not filtered:
                await interaction.response.send_message(f"❌ Категория '{category}' не найдена.")
                return
            for cat, item, qty in filtered:
                embed.add_field(name=item, value=f"{qty} шт.", inline=True)
        else:
            for cat, item, qty in items:
                embed.add_field(name=f"{cat} - {item}", value=f"{qty} шт.", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="псклад", description="Пополнить склад (предмет, категория, кол-во)")
    async def add_warehouse(self, interaction: discord.Interaction, item: str, category: str, quantity: int):
        if not self.has_role(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if quantity <= 0:
            await interaction.response.send_message("❌ Кол-во должно быть положительным.", ephemeral=True)
            return
        current = get_warehouse_item(category, item)
        new_qty = current + quantity
        set_warehouse_item(category, item, new_qty)
        await interaction.response.send_message(f"✅ {item} в категории {category} пополнен на {quantity} шт. (теперь {new_qty})")
        logger.info(f"{interaction.user} добавил {quantity} {item} в {category}")

    @app_commands.command(name="всклад", description="Выдать со склада (предмет, кол-во)")
    async def remove_warehouse(self, interaction: discord.Interaction, item: str, quantity: int):
        if not self.has_role(interaction):
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return
        if quantity <= 0:
            await interaction.response.send_message("❌ Кол-во должно быть положительным.", ephemeral=True)
            return
        categories = get_all_warehouse()
        found = None
        for cat, it, qty in categories:
            if it.lower() == item.lower():
                found = (cat, qty)
                break
        if not found:
            await interaction.response.send_message(f"❌ Предмет {item} не найден на складе.")
            return
        cat, current = found
        if current < quantity:
            await interaction.response.send_message(f"❌ Недостаточно {item} на складе (есть {current})")
            return
        new_qty = current - quantity
        set_warehouse_item(cat, item, new_qty)
        await interaction.response.send_message(f"✅ {item} выдано {quantity} шт. (осталось {new_qty})")
        logger.info(f"{interaction.user} выдал {quantity} {item} со склада")

async def setup(bot: commands.Bot):
    await bot.add_cog(WarehouseCog(bot))
