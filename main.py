import os
import re
import asyncio
import subprocess
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone

# ========= CONFIG =========

TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))
DESTINATION_CHANNEL_ID = int(os.getenv("DESTINATION_CHANNEL_ID"))

DOWNLOAD_BASE = "./downloads"
MAX_DISCORD_FILE_MB = 25

URL_REGEX = re.compile(r"(https?://\S+)")

os.makedirs(DOWNLOAD_BASE, exist_ok=True)

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========= CONTROLE =========

scan_running = False
cancel_scan = False

failed_links = []
long_videos = []

# ========= UTIL =========

def brasilia_now():
    return datetime.now(timezone(timedelta(hours=-3)))

def parse_date_arg(arg: str | None):
    if not arg:
        return None

    now = brasilia_now()

    if arg.lower() == "hoje":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    if arg.lower() == "ontem":
        d = now - timedelta(days=1)
        return d.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        return datetime.strptime(arg, "%d/%m/%Y %H:%M").replace(
            tzinfo=timezone(timedelta(hours=-3))
        )
    except:
        return None

async def safe_sleep():
    await asyncio.sleep(0.6)

# ========= DOWNLOAD =========

async def try_download(msg: discord.Message, download_channel):
    urls = URL_REGEX.findall(msg.content)
    if not urls:
        return False

    for url in urls:
        folder = os.path.join(DOWNLOAD_BASE, str(msg.id))
        os.makedirs(folder, exist_ok=True)

        try:
            proc = subprocess.run(
                ["yt-dlp", "-o", f"{folder}/%(title)s.%(ext)s", url],
                capture_output=True
            )

            if proc.returncode != 0:
                failed_links.append(url)
                await msg.add_reaction("🧐")
                await download_channel.send(url)
                return False

            for file in os.listdir(folder):
                path = os.path.join(folder, file)
                size_mb = os.path.getsize(path) / (1024 * 1024)

                if size_mb > MAX_DISCORD_FILE_MB:
                    long_videos.append(url)
                    await msg.add_reaction("💾")
                    await download_channel.send(url)
                    return False

                await download_channel.send(
                    file=discord.File(path),
                    content=f"📦 Enviado por <@{msg.author.id}>"
                )
                os.remove(path)

            await msg.add_reaction("✅")
            return True

        except Exception:
            failed_links.append(url)
            await msg.add_reaction("🧐")
            await download_channel.send(url)
            return False

# ========= SCAN =========

async def run_scan(ctx, date_filter=None):
    global scan_running, cancel_scan

    if scan_running:
        await ctx.send("⚠️ Já existe um scan em execução.")
        return

    scan_running = True
    cancel_scan = False

    channel = bot.get_channel(SCAN_CHANNEL_ID)
    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)

    await ctx.send("🔍 Iniciando varredura...")

    async for msg in channel.history(limit=None, oldest_first=True):
        if cancel_scan:
            break

        if msg.author.bot:
            continue

        if date_filter and msg.created_at < date_filter.astimezone(timezone.utc):
            continue

        await try_download(msg, download_channel)
        await safe_sleep()

    await ctx.send("✅ Scan finalizado.")
    scan_running = False

# ========= COMANDOS =========

@bot.command()
async def scan(ctx, *, arg=None):
    if ctx.channel.id != SCAN_CHANNEL_ID:
        return

    date_filter = parse_date_arg(arg)
    await run_scan(ctx, date_filter)

@bot.command()
async def cancelscan(ctx):
    global cancel_scan
    cancel_scan = True
    await ctx.send("⛔ Scan cancelado.")

@bot.command()
async def botlimpar(ctx):
    channel = bot.get_channel(SCAN_CHANNEL_ID)
    count = 0

    async for msg in channel.history(limit=300):
        for reaction in msg.reactions:
            if reaction.me:
                await reaction.clear()
                count += 1
        await safe_sleep()

    await ctx.send(f"🧹 {count} reações do bot removidas.")

@bot.command()
async def downvideos(ctx, *, arg=None):
    date_filter = parse_date_arg(arg)
    source = bot.get_channel(SCAN_CHANNEL_ID)
    dest = bot.get_channel(DESTINATION_CHANNEL_ID)

    async for msg in source.history(limit=None, oldest_first=True):
        if msg.attachments:
            if date_filter and msg.created_at < date_filter.astimezone(timezone.utc):
                continue

            for att in msg.attachments:
                await dest.send(att.url)
                await msg.add_reaction("✅")
                await safe_sleep()

# ========= READY =========

@bot.event
async def on_ready():
    print(f"✅ Logado como {bot.user}")

# ========= START =========

bot.run(TOKEN)
