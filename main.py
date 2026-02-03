import discord
import os
import re
import subprocess
import asyncio
from datetime import datetime, timedelta, timezone

# =====================
# ENV VARS
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = os.getenv("SCAN_CHANNEL_ID")
DOWNLOAD_CHANNEL_ID = os.getenv("DOWNLOAD_CHANNEL_ID")

if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN não definido")
if not SCAN_CHANNEL_ID:
    raise RuntimeError("❌ SCAN_CHANNEL_ID não definido")
if not DOWNLOAD_CHANNEL_ID:
    raise RuntimeError("❌ DOWNLOAD_CHANNEL_ID não definido")

SCAN_CHANNEL_ID = int(SCAN_CHANNEL_ID)
DOWNLOAD_CHANNEL_ID = int(DOWNLOAD_CHANNEL_ID)

# =====================
# DISCORD CONFIG
# =====================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# =====================
# GLOBALS
# =====================
URL_REGEX = re.compile(r'https?://\S+')
DOWNLOAD_BASE = "downloads"
SCAN_DELAY = 1.5  # 🔥 anti rate-limit
scan_running = False
scan_cancelled = False
downloaded_urls = set()

# =====================
# UTILS
# =====================
def parse_date(arg: str | None):
    now = datetime.now(timezone.utc)

    if not arg:
        return None

    arg = arg.lower()

    if arg == "hoje":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    if arg == "ontem":
        d = now - timedelta(days=1)
        return d.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        return datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# =====================
# DOWNLOAD LOGIC
# =====================
async def process_message(msg, download_channel):
    if msg.author.bot:
        return

    urls = URL_REGEX.findall(msg.content)
    if not urls:
        return

    for url in urls:
        if url in downloaded_urls:
            continue

        user_id = str(msg.author.id)
        date_folder = msg.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        safe_name = str(abs(hash(url)))

        folder = os.path.join(DOWNLOAD_BASE, user_id, date_folder, safe_name)
        os.makedirs(folder, exist_ok=True)

        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "-o",
                f"{folder}/%(title)s.%(ext)s",
                url
            )
            await proc.communicate()

            if proc.returncode != 0:
                await msg.add_reaction("❌")
                continue

            sent = 0
            for file in os.listdir(folder):
                path = os.path.join(folder, file)
                if os.path.isfile(path):
                    await download_channel.send(
                        content=f"📦 <@{user_id}>",
                        file=discord.File(path)
                    )
                    os.remove(path)
                    sent += 1

            if sent > 0:
                downloaded_urls.add(url)
                await msg.add_reaction("✅")
            else:
                await msg.add_reaction("❌")

        except Exception as e:
            print("Erro download:", e)
            await msg.add_reaction("❌")


# =====================
# SCAN
# =====================
async def run_scan(message, date_filter):
    global scan_running, scan_cancelled

    scan_running = True
    scan_cancelled = False

    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    if not scan_channel or not download_channel:
        await message.channel.send("❌ Canal inválido.")
        scan_running = False
        return

    await message.channel.send("🔍 **Scan iniciado…**")

    async for msg in scan_channel.history(
        after=date_filter,
        oldest_first=True,
        limit=None
    ):
        if scan_cancelled:
            await message.channel.send("🛑 Scan cancelado.")
            break

        await process_message(msg, download_channel)

        # 🔥 PROTEÇÃO RATE LIMIT
        await asyncio.sleep(SCAN_DELAY)

    await message.channel.send("✅ **Scan finalizado**")
    scan_running = False


# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Conectado como {client.user}")


@client.event
async def on_message(message):
    global scan_cancelled

    if message.author.bot:
        return

    if message.channel.id != SCAN_CHANNEL_ID:
        return

    if message.content.startswith("!scan"):
        if scan_running:
            await message.channel.send("⚠️ Já existe um scan em andamento.")
            return

        args = message.content.split()
        date_arg = args[1] if len(args) > 1 else None
        date_filter = parse_date(date_arg)

        await run_scan(message, date_filter)

    elif message.content.startswith("!cancelscan"):
        scan_cancelled = True
        await message.channel.send("🛑 Cancelando scan…")


# =====================
# START
# =====================
client.run(TOKEN)
