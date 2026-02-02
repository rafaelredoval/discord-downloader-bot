import discord
import os
import re
import asyncio

# =====================
# ENV
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID", 0))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID", 0))

if not TOKEN or not SCAN_CHANNEL_ID or not DOWNLOAD_CHANNEL_ID:
    raise RuntimeError("❌ Variáveis de ambiente ausentes")

# =====================
# DISCORD
# =====================
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

# =====================
# CONSTANTES
# =====================
URL_REGEX = re.compile(r"https?://\S+")
DOWNLOAD_BASE = "downloads"
DISCORD_FILE_LIMIT = 8 * 1024 * 1024  # 8MB

scan_running = False
scan_cancelled = False
processed_links = set()

# =====================
# yt-dlp
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
    _, stderr = await process.communicate()
    return process.returncode, stderr.decode()

# =====================
# LOAD LINKS
# =====================
async def load_processed_links(channel):
    processed_links.clear()
    async for msg in channel.history(limit=None):
        if msg.content:
            for url in URL_REGEX.findall(msg.content):
                processed_links.add(url)

# =====================
# PROCESS MSG
# =====================
async def process_message(message, download_channel):
    urls = URL_REGEX.findall(message.content)
    if not urls:
        return 0

    success = 0
    user_id = message.author.id

    for url in urls:
        if scan_cancelled:
            break

        if url in processed_links:
            await message.add_reaction("♻️")
            continue

        folder = os.path.join(
            DOWNLOAD_BASE,
            str(user_id),
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
            if not os.path.isfile(path):
                continue

            size = os.path.getsize(path)

            if size > DISCORD_FILE_LIMIT:
                await download_channel.send(
                    f"⚠️ Arquivo grande demais ({size//1024//1024}MB)\n"
                    f"👤 <@{user_id}>\n🔗 {url}"
                )
                await message.add_reaction("⚠️")
            else:
                await download_channel.send(
                    content=f"📦 <@{user_id}> {url}",
                    file=discord.File(path)
                )
                await message.add_reaction("✅")

            os.remove(path)

        processed_links.add(url)
        success += 1
        await asyncio.sleep(2)

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
        f"🔍 Scan iniciado ({len(processed_links)} links ignorados)"
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
        await ctx.channel.send(f"✅ Scan finalizado — {total} novos")

# =====================
# CLEAN
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
    print(f"✅ Conectado como {client.user}")

@client.event
async def on_message(message):
    global scan_cancelled

    if message.author.bot:
        return
    if message.channel.id != SCAN_CHANNEL_ID:
        return

    cmd = message.content.lower().strip()

    if cmd == "!scan":
        if scan_running:
            await message.channel.send("⚠️ Scan já em execução")
            return
        await run_scan(message)

    elif cmd == "!cancelscan":
        scan_cancelled = True
        await message.channel.send("⛔ Cancelando scan")

    elif cmd == "!botlimpar":
        await message.channel.send("🧹 Limpando reações...")
        await clean_reactions(message.channel)
        await message.channel.send("✅ Limpo")

# =====================
# START
# =====================
client.run(TOKEN)
