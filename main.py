import discord
import os
import re
import subprocess
from datetime import datetime, timezone
import asyncio

# =====================
# ENV VARS
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = os.getenv("SCAN_CHANNEL_ID")
DOWNLOAD_CHANNEL_ID = os.getenv("DOWNLOAD_CHANNEL_ID")
POST_CHANNEL_ID = os.getenv("POST_CHANNEL_ID")
START_DATE_STR = os.getenv("START_DATE")

if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN não definido")
if not SCAN_CHANNEL_ID:
    raise RuntimeError("❌ SCAN_CHANNEL_ID não definido")
if not DOWNLOAD_CHANNEL_ID:
    raise RuntimeError("❌ DOWNLOAD_CHANNEL_ID não definido")
if not POST_CHANNEL_ID:
    raise RuntimeError("❌ POST_CHANNEL_ID não definido")

SCAN_CHANNEL_ID = int(SCAN_CHANNEL_ID)
DOWNLOAD_CHANNEL_ID = int(DOWNLOAD_CHANNEL_ID)
POST_CHANNEL_ID = int(POST_CHANNEL_ID)

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
client = discord.Client(intents=intents)

URL_REGEX = re.compile(r"https?://\S+")
DOWNLOAD_BASE = "downloads"

# =====================
# SCAN CONTROL
# =====================
scan_running = False
scan_cancelled = False

# =====================
# HELPERS
# =====================
def parse_date_from_command(content):
    parts = content.split()
    for p in parts:
        try:
            return datetime.strptime(p, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return DEFAULT_START_DATE

# =====================
# CORE PROCESS
# =====================
async def process_message(message, download_channel, create_thread=False):
    global scan_cancelled

    if scan_cancelled:
        return None

    if message.author.bot:
        return None

    if message.reactions:
        return None

    urls = URL_REGEX.findall(message.content)
    if not urls:
        return None

    user_id = str(message.author.id)
    date_folder = message.created_at.strftime("%Y-%m-%d")

    thread = None
    if create_thread:
        thread = await download_channel.create_thread(
            name=f"{message.author.name}",
            auto_archive_duration=1440
        )

    target = thread if thread else download_channel

    success = 0
    fail = 0

    for url in urls:
        if scan_cancelled:
            break

        safe_name = str(abs(hash(url)))
        folder = os.path.join(DOWNLOAD_BASE, user_id, date_folder, safe_name)
        os.makedirs(folder, exist_ok=True)

        status = await target.send(f"⏳ Baixando:\n{url}")

        try:
            subprocess.run(
                ["yt-dlp", "-o", f"{folder}/%(title)s.%(ext)s", url],
                check=True
            )

            sent = False
            for f in os.listdir(folder):
                path = os.path.join(folder, f)
                if os.path.isfile(path):
                    await target.send(file=discord.File(path))
                    os.remove(path)
                    sent = True

            if sent:
                await message.add_reaction("✅")
                await status.edit(content="✅ Concluído")
                success += 1
            else:
                await message.add_reaction("❌")
                await status.edit(content="⚠️ Nenhum arquivo")
                fail += 1

        except Exception as e:
            await message.add_reaction("❌")
            await status.edit(content="❌ Erro no download")
            print(e)
            fail += 1

    return success, fail, message.author.name

# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Conectado como {client.user}")

@client.event
async def on_message(message):
    global scan_running, scan_cancelled

    if message.author.bot:
        return

    if message.channel.id != SCAN_CHANNEL_ID:
        return

    # -----------------
    # CANCEL SCAN
    # -----------------
    if message.content.startswith("!cancelscan"):
        if not scan_running:
            await message.channel.send("⚠️ Nenhum scan em andamento.")
            return

        scan_cancelled = True
        await message.channel.send("🛑 **Scan cancelado pelo usuário**")
        return

    # -----------------
    # START SCAN
    # -----------------
    if not message.content.startswith("!scan"):
        return

    if scan_running:
        await message.channel.send("⚠️ Já existe um scan em andamento.")
        return

    scan_running = True
    scan_cancelled = False

    create_thread = "post" in message.content
    start_date = parse_date_from_command(message.content)

    await message.channel.send(
        f"🔎 Scan iniciado a partir de {start_date.date()}"
    )

    summary = {}

    try:
        for guild in client.guilds:
            for channel in guild.text_channels:
                async for msg in channel.history(
                    after=start_date, oldest_first=True
                ):
                    if scan_cancelled:
                        break

                    result = await process_message(
                        msg,
                        client.get_channel(
                            POST_CHANNEL_ID if create_thread else DOWNLOAD_CHANNEL_ID
                        ),
                        create_thread=create_thread
                    )

                    if result:
                        ok, fail, user = result
                        summary.setdefault(user, 0)
                        summary[user] += ok

                if scan_cancelled:
                    break

    finally:
        scan_running = False

    if scan_cancelled:
        await message.channel.send("🛑 Scan interrompido.")
        return

    report = "**📊 RESUMO FINAL**\n"
    for user, count in summary.items():
        report += f"👤 {user}: {count} arquivos\n"

    await message.channel.send(report)

# =====================
# START
# =====================
client.run(TOKEN)
