import discord
import os
import re
import asyncio
import subprocess
from datetime import datetime, timedelta, timezone

# =====================
# ENV
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não definido")

# =====================
# DISCORD
# =====================
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

# =====================
# CONFIG
# =====================
URL_REGEX = re.compile(r"https?://\S+")
DOWNLOAD_BASE = "downloads"
MAX_DISCORD_FILE_MB = 25

failed_links = set()
long_videos = set()
cancel_scan = False

# =====================
# DATE PARSER
# =====================
def parse_date_arg(arg):
    if not arg:
        return None

    arg = arg.lower().strip()
    now = datetime.now(timezone.utc)

    if arg == "hoje":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    if arg == "ontem":
        y = now - timedelta(days=1)
        return y.replace(hour=0, minute=0, second=0, microsecond=0)

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(arg, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    raise ValueError("Formato inválido de data")

# =====================
# DOWNLOAD
# =====================
async def try_download(message, url, download_channel):
    global failed_links, long_videos

    folder = os.path.join(
        DOWNLOAD_BASE,
        str(message.author.id),
        message.created_at.strftime("%Y-%m-%d"),
        str(abs(hash(url))),
    )
    os.makedirs(folder, exist_ok=True)

    status = await download_channel.send(f"⏳ Baixando:\n{url}")

    try:
        proc = subprocess.run(
            [
                "yt-dlp",
                "--print", "filesize",
                "-o", f"{folder}/%(title)s.%(ext)s",
                url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        for file in os.listdir(folder):
            path = os.path.join(folder, file)
            size_mb = os.path.getsize(path) / 1024 / 1024

            if size_mb > MAX_DISCORD_FILE_MB:
                long_videos.add(url)
                await message.add_reaction("💾")
                await download_channel.send(f"💾 Vídeo longo:\n{url}")
                os.remove(path)
                await status.edit(content="⚠️ Vídeo maior que limite")
                return False

            await download_channel.send(
                file=discord.File(path),
                content=f"📦 Enviado por <@{message.author.id}>"
            )
            os.remove(path)

        await message.add_reaction("✅")
        await status.edit(content="✅ Download concluído")
        return True

    except Exception:
        failed_links.add(url)
        await message.add_reaction("🧐")
        await download_channel.send(f"🧐 Falha ao baixar:\n{url}")
        await status.edit(content="❌ Falha no download")
        return False

# =====================
# SCAN
# =====================
async def run_scan(ctx_message, start_date):
    global cancel_scan
    cancel_scan = False

    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    await ctx_message.channel.send("🔎 Scan iniciado")

    async for msg in scan_channel.history(limit=None, oldest_first=True):
        if cancel_scan:
            await ctx_message.channel.send("⛔ Scan cancelado")
            return

        if start_date and msg.created_at < start_date:
            continue

        urls = URL_REGEX.findall(msg.content)
        for url in urls:
            await try_download(msg, url, download_channel)
            await asyncio.sleep(1.5)

    await ctx_message.channel.send(
        f"✅ Scan finalizado\n"
        f"❌ Falhas: {len(failed_links)}\n"
        f"💾 Vídeos longos: {len(long_videos)}"
    )

# =====================
# RESCAN
# =====================
async def run_rescan(ctx_message):
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    if not failed_links:
        await ctx_message.channel.send("Nenhum link para re-scan")
        return

    await ctx_message.channel.send("🔁 Re-scan iniciado")

    for url in list(failed_links):
        fake_msg = ctx_message
        ok = await try_download(fake_msg, url, download_channel)
        if ok:
            failed_links.discard(url)
        await asyncio.sleep(2)

    await ctx_message.channel.send("✅ Re-scan finalizado")

# =====================
# CLEAN
# =====================
async def clean_reactions(channel):
    async for msg in channel.history(limit=200):
        for reaction in msg.reactions:
            if reaction.me:
                await reaction.clear()

# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Conectado como {client.user}")

@client.event
async def on_message(message):
    global cancel_scan

    if message.author.bot:
        return

    content = message.content.lower().strip()

    if content.startswith("!scan"):
        arg = content.replace("!scan", "").strip()
        start = None
        if arg:
            try:
                start = parse_date_arg(arg)
            except ValueError as e:
                await message.channel.send(f"❌ {e}")
                return
        await run_scan(message, start)

    elif content.startswith("!rescan"):
        await run_rescan(message)

    elif content.startswith("!cancelscan"):
        cancel_scan = True

    elif content.startswith("!botlimpar"):
        await clean_reactions(message.channel)
        await message.channel.send("🧹 Reações do bot removidas")

# =====================
# START
# =====================
client.run(TOKEN)
