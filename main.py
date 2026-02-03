import discord
import os
import re
import asyncio
import subprocess
from datetime import datetime, timedelta, timezone

# =====================
# ENV VARS
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))

# =====================
# DISCORD
# =====================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# =====================
# GLOBALS
# =====================
URL_REGEX = re.compile(r'https?://\S+')
DOWNLOAD_BASE = "downloads"
SCAN_DELAY = 1.5

scan_running = False
scan_cancelled = False
downloaded_urls = set()

BOT_REACTIONS = {"✅", "❌"}

# =====================
# DATE PARSER (BR)
# =====================
def parse_br_datetime(text):
    try:
        dt = datetime.strptime(text, "%d/%m/%Y %H:%M")
    except ValueError:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")

    # Brasil UTC-3 → UTC
    return dt.replace(tzinfo=timezone(timedelta(hours=-3))).astimezone(timezone.utc)

# =====================
# DOWNLOAD
# =====================
async def try_download(msg, download_channel):
    urls = URL_REGEX.findall(msg.content)
    if not urls:
        return False

    success = False

    for url in urls:
        if url in downloaded_urls:
            continue

        user_id = str(msg.author.id)
        date_folder = msg.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        safe = str(abs(hash(url)))

        folder = os.path.join(DOWNLOAD_BASE, user_id, date_folder, safe)
        os.makedirs(folder, exist_ok=True)

        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "-o", f"{folder}/%(title)s.%(ext)s",
            url
        )
        await proc.communicate()

        if proc.returncode != 0:
            continue

        sent = 0
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path):
                await download_channel.send(
                    content=f"📦 <@{user_id}>",
                    file=discord.File(path)
                )
                os.remove(path)
                sent += 1

        if sent > 0:
            downloaded_urls.add(url)
            success = True

    return success

# =====================
# SCAN NORMAL
# =====================
async def run_scan(message, start_date):
    global scan_running, scan_cancelled
    scan_running = True
    scan_cancelled = False

    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    await message.channel.send("🔍 **Scan iniciado**")

    async for msg in scan_channel.history(after=start_date, oldest_first=True):
        if scan_cancelled:
            break

        ok = await try_download(msg, download_channel)
        await msg.add_reaction("✅" if ok else "❌")
        await asyncio.sleep(SCAN_DELAY)

    scan_running = False
    await message.channel.send("✅ **Scan finalizado**")

# =====================
# RESCAN ❌
# =====================
async def run_rescan(message, start_date):
    global scan_running, scan_cancelled
    scan_running = True
    scan_cancelled = False

    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    await message.channel.send("🔁 **Re-scan iniciado (❌ apenas)**")

    async for msg in scan_channel.history(after=start_date, oldest_first=True):
        if scan_cancelled:
            break

        if not msg.reactions:
            continue

        # verifica se o bot reagiu com ❌
        has_x = False
        for r in msg.reactions:
            if str(r.emoji) == "❌":
                users = [u async for u in r.users()]
                if client.user in users:
                    has_x = True

        if not has_x:
            continue

        ok = await try_download(msg, download_channel)

        # limpa reações antigas do bot
        for r in msg.reactions:
            if str(r.emoji) in BOT_REACTIONS:
                await msg.remove_reaction(r.emoji, client.user)

        await msg.add_reaction("✅" if ok else "❌")
        await asyncio.sleep(SCAN_DELAY)

    scan_running = False
    await message.channel.send("✅ **Re-scan finalizado**")

# =====================
# COMMANDS
# =====================
@client.event
async def on_message(message):
    global scan_cancelled

    if message.author.bot:
        return

    if message.channel.id != SCAN_CHANNEL_ID:
        return

    if message.content.startswith("!scan"):
        if scan_running:
            await message.channel.send("⚠️ Scan já em andamento.")
            return

        parts = message.content.split(maxsplit=1)
        start = None
        if len(parts) > 1:
            start = parse_br_datetime(parts[1])

        await run_scan(message, start)

    elif message.content.startswith("!rescan"):
        if scan_running:
            await message.channel.send("⚠️ Scan já em andamento.")
            return

        parts = message.content.split(maxsplit=1)
        if len(parts) < 2:
            await message.channel.send("❌ Use: !rescan DD/MM/AAAA HH:MM")
            return

        start = parse_br_datetime(parts[1])
        await run_rescan(message, start)

    elif message.content.startswith("!cancelscan"):
        scan_cancelled = True
        await message.channel.send("🛑 Cancelando…")

# =====================
# START
# =====================
@client.event
async def on_ready():
    print(f"✅ Conectado como {client.user}")

client.run(TOKEN)
