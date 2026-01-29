import discord
import re
import subprocess
import os

TOKEN = os.getenv("35e588aecada1adb334dc08a2dcfe7f522cea54f8bdd4bef95de8c8f9dfae139")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def extrair_links(texto):
    return re.findall(r'https?://\S+', texto)

@client.event
async def on_ready():
    print(f"Bot conectado como {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    links = extrair_links(message.content)

    for link in links:
        subprocess.run([
            "yt-dlp",
            "-f", "best",
            "-o", f"{DOWNLOADS_DIR}/%(uploader)s_%(id)s.%(ext)s",
            link
        ])

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não definido nas variáveis do Railway")

client.run(TOKEN)

