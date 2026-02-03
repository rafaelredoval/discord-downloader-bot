import os
import re
import asyncio
import subprocess
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))

URL_REGEX = re.compile(r"(https?://\S+)")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

DOWNLOAD_BASE = "downloads"

FAILED_LINKS = {}   # url -> metadata
DOWNLOADED_URLS = set()

BRAZIL_TZ = timezone(timedelta(hours=-3))

def parse_datetime(date_str, time_str):
    dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
    return dt.replace(tzinfo=BRAZIL_TZ)

async def try_download(url, message, download_channel):
    user_id = str(message.author.id)
    date_folder = message.created_at.astimezone(BRAZIL_TZ).strftime("%Y-%m-%d")
    safe_name = str(abs(hash(url)))

    folder = os.path.join(DOWNLOAD_BASE, user_id, date_folder, safe_name)
    os.makedirs(folder, exist_ok=True)

    try:
        subprocess.run(
            ["yt-dlp", "-o", f"{folder}/%(title)s.%(ext)s", url],
            check=True,
            timeout=900
        )

        sent = False
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path):
                await download_channel.send(
                    content=f"📦 <@{user_id}>",
                    file=discord.File(path)
                )
                os.remove(path)
                sent = True

        if sent:
            await message.add_reaction("✅")
            DOWNLOADED_URLS.add(url)
            FAILED_LINKS.pop(url, None)
            return True

        raise RuntimeError("Nenhum arquivo gerado")

    except subprocess.TimeoutExpired:
        await message.add_reaction("💾")
    except Exception:
        await message.add_reaction("🧐")

    FAILED_LINKS[url] = {
        "message_id": message.id,
        "channel_id": message.channel.id,
        "author_id": user_id,
        "created_at": message.created_at
    }

    await download_channel.send(f"🔍 Falha no download:\n{url}")
    return False

# ---------------- COMMANDS ---------------- #

@bot.command()
async def scan(ctx, *, arg=None):
    if ctx.channel.id != SCAN_CHANNEL_ID:
        return

    date_filter = None

    if arg:
        if arg.lower() == "hoje":
            date_filter = datetime.now(BRAZIL_TZ).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif arg.lower() == "ontem":
            date_filter = datetime.now(BRAZIL_TZ).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=1)
        else:
            try:
                d, t = arg.split()
                date_filter = parse_datetime(d, t)
            except Exception:
                await ctx.send("❌ Use: !scan hoje | ontem | DD/MM/AAAA HH:MM")
                return

    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    await ctx.send("🔍 Iniciando varredura...")

    async for msg in ctx.channel.history(limit=None, oldest_first=True):
        if date_filter and msg.created_at < date_filter:
            continue

        urls = URL_REGEX.findall(msg.content)
        for url in urls:
            if url in DOWNLOADED_URLS:
                continue

            await try_download(url, msg, download_channel)
            await asyncio.sleep(1.2)

    await ctx.send("✅ Scan finalizado.")

@bot.command()
async def rescan(ctx, date: str, time: str):
    if ctx.channel.id != SCAN_CHANNEL_ID:
        return

    start = parse_datetime(date, time)
    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)

    await ctx.send("🔁 Re-scan iniciado (somente falhas)...")

    for url, meta in list(FAILED_LINKS.items()):
        if meta["created_at"] < start:
            continue

        channel = bot.get_channel(meta["channel_id"])
        if not channel:
            continue

        try:
            msg = await channel.fetch_message(meta["message_id"])
        except:
            continue

        await try_download(url, msg, download_channel)
        await asyncio.sleep(1.5)

    await ctx.send("✅ Re-scan concluído.")

# ---------------- EVENTS ---------------- #

@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")

bot.run(TOKEN)
