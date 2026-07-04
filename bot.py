import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button
import sqlite3
import datetime
import io
import os
import re
import random
import json
from better_profanity import profanity
from flask import Flask
from threading import Thread

TOKEN = os.getenv("TOKEN")
DB_PATH = 'gta_rp.db'

BAD_WORDS = [
    "сука", "блядь", "пиздец", "хуй", "пизда", "ебать",
    "гандон", "мудак", "дебил", "идиот", "ублюдок",
    "тварь", "мразь", "отморозок", "урод", "чмо", "лох",
    "шлюха", "курва", "хер", "херня", "мудила", "говно",
    "залупа", "жопа", "срать", "ссать", "пидор", "пидорас",
    "долбоёб", "долбоеб", "член", "членосос", "минет",
    "шлюх", "бля", "пизд", "ебал", "ебаный", "выебок"
]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS server_config (
    guild_id INTEGER PRIMARY KEY,
    admin_role_id INTEGER,
    family_role_id INTEGER,
    contract_role_id INTEGER,
    recruiter_role_id INTEGER,
    dv_role_id INTEGER,
    log_channel_id INTEGER,
    contract_channel_id INTEGER,
    contract_status_channel_id INTEGER,
    discipline_roles TEXT,
    discipline_auto_remove INTEGER DEFAULT 1,
    discipline_remove_days INTEGER DEFAULT 7
)''')

c.execute('''CREATE TABLE IF NOT EXISTS org_roles (
    guild_id INTEGER,
    category TEXT,
    org TEXT,
    sub TEXT,
    role_id INTEGER,
    cc_role_id INTEGER,
    PRIMARY KEY (guild_id, category, org, sub)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS family_members (
    guild_id INTEGER,
    nickname TEXT,
    discord_id INTEGER,
    joined_at TEXT,
    PRIMARY KEY (guild_id, nickname)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    owner_nick TEXT,
    model TEXT,
    plate TEXT,
    status TEXT DEFAULT 'свободен',
    taken_by TEXT,
    taken_at TEXT,
    return_at TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS warehouse (
    guild_id INTEGER,
    item TEXT,
    amount INTEGER CHECK(amount >= 0),
    category TEXT DEFAULT 'Прочее',
    PRIMARY KEY (guild_id, item)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS bank (
    guild_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)''')

c.execute('''CREATE TABLE IF NOT EXISTS disciplinary_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    nickname TEXT,
    discord_id INTEGER,
    action_type TEXT,
    reason TEXT,
    issued_by TEXT,
    date TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    discord_id INTEGER,
    nickname TEXT,
    action TEXT,
    details TEXT,
    timestamp TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    title TEXT,
    participants TEXT,
    due_date TEXT,
    bills INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TEXT,
    status TEXT DEFAULT 'создан',
    message_id INTEGER,
    notified_hours INTEGER DEFAULT 0,
    started_at TEXT
)''')
conn.commit()

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.messages = True
        intents.voice_states = True
        intents.presences = True
        intents.moderation = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        await self.tree.sync()
        print("Глобальные команды синхронизированы.")

bot = MyBot()
games = {}
sessions = {}
org_sessions = {}

def get_config(guild_id):
    c.execute("SELECT * FROM server_config WHERE guild_id=?", (guild_id,))
    row = c.fetchone()
    if not row:
        return None
    keys = ['guild_id','admin_role_id','family_role_id','contract_role_id',
            'recruiter_role_id','dv_role_id','log_channel_id',
            'contract_channel_id','contract_status_channel_id',
            'discipline_roles','discipline_auto_remove','discipline_remove_days']
    return dict(zip(keys, row))

def get_admin_role(guild_id):
    cfg = get_config(guild_id)
    return cfg['admin_role_id'] if cfg else None

def get_family_role(guild_id):
    cfg = get_config(guild_id)
    return cfg['family_role_id'] if cfg else None

def get_contract_role(guild_id):
    cfg = get_config(guild_id)
    return cfg['contract_role_id'] if cfg else None

def get_recruiter_role(guild_id):
    cfg = get_config(guild_id)
    return cfg['recruiter_role_id'] if cfg else None

def get_dv_role(guild_id):
    cfg = get_config(guild_id)
    return cfg['dv_role_id'] if cfg else None

def get_log_channel(guild_id):
    cfg = get_config(guild_id)
    return cfg['log_channel_id'] if cfg else None

def get_contract_channel(guild_id):
    cfg = get_config(guild_id)
    return cfg['contract_channel_id'] if cfg else None

def get_contract_status_channel(guild_id):
    cfg = get_config(guild_id)
    return cfg['contract_status_channel_id'] if cfg else None

def get_discipline_roles(guild_id):
    cfg = get_config(guild_id)
    if cfg and cfg['discipline_roles']:
        return json.loads(cfg['discipline_roles'])
    return {"1":"предупреждение","2":"выговор","warn":"warn"}

def get_discipline_auto_remove(guild_id):
    cfg = get_config(guild_id)
    return cfg['discipline_auto_remove'] if cfg else 1

def get_discipline_remove_days(guild_id):
    cfg = get_config(guild_id)
    return cfg['discipline_remove_days'] if cfg else 7

def get_org_roles(guild_id):
    c.execute("SELECT category, org, sub, role_id, cc_role_id FROM org_roles WHERE guild_id=?", (guild_id,))
    rows = c.fetchall()
    orgs = {}
    for cat, org, sub, role_id, cc_role_id in rows:
        orgs.setdefault(cat, {}).setdefault(org, {})
        if sub:
            orgs[cat][org].setdefault("subs", {})[sub] = {"role_id": role_id, "cc_role_id": cc_role_id}
        else:
            orgs[cat][org]["role_id"] = role_id
            orgs[cat][org]["cc_role_id"] = cc_role_id
    return orgs

async def has_admin(ctx):
    role_id = get_admin_role(ctx.guild.id)
    if role_id is None:
        return ctx.author.guild_permissions.administrator
    return any(role.id == role_id for role in ctx.author.roles)

async def has_recruiter(ctx):
    role_id = get_recruiter_role(ctx.guild.id)
    if role_id is None:
        return False
    return any(role.id == role_id for role in ctx.author.roles)

async def has_dv(ctx):
    role_id = get_dv_role(ctx.guild.id)
    if role_id is None:
        return False
    return any(role.id == role_id for role in ctx.author.roles)

async def has_contract_role(ctx):
    role_id = get_contract_role(ctx.guild.id)
    if role_id is None:
        return False
    return any(role.id == role_id for role in ctx.author.roles)

async def check_admin(interaction):
    role_id = get_admin_role(interaction.guild.id)
    if role_id is None:
        return interaction.user.guild_permissions.administrator
    return any(role.id == role_id for role in interaction.user.roles)

async def check_recruiter(interaction):
    role_id = get_recruiter_role(interaction.guild.id)
    if role_id is None:
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def check_dv(interaction):
    role_id = get_dv_role(interaction.guild.id)
    if role_id is None:
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def check_contract(interaction):
    role_id = get_contract_role(interaction.guild.id)
    if role_id is None:
        return False
    return any(role.id == role_id for role in interaction.user.roles)

def get_family_balance(guild_id):
    c.execute("SELECT balance FROM bank WHERE guild_id=?", (guild_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO bank (guild_id, balance) VALUES (?, 0)", (guild_id,))
        conn.commit()
        return 0
    return row[0]

def get_member_nick(guild_id, user_id):
    c.execute("SELECT nickname FROM family_members WHERE guild_id=? AND discord_id=?", (guild_id, user_id))
    row = c.fetchone()
    return row[0] if row else None

def log_action(guild_id, discord_id, nickname, action, details=""):
    c.execute("INSERT INTO logs (guild_id, discord_id, nickname, action, details, timestamp) VALUES (?,?,?,?,?,?)",
              (guild_id, discord_id, nickname, action, details, datetime.datetime.now().isoformat()))
    conn.commit()

class SetupSession:
    def __init__(self, bot, user_id):
        self.bot = bot
        self.user_id = user_id
        self.step = 0
        self.data = {}
        self.channel = None

    async def start(self, channel):
        self.channel = channel
        await self.ask_guild_id()

    async def ask_guild_id(self):
        await self.channel.send("Укажите ID сервера (включите режим разработчика и скопируйте ID).")
        self.step = 1

    async def handle_message(self, message):
        if message.author.id != self.user_id:
            return
        if self.step == 1:
            try:
                guild_id = int(message.content)
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    await self.channel.send("Сервер не найден. Бот должен быть на сервере.")
                    return
                member = guild.get_member(self.user_id)
                if member is None or not member.guild_permissions.administrator:
                    await self.channel.send("Вы не являетесь администратором на этом сервере.")
                    return
                self.guild_id = guild_id
                self.data['guild_id'] = guild_id
                self.step = 2
                await self.channel.send("Теперь укажите **ID роли администратора бота**.\nЭта роль получит полный доступ к командам.")
            except ValueError:
                await self.channel.send("Неверный формат ID. Попробуйте ещё раз.")

        elif self.step == 2:
            try:
                role_id = int(message.content)
                self.data['admin_role_id'] = role_id
                self.step = 3
                await self.channel.send("Укажите **ID роли семьи** (авто-добавление участников).")
            except ValueError:
                await self.channel.send("Неверный ID. Введите число.")

        elif self.step == 3:
            try:
                role_id = int(message.content)
                self.data['family_role_id'] = role_id
                self.step = 4
                await self.channel.send("Укажите **ID роли рекрутеров** (добавление/удаление из семьи).")
            except ValueError:
                await self.channel.send("Неверный ID. Введите число.")

        elif self.step == 4:
            try:
                role_id = int(message.content)
                self.data['recruiter_role_id'] = role_id
                self.step = 5
                await self.channel.send("Укажите **ID роли для ДВ** (выдача дисциплинарных взысканий).")
            except ValueError:
                await self.channel.send("Неверный ID. Введите число.")

        elif self.step == 5:
            try:
                role_id = int(message.content)
                self.data['dv_role_id'] = role_id
                self.step = 6
                await self.channel.send("Укажите **ID роли, которая может ставить ✅ на контракты**.")
            except ValueError:
                await self.channel.send("Неверный ID. Введите число.")

        elif self.step == 6:
            try:
                role_id = int(message.content)
                self.data['contract_role_id'] = role_id
                self.step = 7
                await self.channel.send("Укажите **ID канала для логов (аудит)**.")
            except ValueError:
                await self.channel.send("Неверный ID. Введите число.")

        elif self.step == 7:
            try:
                channel_id = int(message.content)
                self.data['log_channel_id'] = channel_id
                self.step = 8
                await self.channel.send("Укажите **ID канала для уведомлений о контрактах** (теги участников).")
            except ValueError:
                await self.channel.send("Неверный ID. Введите число.")

        elif self.step == 8:
            try:
                channel_id = int(message.content)
                self.data['contract_channel_id'] = channel_id
                self.step = 9
                await self.channel.send("Укажите **ID канала для статусов контрактов** (создание/завершение).")
            except ValueError:
                await self.channel.send("Неверный ID. Введите число.")

        elif self.step == 9:
            try:
                channel_id = int(message.content)
                self.data['contract_status_channel_id'] = channel_id
                self.step = 10
                await self.channel.send("Настройка завершена! Сохраняем данные...")
                await self.save_config()
                await self.channel.send("✅ Бот успешно настроен для сервера!")
                del sessions[self.user_id]
            except ValueError:
                await self.channel.send("Неверный ID. Введите число.")

    async def save_config(self):
        c.execute('''INSERT OR REPLACE INTO server_config 
            (guild_id, admin_role_id, family_role_id, contract_role_id, recruiter_role_id, dv_role_id,
            log_channel_id, contract_channel_id, contract_status_channel_id)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (self.data['guild_id'], self.data['admin_role_id'], self.data['family_role_id'],
             self.data['contract_role_id'], self.data['recruiter_role_id'], self.data['dv_role_id'],
             self.data['log_channel_id'], self.data['contract_channel_id'], self.data['contract_status_channel_id']))
        conn.commit()

class OrgConfigSession:
    def __init__(self, bot, user_id, guild_id):
        self.bot = bot
        self.user_id = user_id
        self.guild_id = guild_id
        self.state = "category"
        self.categories = ["Госс", "Банды", "Мафии"]
        self.current_category = None
        self.current_org_name = None
        self.org_count = 0
        self.org_names = []
        self.org_index = 0
        self.current_role_id = None
        self.current_cc_role_id = None
        self.sub_count = 0
        self.sub_index = 0
        self.channel = None
        self.pending_org_data = {}

    async def start(self, channel):
        self.channel = channel
        await self.ask_category()

    async def ask_category(self):
        if not self.categories:
            await self.channel.send("🎉 Настройка организаций завершена!")
            del org_sessions[self.user_id]
            return
        self.current_category = self.categories.pop(0)
        self.org_names = []
        self.org_index = 0
        await self.channel.send(f"Настройка категории **{self.current_category}**.\nСколько организаций в ней? Введите число.")
        self.state = "org_count"

    async def handle_message(self, message):
        if message.author.id != self.user_id:
            return
        content = message.content.strip()
        if self.state == "org_count":
            try:
                self.org_count = int(content)
                self.state = "org_name"
                self.org_names = []
                self.org_index = 0
                await self.channel.send("Введите название первой организации.")
            except ValueError:
                await self.channel.send("Введите число.")
        elif self.state == "org_name":
            self.current_org_name = content
            self.state = "org_role"
            await self.channel.send(f"Введите ID роли для **{self.current_org_name}**.")
        elif self.state == "org_role":
            try:
                self.current_role_id = int(content)
                self.state = "org_cc_role"
                await self.channel.send(f"Введите ID CC-роли для **{self.current_org_name}** (или 0, если нет).")
            except ValueError:
                await self.channel.send("Введите число.")
        elif self.state == "org_cc_role":
            try:
                self.current_cc_role_id = int(content)
                self.state = "has_subs"
                await self.channel.send(f"Есть ли у **{self.current_org_name}** подразделения? (да/нет)")
            except ValueError:
                await self.channel.send("Введите число.")
        elif self.state == "has_subs":
            if content.lower() in ("да", "yes", "y"):
                self.state = "sub_count"
                await self.channel.send("Сколько подразделений? Введите число.")
            else:
                await self.save_org()
                self.org_index += 1
                if self.org_index < self.org_count:
                    self.state = "org_name"
                    await self.channel.send("Введите название следующей организации.")
                else:
                    await self.ask_category()
        elif self.state == "sub_count":
            try:
                self.sub_count = int(content)
                self.sub_index = 0
                self.state = "sub_name"
                await self.channel.send("Введите название первого подразделения.")
            except ValueError:
                await self.channel.send("Введите число.")
        elif self.state == "sub_name":
            self.current_sub_name = content
            self.state = "sub_role"
            await self.channel.send(f"Введите ID роли для подразделения **{self.current_sub_name}**.")
        elif self.state == "sub_role":
            try:
                sub_role_id = int(content)
                self.current_sub_role_id = sub_role_id
                self.state = "sub_cc_role"
                await self.channel.send(f"Введите ID CC-роли для подразделения **{self.current_sub_name}** (или 0, если нет).")
            except ValueError:
                await self.channel.send("Введите число.")
        elif self.state == "sub_cc_role":
            try:
                sub_cc_role_id = int(content)
                c.execute("INSERT OR REPLACE INTO org_roles (guild_id, category, org, sub, role_id, cc_role_id) VALUES (?,?,?,?,?,?)",
                          (self.guild_id, self.current_category, self.current_org_name, self.current_sub_name, self.current_sub_role_id, sub_cc_role_id))
                conn.commit()
                self.sub_index += 1
                if self.sub_index < self.sub_count:
                    self.state = "sub_name"
                    await self.channel.send("Введите название следующего подразделения.")
                else:
                    await self.save_org()
                    self.org_index += 1
                    if self.org_index < self.org_count:
                        self.state = "org_name"
                        await self.channel.send("Введите название следующей организации.")
                    else:
                        await self.ask_category()
            except ValueError:
                await self.channel.send("Введите число.")

    async def save_org(self):
        c.execute("INSERT OR REPLACE INTO org_roles (guild_id, category, org, sub, role_id, cc_role_id) VALUES (?,?,?,?,?,?)",
                  (self.guild_id, self.current_category, self.current_org_name, "", self.current_role_id, self.current_cc_role_id))
        conn.commit()

class RoleSelectView(View):
    def __init__(self, user_id, guild_id):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.org_data = get_org_roles(guild_id)
        self.current_category = None
        self.selected_org = None
        self.selected_sub = None
        self.step = "main"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Это не ваше меню!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="⏰ Время выбора истекло.", view=None)

    def build_main_menu(self):
        self.clear_items()
        self.step = "main"
        categories = [cat for cat in self.org_data if self.org_data[cat]]
        if not categories:
            self.add_item(Button(label="Нет настроенных организаций", disabled=True, style=discord.ButtonStyle.secondary))
            return
        options = [discord.SelectOption(label=cat) for cat in categories]
        select = Select(placeholder="Выберите категорию", options=options, custom_id="main_category")
        select.callback = self.category_select
        self.add_item(select)

    async def category_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_category = interaction.data['values'][0]
        orgs = list(self.org_data[self.current_category].keys())
        if not orgs:
            await interaction.followup.send("В этой категории нет организаций.", ephemeral=True)
            self.build_main_menu()
            await interaction.edit_original_response(view=self)
            return
        self.step = "org"
        self.clear_items()
        options = [discord.SelectOption(label=org) for org in orgs]
        select = Select(placeholder=f"Выберите организацию ({self.current_category})", options=options, custom_id="org_select")
        select.callback = self.org_select
        self.add_item(select)
        back_btn = Button(label="Назад", style=discord.ButtonStyle.secondary, custom_id="back_to_main")
        back_btn.callback = self.back_to_main
        self.add_item(back_btn)
        await interaction.edit_original_response(view=self)

    async def org_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.selected_org = interaction.data['values'][0]
        org_info = self.org_data[self.current_category][self.selected_org]
        if "subs" in org_info and org_info["subs"]:
            self.step = "sub"
            self.clear_items()
            subs = list(org_info["subs"].keys())
            options = [discord.SelectOption(label=s) for s in subs]
            select = Select(placeholder="Выберите подразделение", options=options, custom_id="sub_select")
            select.callback = self.sub_select
            self.add_item(select)
            back_btn = Button(label="Назад", style=discord.ButtonStyle.secondary, custom_id="back_to_org")
            back_btn.callback = self.back_to_org
            self.add_item(back_btn)
            await interaction.edit_original_response(view=self)
        else:
            await self.assign_role(interaction, org_info["role_id"], org_info.get("cc_role_id"))

    async def sub_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.selected_sub = interaction.data['values'][0]
        sub_info = self.org_data[self.current_category][self.selected_org]["subs"][self.selected_sub]
        await self.assign_role(interaction, sub_info["role_id"], sub_info.get("cc_role_id"))

    async def assign_role(self, interaction, role_id, cc_role_id=None):
        member = interaction.guild.get_member(self.user_id)
        if not member:
            await interaction.followup.send("Пользователь не найден.", ephemeral=True)
            self.stop()
            return
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.followup.send("Роль не найдена.", ephemeral=True)
            self.stop()
            return
        if role in member.roles:
            await member.remove_roles(role, reason="Самостоятельное снятие")
            action_main = "снята"
        else:
            await member.add_roles(role, reason="Самостоятельный выбор")
            action_main = "выдана"
        cc_msg = ""
        if cc_role_id and cc_role_id != 0:
            cc_role = interaction.guild.get_role(cc_role_id)
            if cc_role:
                if cc_role in member.roles:
                    await member.remove_roles(cc_role, reason="Снятие CC")
                    cc_msg = "; CC снята"
                else:
                    await member.add_roles(cc_role, reason="Выдача CC")
                    cc_msg = "; CC выдана"
        self.clear_items()
        await interaction.followup.send(f"✅ Роль **{role.name}** {action_main}.{cc_msg}", ephemeral=True)
        self.stop()

    async def back_to_main(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.build_main_menu()
        await interaction.edit_original_response(view=self)

    async def back_to_org(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.step = "org"
        self.clear_items()
        orgs = list(self.org_data[self.current_category].keys())
        options = [discord.SelectOption(label=org) for org in orgs]
        select = Select(placeholder=f"Выберите организацию ({self.current_category})", options=options, custom_id="org_select2")
        select.callback = self.org_select
        self.add_item(select)
        back_btn = Button(label="Назад", style=discord.ButtonStyle.secondary, custom_id="back_to_main")
        back_btn.callback = self.back_to_main
        self.add_item(back_btn)
        await interaction.edit_original_response(view=self)

@bot.tree.command(name="роль", description="Выбрать или снять роль организации")
async def role_select(interaction: discord.Interaction):
    view = RoleSelectView(interaction.user.id, interaction.guild.id)
    view.build_main_menu()
    embed = discord.Embed(title="🏢 Выбор роли", description="Сначала выберите категорию, затем организацию. Если у вас уже есть роль, она будет снята.", color=0x2ecc71)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="setup", description="Настроить бота (только в ЛС)")
async def setup(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.DMChannel):
        return await interaction.response.send_message("Эту команду нужно выполнять в личных сообщениях бота.", ephemeral=True)
    if interaction.user.id in sessions:
        return await interaction.response.send_message("У вас уже есть активная сессия настройки.", ephemeral=True)
    session = SetupSession(bot, interaction.user.id)
    await session.start(interaction.channel)
    sessions[interaction.user.id] = session

@bot.tree.command(name="orgconfig", description="Настроить роли организаций (только в ЛС)")
async def orgconfig(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.DMChannel):
        return await interaction.response.send_message("Эту команду нужно выполнять в личных сообщениях бота.", ephemeral=True)
    if interaction.user.id in org_sessions:
        return await interaction.response.send_message("У вас уже есть активная настройка организаций.", ephemeral=True)
    await interaction.response.send_message("Укажите ID сервера для настройки организаций.")
    org_sessions[interaction.user.id] = {"state": "guild_id", "user_id": interaction.user.id}

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.author.id in sessions:
        await sessions[message.author.id].handle_message(message)
        return
    if message.author.id in org_sessions:
        session_data = org_sessions[message.author.id]
        if isinstance(session_data, dict) and session_data["state"] == "guild_id":
            try:
                guild_id = int(message.content)
                guild = bot.get_guild(guild_id)
                if guild is None:
                    await message.channel.send("Сервер не найден.")
                    return
                member = guild.get_member(message.author.id)
                if member is None or not member.guild_permissions.administrator:
                    await message.channel.send("Вы не администратор этого сервера.")
                    return
                session = OrgConfigSession(bot, message.author.id, guild_id)
                await session.start(message.channel)
                org_sessions[message.author.id] = session
            except ValueError:
                await message.channel.send("Неверный ID сервера.")
            return
        elif isinstance(session_data, OrgConfigSession):
            await session_data.handle_message(message)
            return
    content = message.content.lower()
    if message.guild:
        log_id = get_log_channel(message.guild.id)
        if message.channel.id != log_id:
            if profanity.contains_profanity(content):
                await message.delete()
                await message.channel.send(f"{message.author.mention}, ваше сообщение удалено за использование запрещённого слова.", delete_after=10)
                return
            for word in BAD_WORDS:
                if re.search(rf'\b{word}\b', content):
                    await message.delete()
                    await message.channel.send(f"{message.author.mention}, ваше сообщение удалено за использование запрещённого слова.", delete_after=10)
                    return
    await bot.process_commands(message)

@bot.tree.command(name="хелп", description="Помощь по боту")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="✨ Помощь по боту", color=0x9b59b6)
    embed.add_field(name="👥 Семья", value="/дсемья ID Ник\n/усемья ID\n/семья", inline=False)
    embed.add_field(name="🚗 Авто", value="/давто Модель Госномер\n/уавто Госномер\n/авто\n/взавто Номер [часы]\n/веавто Номер", inline=False)
    embed.add_field(name="📦 Склад", value="/склад [Категория]\n/псклад Предмет Категория Кол-во\n/всклад Предмет Кол-во", inline=False)
    embed.add_field(name="💰 Банк", value="/банк\n/пополнить Сумма [Причина] (скриншот обязателен)\n/снять Сумма [Причина]", inline=False)
    embed.add_field(name="📝 Контракты", value="/вк @Участники Название ДД.ММ.ГГГГ ЧЧ:ММ [векселя]", inline=False)
    embed.add_field(name="⚠️ Дисциплина", value="/дв @Участники Тип Причина\n/выг [@Участник]\n/снятьдв @Участник Причина", inline=False)
    embed.add_field(name="📋 Логи", value="/logs [@Участник]", inline=False)
    embed.add_field(name="🛠️ Настройка", value="/setup в ЛС\n/orgconfig в ЛС", inline=False)
    embed.add_field(name="🏢 Роли", value="/роль", inline=False)
    embed.add_field(name="🎮 Игры", value="/игра", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="банк", description="Баланс семьи")
async def bank_balance(interaction: discord.Interaction):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    balance = get_family_balance(interaction.guild.id)
    await interaction.response.send_message(f'💰 Баланс семьи: {balance}')

@bot.tree.command(name="пополнить", description="Пополнить семейный банк (скриншот обязателен)")
async def bank_add(interaction: discord.Interaction, сумма: int, причина: str = "", скриншот: discord.Attachment = None):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    if скриншот is None:
        return await interaction.response.send_message("❌ Необходимо прикрепить скриншот.", ephemeral=True)
    if сумма <= 0:
        return await interaction.response.send_message("❌ Сумма должна быть положительной.", ephemeral=True)
    nick = get_member_nick(interaction.guild.id, interaction.user.id)
    if not nick:
        return await interaction.response.send_message("❌ Вы не привязаны к семье. Используйте /дсемья.", ephemeral=True)
    nick = nick.replace("_", " ")
    c.execute("UPDATE bank SET balance = balance + ? WHERE guild_id=?", (сумма, interaction.guild.id))
    if c.rowcount == 0:
        c.execute("INSERT INTO bank (guild_id, balance) VALUES (?, ?)", (interaction.guild.id, сумма))
    conn.commit()
    new_balance = get_family_balance(interaction.guild.id)
    log_action(interaction.guild.id, interaction.user.id, nick, "Пополнение банка", f"+{сумма}, причина: {причина}")
    file = discord.File(await скриншот.read(), filename=скриншот.filename)
    await interaction.response.send_message(f'💰 Счёт семьи пополнен на {сумма} (от {nick}). Баланс: {new_balance}.', file=file)

@bot.tree.command(name="снять", description="Снять деньги из семейного банка")
async def bank_remove(interaction: discord.Interaction, сумма: int, причина: str = ""):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    if сумма <= 0:
        return await interaction.response.send_message("❌ Сумма должна быть положительной.", ephemeral=True)
    nick = get_member_nick(interaction.guild.id, interaction.user.id)
    if not nick:
        return await interaction.response.send_message("❌ Вы не привязаны к семье. Используйте /дсемья.", ephemeral=True)
    nick = nick.replace("_", " ")
    balance = get_family_balance(interaction.guild.id)
    if balance < сумма:
        return await interaction.response.send_message(f"❌ Недостаточно средств. Баланс: {balance}.", ephemeral=True)
    c.execute("UPDATE bank SET balance = balance - ? WHERE guild_id=?", (сумма, interaction.guild.id))
    conn.commit()
    new_balance = get_family_balance(interaction.guild.id)
    log_action(interaction.guild.id, interaction.user.id, nick, "Снятие с банка", f"-{сумма}, причина: {причина}")
    await interaction.response.send_message(f"💸 Из бюджета семьи снято {сумма} (от {nick}). Баланс: {new_balance}.")

@bot.tree.command(name="дсемья", description="Добавить участника в семью")
async def add_family(interaction: discord.Interaction, discord_id: str, никнейм: str):
    if not await check_admin(interaction) and not await check_recruiter(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    try:
        disc_id = int(discord_id)
    except ValueError:
        return await interaction.response.send_message("❌ Неверный формат ID.", ephemeral=True)
    никнейм = никнейм.replace("_", " ")
    c.execute("SELECT * FROM family_members WHERE guild_id=? AND discord_id=?", (interaction.guild.id, disc_id))
    if c.fetchone():
        return await interaction.response.send_message(f'⚠️ Пользователь с ID `{disc_id}` уже в семье.', ephemeral=True)
    c.execute("SELECT * FROM family_members WHERE guild_id=? AND nickname=?", (interaction.guild.id, никнейм))
    if c.fetchone():
        return await interaction.response.send_message(f'⚠️ Ник `{никнейм}` уже занят.', ephemeral=True)
    c.execute("INSERT INTO family_members (guild_id, nickname, discord_id, joined_at) VALUES (?,?,?,?)",
              (interaction.guild.id, никнейм, disc_id, datetime.datetime.now().isoformat()))
    conn.commit()
    log_action(interaction.guild.id, interaction.user.id, get_member_nick(interaction.guild.id, interaction.user.id) or str(interaction.user),
               "Добавление в семью", f"Добавлен {никнейм} ({disc_id})")
    await interaction.response.send_message(f'✅ <@{disc_id}> (`{никнейм}`) добавлен в семью.', ephemeral=True)

@bot.tree.command(name="усемья", description="Удалить участника из семьи")
async def remove_family(interaction: discord.Interaction, discord_id: str):
    if not await check_admin(interaction) and not await check_recruiter(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    try:
        disc_id = int(discord_id)
    except ValueError:
        return await interaction.response.send_message("❌ Неверный формат ID.", ephemeral=True)
    c.execute("SELECT nickname FROM family_members WHERE guild_id=? AND discord_id=?", (interaction.guild.id, disc_id))
    row = c.fetchone()
    if not row:
        return await interaction.response.send_message(f'❌ Пользователь с ID `{disc_id}` не найден в семье.', ephemeral=True)
    nickname = row[0]
    c.execute("DELETE FROM family_members WHERE guild_id=? AND discord_id=?", (interaction.guild.id, disc_id))
    conn.commit()
    log_action(interaction.guild.id, interaction.user.id, get_member_nick(interaction.guild.id, interaction.user.id) or str(interaction.user),
               "Удаление из семьи", f"Удалён {nickname} ({disc_id})")
    await interaction.response.send_message(f'✅ <@{disc_id}> (`{nickname}`) удалён из семьи.', ephemeral=True)

@bot.tree.command(name="семья", description="Список членов семьи")
async def family_list(interaction: discord.Interaction):
    c.execute("SELECT nickname, discord_id FROM family_members WHERE guild_id=?", (interaction.guild.id,))
    rows = c.fetchall()
    if not rows:
        return await interaction.response.send_message('👪 Семья пуста.', ephemeral=True)
    lines = [f'<@{disc_id}> — `{nick}`' for nick, disc_id in rows]
    embed = discord.Embed(title='👥 Семья', description='\n'.join(lines), color=0x00ff00)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="давто", description="Добавить автомобиль")
async def add_car(interaction: discord.Interaction, модель: str, госномер: str):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    nick = get_member_nick(interaction.guild.id, interaction.user.id)
    if not nick:
        return await interaction.response.send_message('❌ Вы не привязаны к семье. Сначала добавьте себя через /дсемья.', ephemeral=True)
    nick = nick.replace("_", " ")
    try:
        c.execute("INSERT INTO vehicles (guild_id, owner_nick, model, plate) VALUES (?,?,?,?)",
                  (interaction.guild.id, nick, модель, госномер))
        conn.commit()
        car_id = c.lastrowid
        log_action(interaction.guild.id, interaction.user.id, nick, "Добавление авто", f"Модель {модель}, госномер {госномер}")
        await interaction.response.send_message(f'🚗 {модель} ({госномер}) добавлен, номер {car_id}. Владелец: `{nick}`.', ephemeral=True)
    except sqlite3.IntegrityError:
        await interaction.response.send_message(f'❌ Госномер `{госномер}` уже существует.', ephemeral=True)

@bot.tree.command(name="уавто", description="Удалить автомобиль")
async def remove_car(interaction: discord.Interaction, госномер: str):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    c.execute("DELETE FROM vehicles WHERE guild_id=? AND plate=?", (interaction.guild.id, госномер))
    if c.rowcount == 0:
        return await interaction.response.send_message(f'❌ Машина с госномером `{госномер}` не найдена.', ephemeral=True)
    conn.commit()
    log_action(interaction.guild.id, interaction.user.id, get_member_nick(interaction.guild.id, interaction.user.id) or str(interaction.user),
               "Удаление авто", f"Госномер {госномер}")
    await interaction.response.send_message(f'🗑️ Машина `{госномер}` удалена.', ephemeral=True)

@bot.tree.command(name="авто", description="Список автомобилей")
async def car_list(interaction: discord.Interaction):
    c.execute("SELECT id, owner_nick, model, plate, status, taken_by, return_at FROM vehicles WHERE guild_id=?", (interaction.guild.id,))
    cars = c.fetchall()
    if not cars:
        return await interaction.response.send_message('🚫 Нет машин.', ephemeral=True)
    lines = []
    for cid, owner, model, plate, status, taken_by, ret_at in cars:
        if status == 'свободен':
            lines.append(f'`{cid}` {model} ({plate}) — свободен')
        else:
            lines.append(f'`{cid}` {model} ({plate}) — занят {taken_by}, до {ret_at}')
    embed = discord.Embed(title='🚗 Автомобили', description='\n'.join(lines), color=0x3498db)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="взавто", description="Взять автомобиль")
async def take_car(interaction: discord.Interaction, номер: int, часы: float = 2.0):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    nick = get_member_nick(interaction.guild.id, interaction.user.id)
    if not nick:
        return await interaction.response.send_message('❌ Вы не привязаны к семье.', ephemeral=True)
    nick = nick.replace("_", " ")
    c.execute("SELECT status, plate FROM vehicles WHERE guild_id=? AND id=?", (interaction.guild.id, номер))
    car = c.fetchone()
    if not car:
        return await interaction.response.send_message(f'❌ Авто с номером `{номер}` не найдено.', ephemeral=True)
    status, plate = car
    if status != 'свободен':
        return await interaction.response.send_message(f'❌ Авто `{plate}` уже занято.', ephemeral=True)
    now = datetime.datetime.now()
    return_at = now + datetime.timedelta(hours=часы)
    c.execute("UPDATE vehicles SET status='занят', taken_by=?, taken_at=?, return_at=? WHERE guild_id=? AND id=?",
              (nick, now.isoformat(), return_at.isoformat(), interaction.guild.id, номер))
    conn.commit()
    log_action(interaction.guild.id, interaction.user.id, nick, "Взять авто", f"Номер {номер}, на {часы} ч")
    await interaction.response.send_message(f'✅ `{plate}` выдано `{nick}` на {часы} ч до {return_at.strftime("%d.%m.%Y %H:%M")}.', ephemeral=True)

@bot.tree.command(name="веавто", description="Вернуть автомобиль")
async def return_car(interaction: discord.Interaction, номер: int):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    c.execute("SELECT plate, status FROM vehicles WHERE guild_id=? AND id=?", (interaction.guild.id, номер))
    car = c.fetchone()
    if not car:
        return await interaction.response.send_message(f'❌ Авто с номером `{номер}` не найдено.', ephemeral=True)
    plate, status = car
    if status == 'свободен':
        return await interaction.response.send_message(f'❌ Авто `{plate}` уже свободно.', ephemeral=True)
    c.execute("UPDATE vehicles SET status='свободен', taken_by=NULL, taken_at=NULL, return_at=NULL WHERE guild_id=? AND id=?",
              (interaction.guild.id, номер))
    conn.commit()
    log_action(interaction.guild.id, interaction.user.id, get_member_nick(interaction.guild.id, interaction.user.id) or str(interaction.user),
               "Вернуть авто", f"Номер {номер}")
    await interaction.response.send_message(f'✅ Авто `{plate}` возвращено.', ephemeral=True)

@bot.tree.command(name="псклад", description="Положить предмет на склад")
@app_commands.choices(категория=[
    app_commands.Choice(name="Оружие", value="Оружие"),
    app_commands.Choice(name="Патроны", value="Патроны"),
    app_commands.Choice(name="Расходники", value="Расходники"),
    app_commands.Choice(name="Прочее", value="Прочее")
])
async def warehouse_put(interaction: discord.Interaction, предмет: str, категория: str, количество: int):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    nick = get_member_nick(interaction.guild.id, interaction.user.id)
    if not nick:
        return await interaction.response.send_message('❌ Вы не привязаны к семье.', ephemeral=True)
    nick = nick.replace("_", " ")
    if количество <= 0:
        return await interaction.response.send_message('❌ Количество > 0.', ephemeral=True)
    предмет = предмет.replace("_", " ").title()
    c.execute("INSERT INTO warehouse (guild_id, item, category, amount) VALUES (?,?,?,?) ON CONFLICT(guild_id, item) DO UPDATE SET amount = amount + ?, category = ?",
              (interaction.guild.id, предмет, категория, количество, количество, категория))
    conn.commit()
    log_action(interaction.guild.id, interaction.user.id, nick, "Положить на склад", f"{предмет} ({категория}) +{количество}")
    await interaction.response.send_message(f'✅ `{nick}` положил {количество} x **{предмет}** ({категория}) на склад.', ephemeral=True)

@bot.tree.command(name="склад", description="Просмотр склада")
@app_commands.choices(категория=[
    app_commands.Choice(name="Всё", value="all"),
    app_commands.Choice(name="Оружие", value="Оружие"),
    app_commands.Choice(name="Патроны", value="Патроны"),
    app_commands.Choice(name="Расходники", value="Расходники"),
    app_commands.Choice(name="Прочее", value="Прочее")
])
async def warehouse_show(interaction: discord.Interaction, категория: str = "all"):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    if категория == "all":
        c.execute("SELECT item, amount, category FROM warehouse WHERE guild_id=? AND amount > 0", (interaction.guild.id,))
        rows = c.fetchall()
        if not rows:
            return await interaction.response.send_message('📦 Склад пуст.', ephemeral=True)
        cats = {}
        for item, amount, cat in rows:
            cats.setdefault(cat, []).append((item, amount))
        embed = discord.Embed(title="🗄️ СЕМЕЙНЫЙ СКЛАД", color=0x8B5E3C)
        cat_emojis = {"Оружие": "🔫", "Патроны": "📦", "Расходники": "💊", "Прочее": "🧰"}
        def indicator(amount):
            if amount >= 50: return "🟩"
            elif amount >= 20: return "🟨"
            else: return "🟥"
        content_parts = []
        total_all = 0
        for cat in ["Оружие", "Патроны", "Расходники", "Прочее"]:
            if cat in cats:
                cat_total = sum(amount for _, amount in cats[cat])
                total_all += cat_total
                lines = []
                for item, amount in cats[cat]:
                    name = item.replace("_", " ").title()
                    lines.append(f"{indicator(amount)} **{name}** — `{amount}` шт.")
                items_text = "\n".join(lines)
                cat_display = f"{cat_emojis.get(cat, '📦')} {cat.upper()}"
                header = f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n┃   {cat_display.center(22)} ┃\n┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫"
                footer = f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
                content_parts.append(f"{header}\n{items_text}\n{footer}")
        content_parts.append(f"**🧾 ВСЕГО НА СКЛАДЕ:** `{total_all}` предметов")
        embed.description = "\n".join(content_parts)
    else:
        c.execute("SELECT item, amount FROM warehouse WHERE guild_id=? AND category=? AND amount > 0", (interaction.guild.id, категория))
        rows = c.fetchall()
        if not rows:
            return await interaction.response.send_message('📦 Склад пуст.', ephemeral=True)
        total = sum(amount for _, amount in rows)
        lines = []
        for item, amount in rows:
            name = item.replace("_", " ").title()
            lines.append(f"• **{name}** — `{amount}` шт.")
        items_text = "\n".join(lines)
        cat_display = f"{категория.upper()}"
        header = f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n┃   {cat_display.center(22)} ┃\n┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫"
        footer = f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n**Всего:** {total} шт."
        embed = discord.Embed(title="🗄️ СЕМЕЙНЫЙ СКЛАД", color=0x8B5E3C, description=f"{header}\n{items_text}\n{footer}")
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2938/2938122.png")
    embed.set_footer(text=f"Обновлено: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="всклад", description="Взять предмет со склада")
async def warehouse_take(interaction: discord.Interaction, предмет: str, количество: int):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    nick = get_member_nick(interaction.guild.id, interaction.user.id)
    if not nick:
        return await interaction.response.send_message('❌ Вы не привязаны к семье.', ephemeral=True)
    nick = nick.replace("_", " ")
    if количество <= 0:
        return await interaction.response.send_message('❌ Количество > 0.', ephemeral=True)
    предмет = предмет.replace("_", " ").title()
    c.execute("SELECT amount FROM warehouse WHERE guild_id=? AND item=?", (interaction.guild.id, предмет))
    row = c.fetchone()
    if not row or row[0] < количество:
        return await interaction.response.send_message(f'❌ Недостаточно `{предмет}` на складе.', ephemeral=True)
    c.execute("UPDATE warehouse SET amount = amount - ? WHERE guild_id=? AND item=?", (количество, interaction.guild.id, предмет))
    conn.commit()
    log_action(interaction.guild.id, interaction.user.id, nick, "Взять со склада", f"{предмет} -{количество}")
    await interaction.response.send_message(f'✅ `{nick}` забрал {количество} x **{предмет}** со склада.', ephemeral=True)

@bot.tree.command(name="вк", description="Взять контракт")
async def take_contract(interaction: discord.Interaction, участники: str, название: str, дата: str, время: str, векселя: int = 0):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    members = []
    for part in участники.split():
        if part.startswith('<@') and part.endswith('>'):
            uid = part.strip('<@!>')
            if uid.isdigit():
                m = interaction.guild.get_member(int(uid))
                if m: members.append(m)
    if not members:
        return await interaction.response.send_message("❌ Укажите участников через @.", ephemeral=True)
    try:
        due_dt = datetime.datetime.strptime(f"{дата} {время}", "%d.%m.%Y %H:%M")
    except ValueError:
        return await interaction.response.send_message("❌ Неверный формат даты/времени.", ephemeral=True)
    participants_db = ', '.join(str(m.id) for m in members)
    c.execute("INSERT INTO contracts (guild_id, title, participants, due_date, bills, created_by, created_at, status) VALUES (?,?,?,?,?,?,?,?)",
              (interaction.guild.id, название, participants_db, due_dt.isoformat(), векселя, str(interaction.user), datetime.datetime.now().isoformat(), 'создан'))
    conn.commit()
    contract_id = c.lastrowid
    status_channel_id = get_contract_status_channel(interaction.guild.id)
    status_channel = interaction.guild.get_channel(status_channel_id) if status_channel_id else None
    if status_channel is None:
        return await interaction.response.send_message("❌ Канал уведомлений о статусе не найден. Настройте бота через /setup в ЛС.", ephemeral=True)
    participants_mentions = ', '.join(m.mention for m in members)
    contract_role_id = get_contract_role(interaction.guild.id)
    role_mention = f"<@&{contract_role_id}>" if contract_role_id else ""
    embed = discord.Embed(title=f"📝 Контракт «{название}»", color=0x3498db)
    embed.add_field(name="Участники", value=participants_mentions, inline=False)
    embed.add_field(name="Срок", value=f"{дата} {время}", inline=False)
    if векселя: embed.add_field(name="Векселей", value=str(векселя), inline=False)
    embed.set_footer(text=f"ID: {contract_id} | Поставьте ✅ для старта")
    msg = await status_channel.send(content=role_mention, embed=embed)
    c.execute("UPDATE contracts SET message_id=? WHERE id=?", (msg.id, contract_id))
    conn.commit()
    log_action(interaction.guild.id, interaction.user.id, get_member_nick(interaction.guild.id, interaction.user.id) or str(interaction.user),
               "Создание контракта", f"'{название}', участники: {participants_db}")
    await interaction.response.send_message(f"✅ Контракт создан (ID {contract_id}). Уведомления придут в каналы.", ephemeral=True)

@bot.tree.command(name="дв", description="Выдать дисциплинарное взыскание")
@app_commands.choices(тип=[
    app_commands.Choice(name="предупреждение", value="предупреждение"),
    app_commands.Choice(name="выговор", value="выговор"),
    app_commands.Choice(name="2 выговора", value="2выговора"),
    app_commands.Choice(name="warn", value="warn"),
    app_commands.Choice(name="увал", value="увал")
])
async def dv_add(interaction: discord.Interaction, участники: str, тип: str, причина: str):
    if not await check_dv(interaction) and not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    members = []
    for part in участники.split():
        if part.startswith('<@') and part.endswith('>'):
            uid = part.strip('<@!>')
            if uid.isdigit():
                m = interaction.guild.get_member(int(uid))
                if m: members.append(m)
    if not members:
        return await interaction.response.send_message("❌ Укажите участников через @.", ephemeral=True)
    issuer_nick = get_member_nick(interaction.guild.id, interaction.user.id) or str(interaction.user)
    for m in members:
        nickname = m.display_name.replace(" ", "_")
        c.execute("INSERT INTO disciplinary_actions (guild_id, nickname, discord_id, action_type, reason, issued_by, date) VALUES (?,?,?,?,?,?,?)",
                  (interaction.guild.id, nickname, m.id, тип, причина, str(interaction.user), datetime.datetime.now().isoformat()))
        conn.commit()
        log_action(interaction.guild.id, interaction.user.id, issuer_nick, "Выдача ДВ", f"{nickname}: {тип}, причина: {причина}")
    mentions = ', '.join(m.mention for m in members)
    await interaction.response.send_message(f'⚠️ {mentions} получили **{тип}**.\nПричина: {причина}\nВыдал: {interaction.user.mention}', ephemeral=True)

@bot.tree.command(name="снятьдв", description="Снять последнее взыскание")
async def dv_remove(interaction: discord.Interaction, участник: str, причина: str):
    if not await check_dv(interaction) and not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    uid = None
    if участник.startswith('<@') and участник.endswith('>'):
        uid = участник.strip('<@!>')
    if not uid or not uid.isdigit():
        return await interaction.response.send_message("❌ Укажите участника через @.", ephemeral=True)
    member = interaction.guild.get_member(int(uid))
    if member is None:
        return await interaction.response.send_message("❌ Участник не найден.", ephemeral=True)
    nickname = member.display_name.replace(" ", "_")
    c.execute("SELECT date FROM disciplinary_actions WHERE guild_id=? AND nickname=? ORDER BY date DESC LIMIT 1", (interaction.guild.id, nickname))
    row = c.fetchone()
    if row:
        try:
            last_dv_date = datetime.datetime.fromisoformat(row[0])
            days = get_discipline_remove_days(interaction.guild.id)
            if (datetime.datetime.now() - last_dv_date).days < days:
                days_left = days - (datetime.datetime.now() - last_dv_date).days
                return await interaction.response.send_message(f"❌ С момента последнего взыскания прошло менее {days} дней. Осталось: {days_left} дн.", ephemeral=True)
        except:
            pass
    c.execute("DELETE FROM disciplinary_actions WHERE id = (SELECT id FROM disciplinary_actions WHERE guild_id=? AND nickname=? ORDER BY date DESC LIMIT 1)",
              (interaction.guild.id, nickname))
    if c.rowcount == 0:
        return await interaction.response.send_message(f'❌ У {member.mention} нет выговоров.', ephemeral=True)
    conn.commit()
    log_action(interaction.guild.id, interaction.user.id, get_member_nick(interaction.guild.id, interaction.user.id) or str(interaction.user),
               "Снятие ДВ", f"{nickname}, причина: {причина}")
    await interaction.response.send_message(f'✅ Снят последний выговор с {member.mention}.\nПричина: {причина}', ephemeral=True)

@bot.tree.command(name="выг", description="Показать выговоры участника")
async def dv_list(interaction: discord.Interaction, участник: str = None):
    if not await check_dv(interaction) and not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    if участник:
        uid = участник.strip('<@!>') if участник.startswith('<@') else None
        if uid and uid.isdigit():
            member = interaction.guild.get_member(int(uid))
            nickname = member.display_name.replace(" ", "_") if member else участник
        else:
            nickname = участник
    else:
        nickname = get_member_nick(interaction.guild.id, interaction.user.id)
        if not nickname:
            return await interaction.response.send_message('❌ Укажите @участника или будьте в семье.', ephemeral=True)
    c.execute("SELECT action_type, reason, issued_by, date FROM disciplinary_actions WHERE guild_id=? AND nickname=? ORDER BY date DESC",
              (interaction.guild.id, nickname))
    rows = c.fetchall()
    if not rows:
        return await interaction.response.send_message(f'✅ У `{nickname}` нет выговоров.', ephemeral=True)
    lines = [f'**{t}** — {r} (от {i}, {d})' for t, r, i, d in rows]
    embed = discord.Embed(title=f'📋 Выговоры: {nickname}', description='\n'.join(lines), color=0xff0000)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="logs", description="Показать логи")
async def show_logs(interaction: discord.Interaction, участник: str = None):
    if not await check_admin(interaction):
        return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)
    if участник:
        uid = участник.strip('<@!>') if участник.startswith('<@') else None
        if uid and uid.isdigit():
            c.execute("SELECT nickname, action, details, timestamp FROM logs WHERE guild_id=? AND discord_id=? ORDER BY id DESC LIMIT 10",
                      (interaction.guild.id, int(uid)))
        else:
            c.execute("SELECT nickname, action, details, timestamp FROM logs WHERE guild_id=? AND nickname=? ORDER BY id DESC LIMIT 10",
                      (interaction.guild.id, участник))
    else:
        c.execute("SELECT nickname, action, details, timestamp FROM logs WHERE guild_id=? ORDER BY id DESC LIMIT 10", (interaction.guild.id,))
    rows = c.fetchall()
    if not rows:
        return await interaction.response.send_message("📋 Логов нет.", ephemeral=True)
    lines = [f'**{nick}** – {action}\n{details} | {ts}' for nick, action, details, ts in rows]
    embed = discord.Embed(title="📋 Логи", description='\n'.join(lines), color=0x3498db)
    await interaction.response.send_message(embed=embed, ephemeral=True)

class SnakeGame:
    def __init__(self):
        self.board_size = 8
        self.snake = [(4,4)]
        self.direction = (0,1)
        self.food = self.place_food()
        self.score = 0
        self.game_over = False

    def place_food(self):
        while True:
            pos = (random.randint(0, self.board_size-1), random.randint(0, self.board_size-1))
            if pos not in self.snake:
                return pos

    def move(self):
        if self.game_over:
            return False
        head = self.snake[0]
        new_head = (head[0] + self.direction[0], head[1] + self.direction[1])
        if not (0 <= new_head[0] < self.board_size and 0 <= new_head[1] < self.board_size) or new_head in self.snake:
            self.game_over = True
            return False
        self.snake.insert(0, new_head)
        if new_head == self.food:
            self.score += 1
            self.food = self.place_food()
        else:
            self.snake.pop()
        return True

    def render(self):
        board = [['⬛' for _ in range(self.board_size)] for _ in range(self.board_size)]
        for y,x in self.snake:
            if 0 <= y < self.board_size and 0 <= x < self.board_size:
                board[y][x] = '🟢'
        fy, fx = self.food
        board[fy][fx] = '🍎'
        head_y, head_x = self.snake[0]
        if 0 <= head_y < self.board_size and 0 <= head_x < self.board_size:
            board[head_y][head_x] = '🐍'
        return '\n'.join(''.join(row) for row in board)

class MinesweeperGame:
    def __init__(self, size=5, mines=4):
        self.size = size
        self.mines = set()
        while len(self.mines) < mines:
            self.mines.add((random.randint(0,size-1), random.randint(0,size-1)))
        self.revealed = [[False]*size for _ in range(size)]
        self.game_over = False

    def reveal(self, x, y):
        if (x,y) in self.mines:
            self.game_over = True
            return '💣'
        count = 0
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                if dx==0 and dy==0: continue
                nx, ny = x+dx, y+dy
                if 0 <= nx < self.size and 0 <= ny < self.size and (nx,ny) in self.mines:
                    count += 1
        self.revealed[y][x] = True
        emoji_map = ['0️⃣','1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣']
        return emoji_map[count] if count > 0 else '⬜'

    def render(self):
        lines = []
        for y in range(self.size):
            row = ''
            for x in range(self.size):
                if self.revealed[y][x]:
                    if (x,y) in self.mines:
                        row += '💣'
                    else:
                        count = 0
                        for dx in (-1,0,1):
                            for dy in (-1,0,1):
                                if dx==0 and dy==0: continue
                                nx, ny = x+dx, y+dy
                                if 0 <= nx < self.size and 0 <= ny < self.size and (nx,ny) in self.mines:
                                    count += 1
                        emoji_map = ['0️⃣','1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣']
                        row += emoji_map[count] if count > 0 else '⬜'
                else:
                    row += '⬛'
            lines.append(row)
        return '\n'.join(lines)

class GameView(View):
    def __init__(self, game, user_id, game_type):
        super().__init__(timeout=120)
        self.game = game
        self.user_id = user_id
        self.game_type = game_type

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Это не ваша игра!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="⏰ Время игры истекло.", view=None)

class SnakeView(GameView):
    def __init__(self, game, user_id):
        super().__init__(game, user_id, "змейка")

    async def update_game(self, interaction):
        self.game.move()
        embed = discord.Embed(title="🐍 Змейка", description=self.game.render(), color=0x2ecc71)
        embed.set_footer(text=f"Счёт: {self.game.score}")
        if self.game.game_over:
            embed.title = "💀 Игра окончена!"
            for child in self.children:
                child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji='⬆️', style=discord.ButtonStyle.secondary, custom_id='snake_up')
    async def up(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if self.game.direction != (1,0):
            self.game.direction = (-1,0)
        await self.update_game(interaction)

    @discord.ui.button(emoji='⬇️', style=discord.ButtonStyle.secondary, custom_id='snake_down')
    async def down(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if self.game.direction != (-1,0):
            self.game.direction = (1,0)
        await self.update_game(interaction)

    @discord.ui.button(emoji='⬅️', style=discord.ButtonStyle.secondary, custom_id='snake_left')
    async def left(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if self.game.direction != (0,1):
            self.game.direction = (0,-1)
        await self.update_game(interaction)

    @discord.ui.button(emoji='➡️', style=discord.ButtonStyle.secondary, custom_id='snake_right')
    async def right(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if self.game.direction != (0,-1):
            self.game.direction = (0,1)
        await self.update_game(interaction)

class MinesweeperView(GameView):
    def __init__(self, game, user_id):
        super().__init__(game, user_id, "сапёр")

    async def update(self, interaction, x, y):
        self.game.reveal(x, y)
        embed = discord.Embed(title="💣 Сапёр", description=self.game.render(), color=0x3498db)
        if self.game.game_over:
            embed.title = "💥 Взрыв!"
            for child in self.children:
                child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='\u200b', custom_id='ms0', row=0)
    async def btn0(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 0, 0)

    @discord.ui.button(label='\u200b', custom_id='ms1', row=0)
    async def btn1(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 1, 0)

    @discord.ui.button(label='\u200b', custom_id='ms2', row=0)
    async def btn2(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 2, 0)

    @discord.ui.button(label='\u200b', custom_id='ms3', row=0)
    async def btn3(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 3, 0)

    @discord.ui.button(label='\u200b', custom_id='ms4', row=0)
    async def btn4(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 4, 0)

    @discord.ui.button(label='\u200b', custom_id='ms5', row=1)
    async def btn5(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 0, 1)

    @discord.ui.button(label='\u200b', custom_id='ms6', row=1)
    async def btn6(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 1, 1)

    @discord.ui.button(label='\u200b', custom_id='ms7', row=1)
    async def btn7(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 2, 1)

    @discord.ui.button(label='\u200b', custom_id='ms8', row=1)
    async def btn8(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 3, 1)

    @discord.ui.button(label='\u200b', custom_id='ms9', row=1)
    async def btn9(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 4, 1)

    @discord.ui.button(label='\u200b', custom_id='ms10', row=2)
    async def btn10(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 0, 2)

    @discord.ui.button(label='\u200b', custom_id='ms11', row=2)
    async def btn11(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 1, 2)

    @discord.ui.button(label='\u200b', custom_id='ms12', row=2)
    async def btn12(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 2, 2)

    @discord.ui.button(label='\u200b', custom_id='ms13', row=2)
    async def btn13(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 3, 2)

    @discord.ui.button(label='\u200b', custom_id='ms14', row=2)
    async def btn14(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 4, 2)

    @discord.ui.button(label='\u200b', custom_id='ms15', row=3)
    async def btn15(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 0, 3)

    @discord.ui.button(label='\u200b', custom_id='ms16', row=3)
    async def btn16(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 1, 3)

    @discord.ui.button(label='\u200b', custom_id='ms17', row=3)
    async def btn17(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 2, 3)

    @discord.ui.button(label='\u200b', custom_id='ms18', row=3)
    async def btn18(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 3, 3)

    @discord.ui.button(label='\u200b', custom_id='ms19', row=3)
    async def btn19(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 4, 3)

    @discord.ui.button(label='\u200b', custom_id='ms20', row=4)
    async def btn20(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 0, 4)

    @discord.ui.button(label='\u200b', custom_id='ms21', row=4)
    async def btn21(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 1, 4)

    @discord.ui.button(label='\u200b', custom_id='ms22', row=4)
    async def btn22(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 2, 4)

    @discord.ui.button(label='\u200b', custom_id='ms23', row=4)
    async def btn23(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 3, 4)

    @discord.ui.button(label='\u200b', custom_id='ms24', row=4)
    async def btn24(self, interaction, button):
        await interaction.response.defer()
        await self.update(interaction, 4, 4)

@bot.tree.command(name="игра", description="Запустить мини-игру")
@app_commands.choices(игра=[
    app_commands.Choice(name="Змейка", value="змейка"),
    app_commands.Choice(name="Сапёр", value="сапёр")
])
async def start_game(interaction: discord.Interaction, игра: str):
    if interaction.user.id in games:
        await interaction.response.send_message("У вас уже есть активная игра!", ephemeral=True)
        return
    if игра == "змейка":
        game = SnakeGame()
        view = SnakeView(game, interaction.user.id)
        embed = discord.Embed(title="🐍 Змейка", description=game.render(), color=0x2ecc71)
        embed.set_footer(text="Счёт: 0")
        await interaction.response.send_message(embed=embed, view=view)
        games[interaction.user.id] = game
    elif игра == "сапёр":
        game = MinesweeperGame()
        view = MinesweeperView(game, interaction.user.id)
        embed = discord.Embed(title="💣 Сапёр", description=game.render(), color=0x3498db)
        await interaction.response.send_message(embed=embed, view=view)
        games[interaction.user.id] = game

@bot.command(name="банк")
async def bank_balance_txt(ctx):
    if not await has_admin(ctx):
        return await ctx.send("❌ Недостаточно прав.", delete_after=10)
    balance = get_family_balance(ctx.guild.id)
    await ctx.send(f'💰 Баланс семьи: {balance}')

@bot.command(name="пополнить")
async def bank_add_txt(ctx, amount: int, *, reason=""):
    if not await has_admin(ctx):
        return await ctx.send("❌ Недостаточно прав.", delete_after=10)
    if not ctx.message.attachments:
        return await ctx.send("❌ Необходимо прикрепить скриншот.", delete_after=10)
    if amount <= 0:
        return await ctx.send("❌ Сумма должна быть положительной.", delete_after=10)
    nick = get_member_nick(ctx.guild.id, ctx.author.id)
    if not nick:
        return await ctx.send("❌ Вы не привязаны к семье. Используйте !добавсемья.", delete_after=10)
    nick = nick.replace("_", " ")
    c.execute("UPDATE bank SET balance = balance + ? WHERE guild_id=?", (amount, ctx.guild.id))
    if c.rowcount == 0:
        c.execute("INSERT INTO bank (guild_id, balance) VALUES (?, ?)", (ctx.guild.id, amount))
    conn.commit()
    new_balance = get_family_balance(ctx.guild.id)
    log_action(ctx.guild.id, ctx.author.id, nick, "Пополнение банка", f"+{amount}, причина: {reason}")
    file = discord.File(await ctx.message.attachments[0].read(), filename=ctx.message.attachments[0].filename)
    await ctx.send(f"💰 Счёт семьи пополнен на {amount} (от {nick}). Баланс: {new_balance}.", file=file)

@bot.command(name="снять")
async def bank_remove_txt(ctx, amount: int, *, reason=""):
    if not await has_admin(ctx):
        return await ctx.send("❌ Недостаточно прав.", delete_after=10)
    if amount <= 0:
        return await ctx.send("❌ Сумма должна быть положительной.", delete_after=10)
    nick = get_member_nick(ctx.guild.id, ctx.author.id)
    if not nick:
        return await ctx.send("❌ Вы не привязаны к семье. Используйте !добавсемья.", delete_after=10)
    nick = nick.replace("_", " ")
    balance = get_family_balance(ctx.guild.id)
    if balance < amount:
        return await ctx.send(f"❌ Недостаточно средств. Баланс: {balance}.", delete_after=10)
    c.execute("UPDATE bank SET balance = balance - ? WHERE guild_id=?", (amount, ctx.guild.id))
    conn.commit()
    new_balance = get_family_balance(ctx.guild.id)
    log_action(ctx.guild.id, ctx.author.id, nick, "Снятие с банка", f"-{amount}, причина: {reason}")
    await ctx.send(f"💸 Из бюджета семьи снято {amount} (от {nick}). Баланс: {new_balance}.")

@bot.command(name="дв")
async def dv_add_txt(ctx, members: commands.Greedy[discord.Member], action_type: str, *, reason: str):
    if not await has_dv(ctx) and not await has_admin(ctx):
        return await ctx.send("❌ Недостаточно прав.", delete_after=10)
    action_type = action_type.lower()
    allowed = ["предупреждение", "выговор", "2выговора", "warn", "увал"]
    if action_type not in allowed:
        return await ctx.send(f'❌ Неверный тип. Допустимые: {", ".join(allowed)}', delete_after=10)
    issuer_nick = get_member_nick(ctx.guild.id, ctx.author.id) or str(ctx.author)
    for m in members:
        nickname = m.display_name.replace(" ", "_")
        c.execute("INSERT INTO disciplinary_actions (guild_id, nickname, discord_id, action_type, reason, issued_by, date) VALUES (?,?,?,?,?,?,?)",
                  (ctx.guild.id, nickname, m.id, action_type, reason, str(ctx.author), datetime.datetime.now().isoformat()))
        conn.commit()
        log_action(ctx.guild.id, ctx.author.id, issuer_nick, "Выдача ДВ", f"{nickname}: {action_type}, причина: {reason}")
    mentions = ', '.join(m.mention for m in members)
    await ctx.send(f'⚠️ {mentions} получили **{action_type}**.\nПричина: {reason}\nВыдал: {ctx.author.mention}')

@bot.command(name="помощь")
async def help_txt(ctx):
    msg = "✨ **Помощь по боту**\n"
    msg += "👥 **Семья:** !дсемья ID Ник, !усемья ID, !семья\n"
    msg += "🚗 **Авто:** !давто Модель Госномер, !уавто Госномер, !авто, !взавто Номер [часы], !веавто Номер\n"
    msg += "📦 **Склад:** !склад [Категория], !псклад Предмет Категория Кол-во, !всклад Предмет Кол-во\n"
    msg += "💰 **Банк:** !банк, !пополнить Сумма [Причина] (скриншот обязателен), !снять Сумма [Причина]\n"
    msg += "⚠️ **Дисциплина:** !дв @Участники Тип Причина, !выг [@Участник], !снятьдв @Участник Причина\n"
    msg += "📋 **Логи:** !logs [@Участник]\n"
    msg += "🛠️ **Настройка:** !setup в ЛС\n"
    msg += "🎮 **Игры:** /игра"
    await ctx.send(msg)

@bot.event
async def on_ready():
    print(f"Бот {bot.user} готов!")

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()

bot.run(TOKEN)
