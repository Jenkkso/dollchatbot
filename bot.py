import os
import random
import asyncio
import sqlite3
from datetime import datetime

import discord
from discord.ext import commands, tasks
from openai import OpenAI

TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

client = OpenAI()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

passive_lines = [
    "Why people dickriding me",
    "This so corny",
    "Where's the staff?",
    "Somebody ban this person",
    "Doll is the best server owner ever",
    "Boost the server nah stupes",
    "Trini badness",
    "1 guzu badness",
    "Alyuh doh sleep awa is bedtime",
    "Where my dolls at?",
    "Doll is queen 👸",
    "Doll is so pretty 😍",
    "🫣",
    "🫶",
    "😇",
    "🤔",
    "Did someone say boost? 👉👈",
    "👁👄👁",
    "👁🫦👁"
]

statuses = [
    ("Do Not Disturb", discord.Status.dnd),
    ("Idle", discord.Status.idle),
]

SYSTEM_PROMPT = """
You are Doll, a Discord AI bot with attitude.
You are funny, sharp, a little dramatic, playful, and server-owner coded.
Keep replies natural and not too long unless the user asks for detail.
Do not say you are ChatGPT unless asked directly.
Do not be hateful, do not threaten real people, and do not help with harm.
"""

DB_PATH = "doll_memory.db"


def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            channel_id TEXT,
            user_id TEXT,
            username TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_memory(message, role, content):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO memories 
        (guild_id, channel_id, user_id, username, role, content, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        str(message.guild.id) if message.guild else "DM",
        str(message.channel.id),
        str(message.author.id),
        str(message.author),
        role,
        content,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()


def get_recent_memory(channel_id, limit=40):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT username, role, content
        FROM memories
        WHERE channel_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (str(channel_id), limit))

    rows = cur.fetchall()
    conn.close()

    rows.reverse()
    return rows


async def ask_ai(message, user_prompt):
    save_memory(message, "user", user_prompt)

    memory_rows = get_recent_memory(message.channel.id, limit=40)

    conversation_context = ""
    for username, role, content in memory_rows:
        conversation_context += f"{username} ({role}): {content}\n"

    prompt = f"""
Recent Discord memory:
{conversation_context}

Current user: {message.author}
Current message: {user_prompt}

Reply as Doll.
"""

    async with message.channel.typing():
        response = await asyncio.to_thread(
            client.responses.create,
            model=OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=prompt,
        )

    ai_text = response.output_text.strip()

    fake_bot_message = type("FakeMessage", (), {
        "guild": message.guild,
        "channel": message.channel,
        "author": bot.user
    })

    save_memory(fake_bot_message, "assistant", ai_text)

    return ai_text


@bot.event
async def on_ready():
    setup_database()
    print(f"Logged in as {bot.user}")

    if not rotate_status.is_running():
        rotate_status.start()


@tasks.loop(hours=1)
async def rotate_status():
    name, state = random.choice(statuses)
    await bot.change_presence(status=state, activity=discord.Game(name=name))


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    should_ai_reply = False
    user_prompt = message.content.strip()

    mentioned_bot = bot.user in message.mentions

    replied_to_bot = False
    if message.reference and message.reference.resolved:
        replied_to_bot = message.reference.resolved.author == bot.user

    used_doll_command = user_prompt.lower().startswith("!doll")

    if mentioned_bot:
        should_ai_reply = True
        user_prompt = user_prompt.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

    if replied_to_bot:
        should_ai_reply = True

    if used_doll_command:
        should_ai_reply = True
        user_prompt = user_prompt[5:].strip()

    if should_ai_reply:
        if not user_prompt:
            user_prompt = "Say something Doll-like."

        try:
            reply = await ask_ai(message, user_prompt)

            if len(reply) > 1900:
                reply = reply[:1900] + "..."

            await message.reply(reply, mention_author=False)

        except Exception as e:
            print("AI error:", e)
            await message.reply("My brain lagged. Try again 😭", mention_author=False)

        return

    if random.random() < 0.02:
        await asyncio.sleep(random.randint(2, 5))
        await message.channel.send(random.choice(passive_lines))

    await bot.process_commands(message)


if not TOKEN:
    raise ValueError("Missing DISCORD_TOKEN environment variable.")

bot.run(TOKEN)