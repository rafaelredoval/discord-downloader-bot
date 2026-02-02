import discord
import os
import re
import asyncio
from datetime import datetime, timezone

# =====================
# ENV VARS
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID", 0))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID", 0))

if not TOKEN or not SCAN_CHANNEL_ID or not DOWNLOAD_CHANNEL_ID:
    raise RuntimeError("❌ Variáveis de ambiente não configuradas")

# =====================
# DISCORD CONFIG
# =====================
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

# =====================
# GLOBALS
# =====================
URL_REGEX = re.compile(r"https?://\S+")
DOWNLOAD_BASE = "downloads"

scan_running = False
scan_cancelled = False
processed_links = set()

# =====================
# yt-dlp async
# =====================
async def run_yt_dlp(url, output_path):
    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--no-playlist",
        "-o", output_path,
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stderr.decode()

# =====================
# LOAD PROCESSED LINKS
# =====================
async def load_processed_links(download_channel):
    processed_links.clear()

    async for msg in download_channel.history(limit=None):
        if msg.content:
            urls = URL_REGEX.findall(msg.content)
            for url in urls:
                processed_links.add(url)

    print(f"🔁 {len(processed_links)} links já processados")

# =====================
# PROCESS MESSAGE
# =====================
async def process_message(message, download_channel):
    urls = URL_REGEX.findall(message.content)
    if not urls:
        return 0

    success = 0
    user_id = str(message.author.id)
    date_folder = message.created_at.strftime("%Y-%m-%d")

    for url in urls:
        if scan_cancelled:
            break

        if url in processed_links:
            await message.add_reaction("♻️")
            continue

        folder = os.path.join(
            DOWNLOAD_BASE,
            user_id,
            date_folder,
            str(abs(hash(url)))
        )
        os.makedirs(folder, exist_ok=True)

        code, err = await run_yt_dlp(
            url,
            f"{folder}/%(title)s.%(ext)s"
        )

        if code != 0:
            print("❌ yt-dlp erro:", err)
            await message.add_reaction("❌")
            continue

        for file in os.listdir(folder):
            path = os.path.join(folder, file)
            if os.path.isfile(path):
                await download_channel.send(
                    content=f"📦 <@{user_id}> {url}",
                    file=discord.File(path)
                )
                os.remove(path)

        processed_links.add(url)
        await message.add_reaction("✅")
        success += 1

        await asyncio.sleep(2)  # ↓↓↓ diminui chance de 429

    return success

# =====================
# SCAN
# =====================
async def run_scan(ctx):
    global scan_running, scan_cancelled

    scan_running = True
    scan_cancelled = False

    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    await load_processed_links(download_channel)

    await ctx.channel.send(
        f"🔍 Scan iniciado — ignorando {len(processed_links)} links duplicados"
    )

    total = 0

    async for msg in scan_channel.history(limit=None, oldest_first=True):
        if scan_cancelled:
            break
        if msg.author.bot:
            continue

        total += await process_message(msg, download_channel)

    scan_running = False

    if scan_cancelled:
        await ctx.channel.send("⛔ Scan cancelado")
    else:
        await ctx.channel.send(f"✅ Scan finalizado — {total} novos downloads")

# =====================
# CLEAN REACTIONS
# =====================
async def clean_reactions(channel):
    async for msg in channel.history(limit=None):
        for reaction in msg.reactions:
            if reaction.me:
                try:
                    await reaction.clear()
                except:
                    pass

# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Bot conectado como {client.user}")

@client.event
async def on_message(message):
    global scan_cancelled

    if message.author.bot:
        return
    if message.channel.id != SCAN_CHANNEL_ID:
        return

    content = message.content.lower().strip()

    if content == "!scan":
        if scan_running:
            await message.channel.send("⚠️ Scan já em execução")
            return
        await run_scan(message)

    elif content == "!cancelscan":
        scan_cancelled = True
        await message.channel.send("⛔ Cancelando scan...")

    elif content == "!botlimpar":
        await message.channel.send("🧹 Limpando reações...")
        await clean_reactions(message.channel)
        await message.channel.send("✅ Reações removidas")

# =====================
# START
# =====================
client.run(TOKEN)
