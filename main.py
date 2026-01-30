import discord
import os
import re
import subprocess
from datetime import datetime, timezone

# =====================
# ENV VARS
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
START_DATE_STR = os.getenv("START_DATE")
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID")

if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN não definido")

if not TARGET_CHANNEL_ID:
    raise RuntimeError("❌ TARGET_CHANNEL_ID não definido")

TARGET_CHANNEL_ID = int(TARGET_CHANNEL_ID)

if START_DATE_STR:
    START_DATE = datetime.strptime(START_DATE_STR, "%Y-%m-%d").replace(tzinfo=timezone.utc)
else:
    START_DATE = datetime(1970, 1, 1, tzinfo=timezone.utc)

print("✅ START_DATE:", START_DATE.isoformat())

# =====================
# DISCORD CONFIG
# =====================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# =====================
# DOWNLOAD CONFIG
# =====================
URL_REGEX = re.compile(r'https?://\S+')
DOWNLOAD_BASE = "downloads"

# =====================
# FUNÇÃO DE PROCESSAMENTO
# =====================
async def process_message(message):
    if message.author.bot:
        return

    urls = URL_REGEX.findall(message.content)
    if not urls:
        return

    user_id = str(message.author.id)
    date_folder = message.created_at.strftime("%Y-%m-%d")
    user_folder = os.path.join(DOWNLOAD_BASE, user_id, date_folder)
    os.makedirs(user_folder, exist_ok=True)

    for url in urls:
        try:
            print(f"⬇️ Baixando {url} | Usuário {user_id}")

            subprocess.run(
                [
                    "yt-dlp",
                    "-o",
                    f"{user_folder}/%(title)s.%(ext)s",
                    url
                ],
                check=True
            )
        except Exception as e:
            print(f"❌ Erro ao baixar {url}: {e}")

# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Bot conectado como {client.user}")

@client.event
async def on_message(message):
    # ignora outros canais
    if message.channel.id != TARGET_CHANNEL_ID:
        return

    # ignora bots
    if message.author.bot:
        return

    # =====================
    # COMANDO !scan
    # =====================
    if message.content.strip().lower() == "!scan":
        await message.channel.send("🔍 Iniciando scan do histórico...")

        async for msg in message.channel.history(
            after=START_DATE,
            oldest_first=True,
            limit=None
        ):
            await process_message(msg)

        await message.channel.send("✅ Scan finalizado!")
        return

    # =====================
    # MENSAGENS NOVAS
    # =====================
    if message.created_at >= START_DATE:
        await process_message(message)

# =====================
# START BOT
# =====================
client.run(TOKEN)
