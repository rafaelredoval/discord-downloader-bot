import discord
import os
import re
import asyncio
import subprocess
from datetime import datetime, timezone, timedelta

# =====================
# ENV
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID", "0"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID", "0"))

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não definido")

# =====================
# DISCORD
# =====================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

URL_REGEX = re.compile(r'https?://\S+')
BOT_REACTIONS = ["✅", "❌", "🧐", "💾"]

DOWNLOAD_BASE = "downloads"
MAX_MESSAGES = 500
SLEEP_TIME = 1.2

cancel_flag = False
failed_links = set()
processed_links = set()
long_videos = []

# =====================
# HELPERS
# =====================
def parse_date(arg: str | None):
    if not arg:
        return None

    arg = arg.lower()

    now = datetime.now(timezone.utc)

    if arg == "hoje":
        return now.replace(hour=0, minute=0, second=0)

    if arg == "ontem":
        y = now - timedelta(days=1)
        return y.replace(hour=0, minute=0, second=0)

    for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(arg, fmt).replace(tzinfo=timezone.utc)
        except:
            pass

    raise ValueError("Formato de data inválido")

async def safe_history(channel, after):
    async for msg in channel.history(after=after, limit=None, oldest_first=True):
        yield msg
        await asyncio.sleep(0.35)

# =====================
# DOWNLOAD
# =====================
async def try_download(msg, download_channel):
    urls = URL_REGEX.findall(msg.content)
    if not urls:
        return False

    ok_any = False

    for url in urls:
        if url in processed_links:
            continue

        processed_links.add(url)
        print(f"[DOWNLOAD] {url}")

        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "-o", f"{DOWNLOAD_BASE}/%(title)s.%(ext)s",
                "--max-filesize", "50M",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            if proc.returncode != 0:
                raise RuntimeError("yt-dlp falhou")

            await msg.add_reaction("✅")
            ok_any = True

        except Exception:
            failed_links.add(url)
            await msg.add_reaction("🧐")
            await download_channel.send(f"🧐 Falha no download:\n{url}")

        await asyncio.sleep(SLEEP_TIME)

    return ok_any

# =====================
# SCAN
# =====================
async def run_scan(message, start_date):
    global cancel_flag
    cancel_flag = False

    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    await message.channel.send("🔎 Iniciando varredura…")

    count = 0

    async for msg in safe_history(scan_channel, start_date):
        if cancel_flag:
            break

        if msg.author.bot:
            continue

        await try_download(msg, download_channel)

        count += 1
        if count % 10 == 0:
            print(f"[SCAN] Processadas {count}")

        if count >= MAX_MESSAGES:
            break

    await message.channel.send("✅ Scan finalizado")

# =====================
# DOWNVIDEOS
# =====================
async def run_downvideos(message, start_date):
    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    await message.channel.send("📦 Coletando vídeos…")

    count = 0

    async for msg in safe_history(scan_channel, start_date):
        if msg.attachments:
            for att in msg.attachments:
                if att.content_type and "video" in att.content_type:
                    print(f"[DOWNVIDEOS] {att.filename}")
                    await download_channel.send(file=await att.to_file())
                    await msg.add_reaction("✅")
                    await asyncio.sleep(SLEEP_TIME)

        count += 1
        if count >= MAX_MESSAGES:
            break

    await message.channel.send("✅ downvideos finalizado")

# =====================
# CLEAN
# =====================
async def clean_reactions(message):
    channel = client.get_channel(SCAN_CHANNEL_ID)
    async for msg in channel.history(limit=200):
        for reaction in msg.reactions:
            if reaction.me:
                await reaction.clear()

    await message.channel.send("🧹 Reações do bot removidas")

# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Conectado como {client.user}")

@client.event
async def on_message(message):
    global cancel_flag

    if message.author.bot:
        return

    if not message.content.startswith("!"):
        return

    cmd, *args = message.content.split(maxsplit=1)
    arg = args[0] if args else None

    try:
        if cmd == "!scan":
            await run_scan(message, parse_date(arg))

        elif cmd == "!rescan":
            await run_scan(message, parse_date(arg))

        elif cmd == "!downvideos":
            await run_downvideos(message, parse_date(arg))

        elif cmd == "!botlimpar":
            await clean_reactions(message)

        elif cmd == "!cancelgeral":
            cancel_flag = True
            await message.channel.send("⛔ Scan cancelado")

    except Exception as e:
        await message.channel.send(f"❌ Erro: {e}")
        print(e)

# =====================
# START
# =====================
client.run(TOKEN)
