import discord
import os
import re
import subprocess
from datetime import datetime, timezone

TOKEN = os.getenv("MTQ1OTgxNDE3NzgyNzk4MzQ3Mg.GsXecL.XuopVIZTtMgSZ805-kXh802UC9A4ArtSx1DQkI")
START_DATE_STR = os.getenv("START_DATE")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não definido no Railway")

if not START_DATE_STR:
    raise RuntimeError("START_DATE não definido no Railway")

START_DATE = datetime.strptime(START_DATE_STR, "%Y-%m-%d").replace(tzinfo=timezone.utc)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

URL_REGEX = re.compile(r'https?://\S+')

DOWNLOAD_BASE = "downloads"

@client.event
async def on_ready():
    print(f"✅ Bot conectado como {client.user}")
    print(f"📅 Processando mensagens a partir de {START_DATE.date()}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # 🔒 filtro por data
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
            print(f"⬇️ Baixando de {url} | Usuário {user_id}")

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

client.run(TOKEN)
