import discord
import os
import re
import subprocess
import asyncio
from datetime import datetime, timezone

# =====================
# ENV VARS
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = os.getenv("SCAN_CHANNEL_ID")
DOWNLOAD_CHANNEL_ID = os.getenv("DOWNLOAD_CHANNEL_ID")
START_DATE_ENV = os.getenv("START_DATE", "1970-01-01")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não definido")
if not SCAN_CHANNEL_ID:
    raise RuntimeError("SCAN_CHANNEL_ID não definido")
if not DOWNLOAD_CHANNEL_ID:
    raise RuntimeError("DOWNLOAD_CHANNEL_ID não definido")

SCAN_CHANNEL_ID = int(SCAN_CHANNEL_ID)
DOWNLOAD_CHANNEL_ID = int(DOWNLOAD_CHANNEL_ID)

START_DATE_DEFAULT = datetime.strptime(
    START_DATE_ENV, "%Y-%m-%d"
).replace(tzinfo=timezone.utc)

# =====================
# DISCORD CONFIG
# =====================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.reactions = True

client = discord.Client(intents=intents)

# =====================
# GLOBALS
# =====================
URL_REGEX = re.compile(r'https?://\S+')
DOWNLOAD_BASE = "downloads"
scan_cancelled = False

# =====================
# HELPERS
# =====================
def parse_date(arg):
    try:
        return datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Conectado como {client.user}")

# =====================
# SCAN CORE
# =====================
async def run_scan(
    channel,
    after_date,
    create_thread=False
):
    global scan_cancelled
    scan_cancelled = False

    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)
    summary = {}
    total_seconds = 0

    await channel.send(f"🔍 **Scan iniciado a partir de {after_date.date()}**")

    async for message in channel.history(after=after_date, oldest_first=True):
        if scan_cancelled:
            await channel.send("⛔ Scan cancelado.")
            return

        if message.author.bot:
            continue

        if message.reactions:
            continue

        urls = URL_REGEX.findall(message.content)
        if not urls:
            continue

        for url in urls:
            user = message.author
            user_id = str(user.id)

            safe = str(abs(hash(url)))
            folder = os.path.join(DOWNLOAD_BASE, user_id, safe)
            os.makedirs(folder, exist_ok=True)

            target_channel = download_channel

            if create_thread:
                thread = await download_channel.create_thread(
                    name=f"{user.display_name}",
                    auto_archive_duration=1440
                )
                target_channel = thread

            status = await target_channel.send(
                f"⏳ **Baixando**\n🔗 {url}\n👤 {user.mention}"
            )

            try:
                result = subprocess.run(
                    [
                        "yt-dlp",
                        "--print",
                        "duration",
                        "-o",
                        f"{folder}/%(title)s.%(ext)s",
                        url
                    ],
                    capture_output=True,
                    text=True
                )

                duration = result.stdout.strip()
                if duration.isdigit():
                    total_seconds += int(duration)

                subprocess.run(
                    [
                        "yt-dlp",
                        "-o",
                        f"{folder}/%(title)s.%(ext)s",
                        url
                    ],
                    check=True
                )

                sent = 0
                for f in os.listdir(folder):
                    path = os.path.join(folder, f)
                    await target_channel.send(
                        file=discord.File(path)
                    )
                    os.remove(path)
                    sent += 1

                await message.add_reaction("✅")
                await status.edit(
                    content=f"✅ **Concluído ({sent} arquivo(s))**"
                )

                summary[user.display_name] = summary.get(
                    user.display_name, 0
                ) + sent

            except Exception as e:
                await message.add_reaction("❌")
                await status.edit(content="❌ **Erro ao baixar**")
                print(e)

    # =====================
    # FINAL SUMMARY
    # =====================
    total_time = str(datetime.utcfromtimestamp(total_seconds).time())

    report = "📊 **Resumo do Scan**\n"
    for user, count in summary.items():
        report += f"• {user}: {count} arquivo(s)\n"

    report += f"\n⏱️ **Duração total dos vídeos:** {total_time}"

    await channel.send(report)

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

    args = message.content.lower().split()

    # !scan
    if args[0] == "!scan":
        date = parse_date(args[1]) if len(args) > 1 else START_DATE_DEFAULT
        if not date:
            await message.channel.send("❌ Data inválida. Use YYYY-MM-DD")
            return
        await run_scan(message.channel, date)
        return

    # !scan post
    if args[:2] == ["!scan", "post"]:
        date = parse_date(args[2]) if len(args) > 2 else START_DATE_DEFAULT
        if not date:
            await message.channel.send("❌ Data inválida.")
            return
        await run_scan(message.channel, date, create_thread=True)
        return

    # !cancelscan
    if message.content.lower() == "!cancelscan":
        scan_cancelled = True
        await message.channel.send("⛔ Cancelando scan…")
        return

    # !limpar scan
    if message.content.lower() == "!limpar scan":
        removed = 0
        async for msg in message.channel.history(limit=300):
            if not URL_REGEX.search(msg.content):
                continue
            for reaction in msg.reactions:
                async for user in reaction.users():
                    if user.id == client.user.id:
                        await reaction.remove(user)
                        removed += 1
        await message.channel.send(
            f"🧹 Limpeza concluída — {removed} reações removidas"
        )

# =====================
# START
# =====================
client.run(TOKEN)
