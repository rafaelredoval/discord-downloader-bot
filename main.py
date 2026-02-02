import discord
import os
import re
import subprocess
import asyncio
from datetime import datetime, timezone

# =====================
# ENV VARS
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID", "0"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID", "0"))

if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN não definido")

if SCAN_CHANNEL_ID == 0:
    raise RuntimeError("❌ SCAN_CHANNEL_ID não definido")

if DOWNLOAD_CHANNEL_ID == 0:
    raise RuntimeError("❌ DOWNLOAD_CHANNEL_ID não definido")

# =====================
# DISCORD CONFIG
# =====================
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True

client = discord.Client(intents=intents)

# =====================
# GLOBALS
# =====================
URL_REGEX = re.compile(r'https?://\S+')
DOWNLOAD_BASE = "downloads"
scan_cancelled = False

# =====================
# UTILS
# =====================
def parse_date(arg):
    try:
        return datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Bot conectado como {client.user}")
    print(f"📌 Canal Scan: {SCAN_CHANNEL_ID}")
    print(f"📦 Canal Download: {DOWNLOAD_CHANNEL_ID}")

# =====================
# SCAN FUNCTION
# =====================
async def run_scan(ctx_message, date_filter=None):
    global scan_cancelled
    scan_cancelled = False

    scan_channel = ctx_message.channel
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    await scan_channel.send("🔍 **Iniciando varredura...**")

    async for msg in scan_channel.history(
        limit=None,
        oldest_first=True,
        after=date_filter
    ):
        if scan_cancelled:
            await scan_channel.send("⛔ **Scan cancelado**")
            return

        if msg.author.bot:
            continue

        urls = URL_REGEX.findall(msg.content)
        if not urls:
            continue

        for url in urls:
            try:
                # testa se o link é válido
                subprocess.run(
                    ["yt-dlp", "--skip-download", url],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                await msg.add_reaction("✅")

            except Exception:
                await msg.add_reaction("❌")

    await scan_channel.send("✅ **Scan finalizado**")

# =====================
# COMMANDS
# =====================
@client.event
async def on_message(message):
    global scan_cancelled

    if message.author.bot:
        return

    # =====================
    # !scan [data]
    # =====================
    if message.content.startswith("!scan"):
        if message.channel.id != SCAN_CHANNEL_ID:
            await message.channel.send("❌ Este não é o canal de scan")
            return

        parts = message.content.split()
        date_filter = parse_date(parts[1]) if len(parts) > 1 else None

        await run_scan(message, date_filter)

    # =====================
    # !cancelscan
    # =====================
    elif message.content == "!cancelscan":
        scan_cancelled = True
        await message.channel.send("⛔ Cancelamento solicitado")

    # =====================
    # !botlimpar
    # =====================
    elif message.content == "!botlimpar":
        removed = 0

        async for msg in message.channel.history(limit=None):
            try:
                await msg.clear_reactions()
                removed += 1
            except:
                pass

        await message.channel.send(f"🧹 Reações limpas em {removed} mensagens")

# =====================
# START
# =====================
client.run(TOKEN)
