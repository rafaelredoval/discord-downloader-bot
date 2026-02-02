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
START_DATE_STR = os.getenv("START_DATE")  # opcional

if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN não definido")

if not SCAN_CHANNEL_ID:
    raise RuntimeError("❌ SCAN_CHANNEL_ID não definido")

if not DOWNLOAD_CHANNEL_ID:
    raise RuntimeError("❌ DOWNLOAD_CHANNEL_ID não definido")

# START_DATE padrão
if START_DATE_STR:
    DEFAULT_START_DATE = datetime.strptime(
        START_DATE_STR, "%Y-%m-%d"
    ).replace(tzinfo=timezone.utc)
else:
    DEFAULT_START_DATE = datetime(1970, 1, 1, tzinfo=timezone.utc)

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
scan_cancelled = False
scan_running = False

# =====================
# yt-dlp ASYNC
# =====================
async def run_yt_dlp(url, output_path):
    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-o",
        output_path,
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode(), stderr.decode()

# =====================
# BOT READY
# =====================
@client.event
async def on_ready():
    print(f"✅ Bot conectado como {client.user}")
    print(f"📥 Canal Scan: {SCAN_CHANNEL_ID}")
    print(f"📤 Canal Download: {DOWNLOAD_CHANNEL_ID}")

# =====================
# PROCESS MESSAGE
# =====================
async def process_message(message, download_channel):
    urls = URL_REGEX.findall(message.content)
    if not urls:
        return 0

    user_id = str(message.author.id)
    date_folder = message.created_at.strftime("%Y-%m-%d")
    success_count = 0

    for url in urls:
        if scan_cancelled:
            break

        safe_name = str(abs(hash(url)))
        download_folder = os.path.join(
            DOWNLOAD_BASE, user_id, date_folder, safe_name
        )
        os.makedirs(download_folder, exist_ok=True)

        try:
            code, _, err = await run_yt_dlp(
                url,
                f"{download_folder}/%(title)s.%(ext)s"
            )

            if code != 0:
                raise Exception(err)

            await message.add_reaction("✅")

            for file in os.listdir(download_folder):
                path = os.path.join(download_folder, file)
                if os.path.isfile(path):
                    await download_channel.send(
                        content=f"📦 <@{user_id}>",
                        file=discord.File(path)
                    )
                    os.remove(path)

            success_count += 1

        except Exception as e:
            print("❌ Erro:", e)
            await message.add_reaction("❌")

    return success_count

# =====================
# SCAN FUNCTION
# =====================
async def run_scan(ctx_message, start_date):
    global scan_running, scan_cancelled
    scan_running = True
    scan_cancelled = False

    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    await ctx_message.channel.send(
        f"🔍 **Scan iniciado** a partir de `{start_date.date()}`"
    )

    total_downloads = 0

    async for message in scan_channel.history(
        after=start_date,
        oldest_first=True,
        limit=None
    ):
        if scan_cancelled:
            break

        if message.author.bot:
            continue

        total_downloads += await process_message(message, download_channel)

    scan_running = False

    if scan_cancelled:
        await ctx_message.channel.send("⛔ **Scan cancelado**")
    else:
        await ctx_message.channel.send(
            f"✅ **Scan finalizado** — {total_downloads} downloads"
        )

# =====================
# CLEAN BOT REACTIONS
# =====================
async def clean_reactions(channel):
    async for message in channel.history(limit=None):
        for reaction in message.reactions:
            if reaction.me:
                try:
                    await reaction.clear()
                except:
                    pass

# =====================
# COMMAND HANDLER
# =====================
@client.event
async def on_message(message):
    global scan_cancelled

    if message.author.bot:
        return

    if message.channel.id != SCAN_CHANNEL_ID:
        return

    content = message.content.strip().lower()

    # !scan [data]
    if content.startswith("!scan"):
        if scan_running:
            await message.channel.send("⚠️ Scan já está em execução")
            return

        parts = content.split()
        if len(parts) == 2:
            try:
                start_date = datetime.strptime(
                    parts[1], "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)
            except:
                await message.channel.send("❌ Use: !scan YYYY-MM-DD")
                return
        else:
            start_date = DEFAULT_START_DATE

        await run_scan(message, start_date)

    # !cancelscan
    elif content == "!cancelscan":
        if scan_running:
            scan_cancelled = True
            await message.channel.send("⛔ Cancelando scan…")
        else:
            await message.channel.send("ℹ️ Nenhum scan em execução")

    # !botlimpar
    elif content == "!botlimpar":
        await message.channel.send("🧹 Limpando reações do bot…")
        await clean_reactions(message.channel)
        await message.channel.send("✅ Reações removidas")

# =====================
# START BOT
# =====================
client.run(TOKEN)
