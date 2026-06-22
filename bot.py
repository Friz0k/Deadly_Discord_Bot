import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import datetime
import io
import os
import re
from flask import Flask
from threading import Thread

TOKEN = os.getenv("TOKEN")
GUILD_ID = discord.Object(id=1473690194539708457)

SUPER_ADMIN_ROLE = "Тех. Состав"
RECRUITER_ROLE = "Recruiter"
ASSISTANT_ROLE = "Assistant"
DEADLY_ROLE = "Deadly"
DISCIPLINE_ROLE = "Discipline"

CONTRACT_NOTIFY_ROLE_ID = 1516422622122999888
CONTRACT_CHANNEL_ID = 1515046132936343633
CONTRACT_STATUS_CHANNEL_ID = 1515039473581166642
SERVER_LOG_CHANNEL_ID = 1518296636030325017

ROLE_PRED = 1473709199488975020
ROLE_1VYG = 1473709489780953260
ROLE_2VYG = 1473709343126847549
ROLE_WARN = 1516422427327074404
ROLE_FAMILY_AUTO = 1475823094869393591
ROLE_VACATION_ID = 1517727379198578739

DISC_ROLES = [ROLE_PRED, ROLE_1VYG, ROLE_2VYG, ROLE_WARN]
DB_PATH = 'gta_rp.db'
BAD_WORDS = ["плохоеслово1", "плохоеслово2"]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS family_members (
    nickname TEXT PRIMARY KEY,
    discord_id INTEGER UNIQUE,
    joined_at TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_nick TEXT,
    model TEXT,
    plate TEXT UNIQUE,
    status TEXT DEFAULT 'свободен',
    taken_by TEXT,
    taken_at TEXT,
    return_at TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS warehouse (
    item TEXT PRIMARY KEY,
    amount INTEGER CHECK(amount >= 0),
    category TEXT DEFAULT 'Прочее'
)''')
c.execute('''CREATE TABLE IF NOT EXISTS bank (
    balance INTEGER DEFAULT 0
)''')
c.execute("INSERT INTO bank (balance) SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM bank)")
c.execute('''CREATE TABLE IF NOT EXISTS disciplinary_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname TEXT,
    discord_id INTEGER,
    action_type TEXT,
    reason TEXT,
    issued_by TEXT,
    date TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id INTEGER,
    nickname TEXT,
    action TEXT,
    details TEXT,
    timestamp TEXT
)''')

def ensure_contracts_columns():
    c.execute('''CREATE TABLE IF NOT EXISTS contracts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    required = {'bills': 'INTEGER DEFAULT 0', 'status': "TEXT DEFAULT 'создан'", 'message_id': 'INTEGER', 'notified_hours': 'INTEGER DEFAULT 0', 'started_at': 'TEXT'}
    for col, dtype in required.items():
        c.execute(f"PRAGMA table_info(contracts)")
        if col not in [col[1] for col in c.fetchall()]:
            c.execute(f"ALTER TABLE contracts ADD COLUMN {col} {dtype}")
    conn.commit()

ensure_contracts_columns()

def add_column_if_not_exists(table, column, type_def):
    c.execute(f"PRAGMA table_info({table})")
    if column not in [col[1] for col in c.fetchall()]:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_def}")
        conn.commit()

add_column_if_not_exists("family_members", "discord_id", "INTEGER")
add_column_if_not_exists("disciplinary_actions", "discord_id", "INTEGER")
add_column_if_not_exists("warehouse", "category", "TEXT DEFAULT 'Прочее'")
c.execute("UPDATE warehouse SET category = 'Прочее' WHERE category = 'Проче'")
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
        await self.tree.sync(guild=GUILD_ID)
        print("Слеш-команды синхронизированы.")

bot = MyBot()

def get_member_nick(user_id):
    c.execute("SELECT nickname FROM family_members WHERE discord_id=?", (user_id,))
    row = c.fetchone()
    return row[0] if row else None

def get_family_balance():
    c.execute("SELECT balance FROM bank LIMIT 1")
    return c.fetchone()[0]

def auto_return():
    now = datetime.datetime.now().isoformat()
    c.execute("UPDATE vehicles SET status='свободен', taken_by=NULL, taken_at=NULL, return_at=NULL WHERE status='занят' AND return_at <= ?", (now,))
    conn.commit()

def log_action(discord_id, nickname, action, details=""):
    c.execute("INSERT INTO logs (discord_id, nickname, action, details, timestamp) VALUES (?,?,?,?,?)",
              (discord_id, nickname, action, details, datetime.datetime.now().isoformat()))
    conn.commit()

def get_discipline_counts(nickname):
    c.execute("SELECT COUNT(*) FROM disciplinary_actions WHERE nickname=? AND action_type='предупреждение'", (nickname,))
    warnings = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM disciplinary_actions WHERE nickname=? AND action_type='выговор'", (nickname,))
    vygs = c.fetchone()[0]
    return warnings, vygs

async def update_discipline_roles(member, nickname):
    for role_id in DISC_ROLES:
        role = member.guild.get_role(role_id)
        if role and role in member.roles:
            try: await member.remove_roles(role, reason="Пересчёт наказаний")
            except: pass
    warns, vygs = get_discipline_counts(nickname)
    new_vygs = vygs + warns // 2
    remaining_warns = warns % 2
    if warns >= 2:
        c.execute("DELETE FROM disciplinary_actions WHERE nickname=? AND action_type='предупреждение'", (nickname,))
        for _ in range(warns // 2):
            c.execute("INSERT INTO disciplinary_actions (nickname, discord_id, action_type, reason, issued_by, date) VALUES (?,?,?,?,?,?)",
                      (nickname, member.id, "выговор", "Автоконвертация 2 предупреждений", "Система", datetime.datetime.now().isoformat()))
        conn.commit()
        new_vygs = vygs + warns // 2
        remaining_warns = 0
    if remaining_warns == 1:
        role = member.guild.get_role(ROLE_PRED)
        if role: await member.add_roles(role, reason="Предупреждение")
    if new_vygs >= 3: role = member.guild.get_role(ROLE_WARN)
    elif new_vygs == 2: role = member.guild.get_role(ROLE_2VYG)
    elif new_vygs == 1: role = member.guild.get_role(ROLE_1VYG)
    else: role = None
    if role: await member.add_roles(role, reason=f"Выговоры: {new_vygs}")

@bot.event
async def on_audit_log_entry_create(entry):
    log_channel = entry.guild.get_channel(SERVER_LOG_CHANNEL_ID)
    if not log_channel:
        return
    user = entry.user.mention if entry.user else "Неизвестно"
    target = entry.target.mention if entry.target else "Неизвестно"
    action = entry.action
    reason = entry.reason or "Не указана"

    if action == discord.AuditLogAction.member_role_update:
        embed = discord.Embed(title="🔄 Изменение ролей", color=0x3498db, timestamp=datetime.datetime.now())
        embed.add_field(name="Инициатор", value=user)
        embed.add_field(name="Пользователь", value=target)
        if entry.before.roles != entry.after.roles:
            added = [role.mention for role in entry.after.roles if role not in entry.before.roles]
            removed = [role.mention for role in entry.before.roles if role not in entry.after.roles]
            if added: embed.add_field(name="➕ Выданы роли", value=", ".join(added) or "Нет", inline=False)
            if removed: embed.add_field(name="➖ Сняты роли", value=", ".join(removed) or "Нет", inline=False)
        await log_channel.send(embed=embed)

    elif action == discord.AuditLogAction.kick:
        embed = discord.Embed(title="🥾 Кик участника", color=0xe74c3c, timestamp=datetime.datetime.now())
        embed.add_field(name="Инициатор", value=user)
        embed.add_field(name="Пользователь", value=target)
        embed.add_field(name="Причина", value=reason, inline=False)
        await log_channel.send(embed=embed)

    elif action == discord.AuditLogAction.ban:
        embed = discord.Embed(title="🔨 Бан участника", color=0xe74c3c, timestamp=datetime.datetime.now())
        embed.add_field(name="Инициатор", value=user)
        embed.add_field(name="Пользователь", value=target)
        embed.add_field(name="Причина", value=reason, inline=False)
        await log_channel.send(embed=embed)

    elif action == discord.AuditLogAction.unban:
        embed = discord.Embed(title="✅ Разбан участника", color=0x2ecc71, timestamp=datetime.datetime.now())
        embed.add_field(name="Инициатор", value=user)
        embed.add_field(name="Пользователь", value=target)
        await log_channel.send(embed=embed)

    elif action == discord.AuditLogAction.member_update:
        if entry.before.nick != entry.after.nick:
            embed = discord.Embed(title="🔄 Смена ника", color=0x3498db, timestamp=datetime.datetime.now())
            embed.add_field(name="Инициатор", value=user)
            embed.add_field(name="Пользователь", value=target)
            embed.add_field(name="Было", value=entry.before.nick or entry.before.name)
            embed.add_field(name="Стало", value=entry.after.nick or entry.after.name)
            await log_channel.send(embed=embed)

    elif action == discord.AuditLogAction.message_delete:
        embed = discord.Embed(title="🗑️ Сообщение удалено", color=0xe74c3c, timestamp=datetime.datetime.now())
        embed.add_field(name="Инициатор", value=user)
        embed.add_field(name="Автор сообщения", value=target)
        embed.add_field(name="Канал", value=entry.extra.channel.mention if entry.extra and entry.extra.channel else "Неизвестно")
        if hasattr(entry, 'before') and hasattr(entry.before, 'content'):
            embed.add_field(name="Содержание", value=entry.before.content[:1024] or "Нет текста", inline=False)
        await log_channel.send(embed=embed)

    elif action in [discord.AuditLogAction.channel_create, discord.AuditLogAction.channel_delete, discord.AuditLogAction.channel_update]:
        channel = entry.target.mention if entry.target else "Неизвестно"
        embed = discord.Embed(title=f"{'➕ Создан' if action == discord.AuditLogAction.channel_create else '➖ Удалён' if action == discord.AuditLogAction.channel_delete else '🔄 Изменён'} канал",
                              color=0x3498db, timestamp=datetime.datetime.now())
        embed.add_field(name="Инициатор", value=user)
        embed.add_field(name="Канал", value=channel)
        await log_channel.send(embed=embed)

    elif action == discord.AuditLogAction.overwrite_create:
        embed = discord.Embed(title="🔒 Изменены права канала", color=0x3498db, timestamp=datetime.datetime.now())
        embed.add_field(name="Инициатор", value=user)
        embed.add_field(name="Канал", value=entry.target.mention if entry.target else "Неизвестно")
        await log_channel.send(embed=embed)

@bot.event
async def on_voice_state_update(member, before, after):
    log_channel = member.guild.get_channel(SERVER_LOG_CHANNEL_ID) if member.guild else None
    if not log_channel or member.bot:
        return
    if before.channel is None and after.channel is not None:
        embed = discord.Embed(title="🔊 Зашёл в голосовой канал", color=0x2ecc71, timestamp=datetime.datetime.now())
        embed.add_field(name="Пользователь", value=member.mention)
        embed.add_field(name="Канал", value=after.channel.name)
        await log_channel.send(embed=embed)
    elif before.channel is not None and after.channel is None:
        embed = discord.Embed(title="🔇 Вышел из голосового канала", color=0xe74c3c, timestamp=datetime.datetime.now())
        embed.add_field(name="Пользователь", value=member.mention)
        embed.add_field(name="Канал", value=before.channel.name)
        await log_channel.send(embed=embed)
    elif before.channel != after.channel:
        embed = discord.Embed(title="🔄 Переместился в голосовой канал", color=0x3498db, timestamp=datetime.datetime.now())
        embed.add_field(name="Пользователь", value=member.mention)
        embed.add_field(name="Из", value=before.channel.name)
        embed.add_field(name="В", value=after.channel.name)
        await log_channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot: return
    content = message.content.lower()
    for word in BAD_WORDS:
        if re.search(rf'\b{word}\b', content):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, ваше сообщение удалено за использование запрещённого слова.", delete_after=10)
            log_channel = message.guild.get_channel(SERVER_LOG_CHANNEL_ID)
            if log_channel:
                embed = discord.Embed(title="🚫 Модерация слов", color=0xe74c3c, timestamp=datetime.datetime.now())
                embed.add_field(name="Пользователь", value=message.author.mention)
                embed.add_field(name="Канал", value=message.channel.mention)
                embed.add_field(name="Содержание", value=message.content[:500])
                await log_channel.send(embed=embed)
            break
    await bot.process_commands(message)

@tasks.loop(minutes=10)
async def update_all_nicknames():
    c.execute("SELECT discord_id, nickname FROM family_members")
    rows = c.fetchall()
    guild = bot.guilds[0] if bot.guilds else None
    if not guild: return
    for disc_id, old_nick in rows:
        member = guild.get_member(disc_id)
        if member:
            new_nick = member.display_name.replace(" ", "_")
            if new_nick != old_nick:
                c.execute("UPDATE family_members SET nickname=? WHERE discord_id=?", (new_nick, disc_id))
                conn.commit()

@tasks.loop(hours=1)
async def auto_remove_expired_discipline():
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
    c.execute("DELETE FROM disciplinary_actions WHERE date <= ?", (cutoff,))
    if c.rowcount > 0:
        conn.commit()
        guild = bot.guilds[0] if bot.guilds else None
        if guild:
            c.execute("SELECT DISTINCT discord_id, nickname FROM disciplinary_actions")
            for disc_id, nick in c.fetchall():
                member = guild.get_member(disc_id)
                if member: await update_discipline_roles(member, nick)

@tasks.loop(hours=1)
async def contract_reminders():
    now = datetime.datetime.now()
    c.execute("SELECT id, title, participants, due_date, notified_hours, message_id, started_at FROM contracts WHERE status='в процессе'")
    contracts = c.fetchall()
    guild = bot.guilds[0] if bot.guilds else None
    if not guild: return
    channel = guild.get_channel(CONTRACT_CHANNEL_ID)
    status_channel = guild.get_channel(CONTRACT_STATUS_CHANNEL_ID)
    if not channel: return
    for cid, title, participants, due_str, notified, msg_id, started_str in contracts:
        try:
            due_date = datetime.datetime.fromisoformat(due_str)
            started_at = datetime.datetime.fromisoformat(started_str) if started_str else None
        except: continue
        if due_date > now:
            if started_at:
                elapsed = now - started_at
                hours_passed = int(elapsed.total_seconds() // 3600)
            else: hours_passed = 0
            participants_mentions = ', '.join([f'<@{p.strip()}>' for p in participants.split(',') if p.strip().isdigit()])
            c.execute("UPDATE contracts SET notified_hours = notified_hours + 1 WHERE id=?", (cid,))
            conn.commit()
            await channel.send(f'{participants_mentions} У ВАС ИДЕТ КОНТРАКТ прошло: {hours_passed} ч.')
        else:
            c.execute("UPDATE contracts SET status='выполнен' WHERE id=?", (cid,))
            conn.commit()
            participants_mentions = ', '.join([f'<@{p.strip()}>' for p in participants.split(',') if p.strip().isdigit()])
            if status_channel:
                embed = discord.Embed(title=f"✅ Контракт «{title}» выполнен", description="Время выполнения истекло.", color=0x2ecc71)
                embed.add_field(name="Участники", value=participants_mentions or "Не указаны")
                embed.add_field(name="Дедлайн", value=due_date.strftime("%d.%m.%Y %H:%M"))
                await status_channel.send(embed=embed)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.emoji.name != '✅' or payload.channel_id != CONTRACT_STATUS_CHANNEL_ID: return
    guild = bot.get_guild(payload.guild_id)
    if guild is None: return
    member = guild.get_member(payload.user_id)
    if member is None or member.bot: return
    if not any(role.id == CONTRACT_NOTIFY_ROLE_ID for role in member.roles): return
    c.execute("SELECT id, status FROM contracts WHERE message_id=?", (payload.message_id,))
    row = c.fetchone()
    if row and row[1] == 'создан':
        now = datetime.datetime.now()
        c.execute("UPDATE contracts SET status='в процессе', started_at=? WHERE id=?", (now.isoformat(), row[0]))
        conn.commit()
        c.execute("SELECT title, participants, message_id FROM contracts WHERE id=?", (row[0],))
        contract = c.fetchone()
        if contract:
            title, participants, msg_id = contract
            participants_mentions = ', '.join([f'<@{p.strip()}>' for p in participants.split(',') if p.strip().isdigit()])
            notify_channel = guild.get_channel(CONTRACT_CHANNEL_ID)
            if notify_channel:
                await notify_channel.send(f"{participants_mentions} Ваш контракт начал выполняться!")
        channel = bot.get_channel(payload.channel_id)
        if channel: await channel.send(f"✅ Контракт (ID {row[0]}) принят к выполнению.")

@bot.event
async def on_ready():
    print(f"Бот {bot.user} готов!")
    update_all_nicknames.start()
    auto_remove_expired_discipline.start()
    contract_reminders.start()

@bot.tree.command(name="хелп", description="Помощь по боту", guild=GUILD_ID)
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="✨ Помощь по боту", color=0x9b59b6)
    embed.add_field(name="👥 Семья", value="/дсемья ID Ник — добавить\n/усемья ID — удалить\n/семья", inline=False)
    embed.add_field(name="🚗 Авто", value="/давто Модель Госномер\n/уавто Госномер\n/авто — список\n/взавто Номер [часы]\n/веавто Номер", inline=False)
    embed.add_field(name="📦 Склад", value="/склад [Категория]\n/псклад Предмет Категория Кол-во\n/всклад Предмет Кол-во", inline=False)
    embed.add_field(name="💰 Банк", value="/банк — баланс\n/пополнить Сумма [Причина]\n/снять Сумма [Причина]", inline=False)
    embed.add_field(name="📝 Контракты", value="/вк @Участники Название ДД.ММ.ГГГГ ЧЧ:ММ [векселя]", inline=False)
    embed.add_field(name="⚠️ Дисциплина", value="/дв @Участники Тип Причина\n/выг [@Участник]\n/снятьдв @Участник Причина", inline=False)
    embed.add_field(name="📋 Логи", value="/logs [@Участник]", inline=False)
    embed.add_field(name="💾 Бекап", value="/backup\n/restore\n/reset_contracts", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="backup", description="Сохранить базу данных", guild=GUILD_ID)
@app_commands.checks.has_any_role(ASSISTANT_ROLE, SUPER_ADMIN_ROLE)
async def backup_db(interaction: discord.Interaction):
    if not os.path.exists(DB_PATH):
        await interaction.response.send_message("❌ База данных не найдена.", ephemeral=True); return
    file = discord.File(DB_PATH, filename="gta_rp.db")
    await interaction.response.send_message("📦 Бекап базы данных:", file=file, ephemeral=True)

@bot.tree.command(name="restore", description="Восстановить базу данных", guild=GUILD_ID)
@app_commands.checks.has_any_role(ASSISTANT_ROLE, SUPER_ADMIN_ROLE)
async def restore_db(interaction: discord.Interaction, файл: discord.Attachment):
    if not файл.filename.endswith('.db'):
        await interaction.response.send_message("❌ Файл должен иметь расширение .db."); return
    if os.path.exists(DB_PATH):
        os.rename(DB_PATH, DB_PATH + '.backup')
    try:
        await файл.save(DB_PATH)
        global conn, c
        conn.close()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        update_all_nicknames.restart()
        auto_remove_expired_discipline.restart()
        contract_reminders.restart()
        await interaction.response.send_message("✅ База данных восстановлена.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Ошибка восстановления: {e}")
        if os.path.exists(DB_PATH + '.backup'):
            os.rename(DB_PATH + '.backup', DB_PATH)

@bot.tree.command(name="reset_contracts", description="Исправить таблицу контрактов", guild=GUILD_ID)
@app_commands.checks.has_any_role(ASSISTANT_ROLE, SUPER_ADMIN_ROLE)
async def reset_contracts(interaction: discord.Interaction):
    c.execute("DROP TABLE IF EXISTS contracts")
    c.execute('''CREATE TABLE contracts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    await interaction.response.send_message("✅ Таблица контрактов исправлена. Можете пользоваться `/вк`.")

@bot.tree.command(name="id", description="Узнать Discord ID", guild=GUILD_ID)
@app_commands.checks.has_any_role(RECRUITER_ROLE, SUPER_ADMIN_ROLE)
async def get_id(interaction: discord.Interaction, пользователь: discord.Member = None):
    member = пользователь or interaction.user
    await interaction.response.send_message(f'🆔 {member.mention}: `{member.id}`')

@bot.tree.command(name="дсемья", description="Добавить участника в семью", guild=GUILD_ID)
@app_commands.checks.has_any_role(RECRUITER_ROLE, SUPER_ADMIN_ROLE)
async def add_family(interaction: discord.Interaction, discord_id: str, никнейм: str):
    try: disc_id = int(discord_id)
    except ValueError:
        await interaction.response.send_message("❌ Неверный формат ID."); return
    никнейм = никнейм.replace("_", " ")
    c.execute("SELECT * FROM family_members WHERE discord_id=?", (disc_id,))
    if c.fetchone():
        await interaction.response.send_message(f'⚠️ Пользователь с ID `{disc_id}` уже в семье.'); return
    c.execute("SELECT * FROM family_members WHERE nickname=?", (никнейм,))
    if c.fetchone():
        await interaction.response.send_message(f'⚠️ Ник `{никнейм}` уже занят.'); return
    c.execute("INSERT INTO family_members (nickname, discord_id, joined_at) VALUES (?, ?, ?)", (никнейм, disc_id, datetime.datetime.now().isoformat()))
    conn.commit()
    log_action(interaction.user.id, get_member_nick(interaction.user.id) or str(interaction.user), "Добавление в семью", f"Добавлен {никнейм} ({disc_id})")
    await interaction.response.send_message(f'✅ <@{disc_id}> (`{никнейм}`) добавлен в семью.')

@bot.tree.command(name="усемья", description="Удалить участника из семьи", guild=GUILD_ID)
@app_commands.checks.has_any_role(ASSISTANT_ROLE, SUPER_ADMIN_ROLE)
async def remove_family(interaction: discord.Interaction, discord_id: str):
    try: disc_id = int(discord_id)
    except ValueError:
        await interaction.response.send_message("❌ Неверный формат ID."); return
    c.execute("SELECT nickname FROM family_members WHERE discord_id=?", (disc_id,))
    row = c.fetchone()
    if not row:
        await interaction.response.send_message(f'❌ Пользователь с ID `{disc_id}` не найден в семье.'); return
    nickname = row[0]
    c.execute("DELETE FROM family_members WHERE discord_id=?", (disc_id,))
    conn.commit()
    log_action(interaction.user.id, get_member_nick(interaction.user.id) or str(interaction.user), "Удаление из семьи", f"Удалён {nickname} ({disc_id})")
    await interaction.response.send_message(f'✅ <@{disc_id}> (`{nickname}`) удалён из семьи.')

@bot.tree.command(name="семья", description="Список членов семьи", guild=GUILD_ID)
@app_commands.checks.has_any_role(RECRUITER_ROLE, SUPER_ADMIN_ROLE)
async def family_list(interaction: discord.Interaction):
    c.execute("SELECT nickname, discord_id FROM family_members")
    rows = c.fetchall()
    if not rows:
        await interaction.response.send_message('👪 Семья пуста.'); return
    lines = [f'<@{disc_id}> — `{nick}`' for nick, disc_id in rows]
    embed = discord.Embed(title='👥 Семья', description='\n'.join(lines), color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="давто", description="Добавить автомобиль", guild=GUILD_ID)
@app_commands.checks.has_any_role(ASSISTANT_ROLE, SUPER_ADMIN_ROLE)
async def add_car(interaction: discord.Interaction, модель: str, госномер: str):
    nick = get_member_nick(interaction.user.id)
    if not nick:
        await interaction.response.send_message('❌ Вы не привязаны к семье. Сначала добавьте себя через /дсемья.'); return
    nick = nick.replace("_", " ")
    try:
        c.execute("INSERT INTO vehicles (owner_nick, model, plate) VALUES (?, ?, ?)", (nick, модель, госномер))
        conn.commit()
        car_id = c.lastrowid
        log_action(interaction.user.id, nick, "Добавление авто", f"Модель {модель}, госномер {госномер}")
        await interaction.response.send_message(f'🚗 {модель} ({госномер}) добавлен, номер {car_id}. Владелец: `{nick}`.')
    except sqlite3.IntegrityError:
        await interaction.response.send_message(f'❌ Госномер `{госномер}` уже существует.')

@bot.tree.command(name="уавто", description="Удалить автомобиль", guild=GUILD_ID)
@app_commands.checks.has_any_role(ASSISTANT_ROLE, SUPER_ADMIN_ROLE)
async def remove_car(interaction: discord.Interaction, госномер: str):
    c.execute("DELETE FROM vehicles WHERE plate=?", (госномер,))
    if c.rowcount == 0:
        await interaction.response.send_message(f'❌ Машина с госномером `{госномер}` не найдена.'); return
    conn.commit()
    log_action(interaction.user.id, get_member_nick(interaction.user.id) or str(interaction.user), "Удаление авто", f"Госномер {госномер}")
    await interaction.response.send_message(f'🗑️ Машина `{госномер}` удалена.')

@bot.tree.command(name="авто", description="Список автомобилей", guild=GUILD_ID)
@app_commands.checks.has_any_role(DEADLY_ROLE, SUPER_ADMIN_ROLE)
async def car_list(interaction: discord.Interaction):
    auto_return()
    c.execute("SELECT id, owner_nick, model, plate, status, taken_by, return_at FROM vehicles")
    cars = c.fetchall()
    if not cars:
        await interaction.response.send_message('🚫 Нет машин.'); return
    lines = []
    for cid, owner, model, plate, status, taken_by, ret_at in cars:
        if status == 'свободен':
            lines.append(f'`{cid}` {model} ({plate}) — свободен')
        else:
            lines.append(f'`{cid}` {model} ({plate}) — занят {taken_by}, до {ret_at}')
    embed = discord.Embed(title='🚗 Автомобили', description='\n'.join(lines), color=0x3498db)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="взавто", description="Взять автомобиль", guild=GUILD_ID)
@app_commands.checks.has_any_role(DEADLY_ROLE, SUPER_ADMIN_ROLE)
async def take_car(interaction: discord.Interaction, номер: int, часы: float = 2.0):
    nick = get_member_nick(interaction.user.id)
    if not nick:
        await interaction.response.send_message('❌ Вы не привязаны к семье.'); return
    nick = nick.replace("_", " ")
    auto_return()
    c.execute("SELECT status, plate FROM vehicles WHERE id=?", (номер,))
    car = c.fetchone()
    if not car:
        await interaction.response.send_message(f'❌ Авто с номером `{номер}` не найдено.'); return
    status, plate = car
    if status != 'свободен':
        await interaction.response.send_message(f'❌ Авто `{plate}` уже занято.'); return
    now = datetime.datetime.now()
    return_at = now + datetime.timedelta(hours=часы)
    c.execute("UPDATE vehicles SET status='занят', taken_by=?, taken_at=?, return_at=? WHERE id=?", (nick, now.isoformat(), return_at.isoformat(), номер))
    conn.commit()
    log_action(interaction.user.id, nick, "Взять авто", f"Номер {номер}, на {часы} ч")
    await interaction.response.send_message(f'✅ `{plate}` выдано `{nick}` на {часы} ч до {return_at.strftime("%d.%m.%Y %H:%M")}.')

@bot.tree.command(name="веавто", description="Вернуть автомобиль", guild=GUILD_ID)
@app_commands.checks.has_any_role(DEADLY_ROLE, SUPER_ADMIN_ROLE)
async def return_car(interaction: discord.Interaction, номер: int):
    c.execute("SELECT plate, status FROM vehicles WHERE id=?", (номер,))
    car = c.fetchone()
    if not car:
        await interaction.response.send_message(f'❌ Авто с номером `{номер}` не найдено.'); return
    plate, status = car
    if status == 'свободен':
        await interaction.response.send_message(f'❌ Авто `{plate}` уже свободно.'); return
    c.execute("UPDATE vehicles SET status='свободен', taken_by=NULL, taken_at=NULL, return_at=NULL WHERE id=?", (номер,))
    conn.commit()
    log_action(interaction.user.id, get_member_nick(interaction.user.id) or str(interaction.user), "Вернуть авто", f"Номер {номер}")
    await interaction.response.send_message(f'✅ Авто `{plate}` возвращено.')

@bot.tree.command(name="псклад", description="Положить предмет на склад", guild=GUILD_ID)
@app_commands.checks.has_any_role(ASSISTANT_ROLE, SUPER_ADMIN_ROLE)
@app_commands.choices(категория=[
    app_commands.Choice(name="Оружие", value="Оружие"),
    app_commands.Choice(name="Патроны", value="Патроны"),
    app_commands.Choice(name="Расходники", value="Расходники"),
    app_commands.Choice(name="Прочее", value="Прочее")
])
async def warehouse_put(interaction: discord.Interaction, предмет: str, категория: str, количество: int):
    nick = get_member_nick(interaction.user.id)
    if not nick:
        await interaction.response.send_message('❌ Вы не привязаны к семье.'); return
    nick = nick.replace("_", " ")
    if количество <= 0:
        await interaction.response.send_message('❌ Количество > 0.'); return
    предмет = предмет.replace("_", " ").title()
    c.execute("INSERT INTO warehouse (item, category, amount) VALUES (?, ?, ?) ON CONFLICT(item) DO UPDATE SET amount = amount + ?, category = ?",
              (предмет, категория, количество, количество, категория))
    conn.commit()
    log_action(interaction.user.id, nick, "Положить на склад", f"{предмет} ({категория}) +{количество}")
    await interaction.response.send_message(f'✅ `{nick}` положил {количество} x **{предмет}** ({категория}) на склад.')

@bot.tree.command(name="склад", description="Просмотр склада", guild=GUILD_ID)
@app_commands.checks.has_any_role(DEADLY_ROLE, SUPER_ADMIN_ROLE)
@app_commands.choices(категория=[
    app_commands.Choice(name="Всё", value="all"),
    app_commands.Choice(name="Оружие", value="Оружие"),
    app_commands.Choice(name="Патроны", value="Патроны"),
    app_commands.Choice(name="Расходники", value="Расходники"),
    app_commands.Choice(name="Прочее", value="Прочее")
])
async def warehouse_show(interaction: discord.Interaction, категория: str = "all"):
    if категория == "all":
        c.execute("SELECT item, amount, category FROM warehouse WHERE amount > 0")
        rows = c.fetchall()
        if not rows:
            await interaction.response.send_message('📦 Склад пуст.'); return
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
        c.execute("SELECT item, amount FROM warehouse WHERE category=? AND amount > 0", (категория,))
        rows = c.fetchall()
        if not rows:
            await interaction.response.send_message('📦 Склад пуст.'); return
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
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="всклад", description="Взять предмет со склада", guild=GUILD_ID)
@app_commands.checks.has_any_role(DEADLY_ROLE, SUPER_ADMIN_ROLE)
async def warehouse_take(interaction: discord.Interaction, предмет: str, количество: int):
    nick = get_member_nick(interaction.user.id)
    if not nick:
        await interaction.response.send_message('❌ Вы не привязаны к семье.'); return
    nick = nick.replace("_", " ")
    if количество <= 0:
        await interaction.response.send_message('❌ Количество > 0.'); return
    предмет = предмет.replace("_", " ").title()
    c.execute("SELECT amount FROM warehouse WHERE item=?", (предмет,))
    row = c.fetchone()
    if not row or row[0] < количество:
        await interaction.response.send_message(f'❌ Недостаточно `{предмет}` на складе.'); return
    c.execute("UPDATE warehouse SET amount = amount - ? WHERE item=?", (количество, предмет))
    conn.commit()
    log_action(interaction.user.id, nick, "Взять со склада", f"{предмет} -{количество}")
    await interaction.response.send_message(f'✅ `{nick}` забрал {количество} x **{предмет}** со склада.')

@bot.tree.command(name="банк", description="Баланс семьи", guild=GUILD_ID)
@app_commands.checks.has_any_role(ASSISTANT_ROLE, SUPER_ADMIN_ROLE)
async def bank_balance(interaction: discord.Interaction):
    balance = get_family_balance()
    await interaction.response.send_message(f'💰 Баланс семьи: {balance}')

@bot.tree.command(name="пополнить", description="Пополнить семейный банк", guild=GUILD_ID)
@app_commands.checks.has_any_role(DEADLY_ROLE, SUPER_ADMIN_ROLE)
async def bank_add(interaction: discord.Interaction, сумма: int, причина: str = ""):
    if сумма <= 0:
        await interaction.response.send_message('❌ Сумма должна быть положительной.'); return
    nick = get_member_nick(interaction.user.id)
    if not nick:
        await interaction.response.send_message('❌ Вы не привязаны к семье. Используйте /дсемья.'); return
    nick = nick.replace("_", " ")
    c.execute("UPDATE bank SET balance = balance + ?", (сумма,))
    conn.commit()
    new_balance = get_family_balance()
    log_action(interaction.user.id, nick, "Пополнение банка", f"+{сумма}, причина: {причина}")
    await interaction.response.send_message(f'💰 Счёт семьи пополнен на {сумма} (от {nick}). Баланс: {new_balance}.')

@bot.tree.command(name="снять", description="Снять деньги из семейного банка", guild=GUILD_ID)
@app_commands.checks.has_any_role(DEADLY_ROLE, SUPER_ADMIN_ROLE)
async def bank_remove(interaction: discord.Interaction, сумма: int, причина: str = ""):
    if сумма <= 0:
        await interaction.response.send_message('❌ Сумма должна быть положительной.'); return
    nick = get_member_nick(interaction.user.id)
    if not nick:
        await interaction.response.send_message('❌ Вы не привязаны к семье. Используйте /дсемья.'); return
    nick = nick.replace("_", " ")
    balance = get_family_balance()
    if balance < сумма:
        await interaction.response.send_message(f'❌ Недостаточно средств. Баланс: {balance}.'); return
    c.execute("UPDATE bank SET balance = balance - ?", (сумма,))
    conn.commit()
    new_balance = get_family_balance()
    log_action(interaction.user.id, nick, "Снятие с банка", f"-{сумма}, причина: {причина}")
    await interaction.response.send_message(f'💸 Из бюджета семьи снято {сумма} (от {nick}). Баланс: {new_balance}.')

@bot.tree.command(name="вк", description="Взять контракт", guild=GUILD_ID)
@app_commands.checks.has_any_role(DEADLY_ROLE, SUPER_ADMIN_ROLE)
async def take_contract(interaction: discord.Interaction, участники: str, название: str, дата: str, время: str, векселя: int = 0):
    members = []
    for part in участники.split():
        if part.startswith('<@') and part.endswith('>'):
            uid = part.strip('<@!>')
            if uid.isdigit():
                m = interaction.guild.get_member(int(uid))
                if m: members.append(m)
    if not members:
        await interaction.response.send_message("❌ Укажите участников через @."); return
    try: due_dt = datetime.datetime.strptime(f"{дата} {время}", "%d.%m.%Y %H:%M")
    except ValueError:
        await interaction.response.send_message("❌ Неверный формат даты/времени."); return
    participants_db = ', '.join(str(m.id) for m in members)
    c.execute("INSERT INTO contracts (title, participants, due_date, bills, created_by, created_at, status) VALUES (?,?,?,?,?,?,?)",
              (название, participants_db, due_dt.isoformat(), векселя, str(interaction.user), datetime.datetime.now().isoformat(), 'создан'))
    conn.commit()
    contract_id = c.lastrowid
    status_channel = interaction.guild.get_channel(CONTRACT_STATUS_CHANNEL_ID)
    if status_channel is None:
        await interaction.response.send_message("❌ Канал уведомлений о статусе не найден."); return
    participants_mentions = ', '.join(m.mention for m in members)
    role_mention = f"<@&{CONTRACT_NOTIFY_ROLE_ID}>"
    embed = discord.Embed(title=f"📝 Контракт «{название}»", color=0x3498db)
    embed.add_field(name="Участники", value=participants_mentions, inline=False)
    embed.add_field(name="Срок", value=f"{дата} {время}", inline=False)
    if векселя: embed.add_field(name="Векселей", value=str(векселя), inline=False)
    embed.set_footer(text=f"ID: {contract_id} | Поставьте ✅ для старта")
    msg = await status_channel.send(content=role_mention, embed=embed)
    c.execute("UPDATE contracts SET message_id=? WHERE id=?", (msg.id, contract_id))
    conn.commit()
    log_action(interaction.user.id, get_member_nick(interaction.user.id) or str(interaction.user), "Создание контракта", f"'{название}', участники: {participants_db}")
    await interaction.response.send_message(f"✅ Контракт создан (ID {contract_id}). Уведомления придут в каналы.")

@bot.tree.command(name="дв", description="Выдать дисциплинарное взыскание", guild=GUILD_ID)
@app_commands.checks.has_any_role(DISCIPLINE_ROLE, SUPER_ADMIN_ROLE)
@app_commands.choices(тип=[
    app_commands.Choice(name="предупреждение", value="предупреждение"),
    app_commands.Choice(name="выговор", value="выговор"),
    app_commands.Choice(name="2 выговора", value="2выговора"),
    app_commands.Choice(name="warn", value="warn"),
    app_commands.Choice(name="увал", value="увал")
])
async def dv_add(interaction: discord.Interaction, участники: str, тип: str, причина: str):
    members = []
    for part in участники.split():
        if part.startswith('<@') and part.endswith('>'):
            uid = part.strip('<@!>')
            if uid.isdigit():
                m = interaction.guild.get_member(int(uid))
                if m: members.append(m)
    if not members:
        await interaction.response.send_message("❌ Укажите участников через @."); return
    vacation_role = interaction.guild.get_role(ROLE_VACATION_ID)
    blocked = []
    for m in members:
        if vacation_role and vacation_role in m.roles:
            blocked.append(m.display_name)
    if blocked:
        await interaction.response.send_message(f"❌ Нельзя выдать ДВ следующим участникам (Отпуск): {', '.join(blocked)}"); return
    issuer_nick = get_member_nick(interaction.user.id) or str(interaction.user)
    for m in members:
        nickname = m.display_name.replace(" ", "_")
        c.execute("INSERT INTO disciplinary_actions (nickname, discord_id, action_type, reason, issued_by, date) VALUES (?,?,?,?,?,?)",
                  (nickname, m.id, тип, причина, str(interaction.user), datetime.datetime.now().isoformat()))
        conn.commit()
        await update_discipline_roles(m, nickname)
        log_action(interaction.user.id, issuer_nick, "Выдача ДВ", f"{nickname}: {тип}, причина: {причина}")
    mentions = ', '.join(m.mention for m in members)
    await interaction.response.send_message(f'⚠️ {mentions} получили **{тип}**.\nПричина: {причина}\nВыдал: {interaction.user.mention}')

@bot.tree.command(name="снятьдв", description="Снять последнее взыскание", guild=GUILD_ID)
@app_commands.checks.has_any_role(DISCIPLINE_ROLE, SUPER_ADMIN_ROLE)
async def dv_remove(interaction: discord.Interaction, участник: str, причина: str):
    uid = None
    if участник.startswith('<@') and участник.endswith('>'):
        uid = участник.strip('<@!>')
    if not uid or not uid.isdigit():
        await interaction.response.send_message("❌ Укажите участника через @."); return
    member = interaction.guild.get_member(int(uid))
    if member is None:
        await interaction.response.send_message("❌ Участник не найден."); return
    nickname = member.display_name.replace(" ", "_")
    c.execute("SELECT date FROM disciplinary_actions WHERE nickname=? ORDER BY date DESC LIMIT 1", (nickname,))
    row = c.fetchone()
    if row:
        try: last_dv_date = datetime.datetime.fromisoformat(row[0])
        except: last_dv_date = None
        if last_dv_date and (datetime.datetime.now() - last_dv_date).days < 7:
            days_left = 7 - (datetime.datetime.now() - last_dv_date).days
            await interaction.response.send_message(f"❌ С момента последнего взыскания прошло менее 7 дней. Осталось: {days_left} дн."); return
    c.execute("DELETE FROM disciplinary_actions WHERE id = (SELECT id FROM disciplinary_actions WHERE nickname=? ORDER BY date DESC LIMIT 1)", (nickname,))
    if c.rowcount == 0:
        await interaction.response.send_message(f'❌ У {member.mention} нет выговоров.'); return
    conn.commit()
    await update_discipline_roles(member, nickname)
    log_action(interaction.user.id, get_member_nick(interaction.user.id) or str(interaction.user), "Снятие ДВ", f"{nickname}, причина: {причина}")
    await interaction.response.send_message(f'✅ Снят последний выговор с {member.mention}.\nПричина: {причина}')

@bot.tree.command(name="выг", description="Показать выговоры участника", guild=GUILD_ID)
@app_commands.checks.has_any_role(DISCIPLINE_ROLE, SUPER_ADMIN_ROLE)
async def dv_list(interaction: discord.Interaction, участник: str = None):
    if участник:
        uid = участник.strip('<@!>') if участник.startswith('<@') else None
        if uid and uid.isdigit():
            member = interaction.guild.get_member(int(uid))
            nickname = member.display_name.replace(" ", "_") if member else участник
        else: nickname = участник
    else:
        nickname = get_member_nick(interaction.user.id)
        if not nickname:
            await interaction.response.send_message('❌ Укажите @участника или будьте в семье.'); return
    c.execute("SELECT action_type, reason, issued_by, date FROM disciplinary_actions WHERE nickname=? ORDER BY date DESC", (nickname,))
    rows = c.fetchall()
    if not rows:
        await interaction.response.send_message(f'✅ У `{nickname}` нет выговоров.'); return
    lines = [f'**{t}** — {r} (от {i}, {d})' for t, r, i, d in rows]
    embed = discord.Embed(title=f'📋 Выговоры: {nickname}', description='\n'.join(lines), color=0xff0000)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="logs", description="Показать логи", guild=GUILD_ID)
@app_commands.checks.has_any_role(ASSISTANT_ROLE, SUPER_ADMIN_ROLE)
async def show_logs(interaction: discord.Interaction, участник: str = None):
    if участник:
        uid = участник.strip('<@!>') if участник.startswith('<@') else None
        if uid and uid.isdigit():
            c.execute("SELECT nickname, action, details, timestamp FROM logs WHERE discord_id=? ORDER BY id DESC LIMIT 10", (int(uid),))
        else:
            c.execute("SELECT nickname, action, details, timestamp FROM logs WHERE nickname=? ORDER BY id DESC LIMIT 10", (участник,))
    else:
        c.execute("SELECT nickname, action, details, timestamp FROM logs ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    if not rows:
        await interaction.response.send_message("📋 Логов нет."); return
    lines = [f'**{nick}** – {action}\n{details} | {ts}' for nick, action, details, ts in rows]
    embed = discord.Embed(title="📋 Логи", description='\n'.join(lines), color=0x3498db)
    await interaction.response.send_message(embed=embed)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()

bot.run(TOKEN)
