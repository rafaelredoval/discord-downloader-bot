import discord
import os
import re
import subprocess
from datetime import datetime, timezone

# =====================
# ENV VARS
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
START_DATE_STR = os.getenv("START_DATE")  # opcional

if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN não definido no Railway")

# START_DATE opcional
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
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Bot conectado como {client.user}")
    print(f"📅 Processando mensagens a partir de {START_DATE.date()}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # filtro por data
    if message.created_at < START_DATE:
        return

    urls = URL_REGEX.findall(message.content)
    if not urls:
        return

    user_id = str(message.author.id)
    user_folder = os.path.join(DOWNLOAD_BASE, user_id)
    os.makedirs(user_folder, exist_ok=True)

    for url in urls:
        try:
            print(f"⬇️ Baixando: {url} | Usuário: {user_id}")

            subprocess.run(
                [
                    "yt-dlp",
                    "-o",
                    f"{user_folder}/%(title)s.%(ext)s",
                    url
                ],
                check=True
            )

        except subprocess.CalledProcessError as e:
            print(f"❌ yt-dlp falhou para {url}: {e}")
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")

# =====================
# START BOT
# =====================
client.run(TOKEN)
