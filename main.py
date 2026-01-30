import discord
import os
import re
import subprocess
import hashlib
from datetime import datetime, timezone

# =====================
# ENV VARS (Railway)
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))       # canal onde usa !scan
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))  # canal que recebe arquivos
START_DATE_STR = os.getenv("START_DATE")  # opcional YYYY-MM-DD

if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN não definido")

# START_DATE opcional
if START_DATE_STR:
    START_DATE = datetime.strptime(
        START_DATE_STR, "%Y-%m-%d"
    ).replace(tzinfo=timezone.utc)
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

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Apenas no canal definido
    if message.channel.id != SCAN_CHANNEL_ID:
        return

    # Comando !scan
    if not message.content.startswith("!scan"):
        return

    await message.channel.send("🔍 **Iniciando varredura de links…**")

    async for msg in message.channel.history(
        after=START_DATE,
        oldest_first=True,
        limit=None
    ):
        await process_message(msg)

    await message.channel.send("✅ **Varredura concluída!**")

# =====================
# CORE FUNCTION
# =====================
async def process_message(message):
    urls = URL_REGEX.findall(message.content)
    if not urls:
        return

    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)
    if not download_channel:
        print("❌ Canal de download não encontrado")
        return

    user_id = str(message.author.id)
    date_folder = message.created_at.strftime("%Y-%m-%d")

    for url in urls:
        # pasta única por URL (hash fixo)
        safe_name = hashlib.sha1(url.encode()).hexdigest()

        download_folder = os.path.join(
            DOWNLOAD_BASE, user_id, date_folder, safe_name
        )
        os.makedirs(download_folder, exist_ok=True)

        status_msg = await download_channel.send(
            f"⏳ **Baixando conteúdo**\n"
            f"🔗 {url}\n"
            f"👤 Usuário: <@{user_id}>"
        )

        try:
            subprocess.run(
                [
                    "yt-dlp",
                    "-o",
                    f"{download_folder}/%(title)s.%(ext)s",
                    url
                ],
                check=True
            )

            await status_msg.edit(content="📤 **Enviando arquivo(s)…**")

            files_sent = 0

            for filename in os.listdir(download_folder):
                file_path = os.path.join(download_folder, filename)

                if not os.path.isfile(file_path):
                    continue

                try:
                    await download_channel.send(
                        content=f"📦 Enviado por <@{user_id}>",
                        file=discord.File(file_path)
                    )
                    os.remove(file_path)
                    files_sent += 1

                except Exception as e:
                    await download_channel.send(
                        f"❌ Falha ao enviar `{filename}` (arquivo muito grande?)"
                    )
                    print(e)

            if files_sent == 0:
                await status_msg.edit(content="⚠️ Nenhum arquivo foi enviado.")
            else:
                await status_msg.edit(
                    content=f"✅ **Download concluído ({files_sent} arquivo(s))**"
                )

        except subprocess.CalledProcessError as e:
            await status_msg.edit(content="❌ **Erro ao baixar o conteúdo**")
            print(e)

# =====================
# START BOT
# =====================
client.run(TOKEN)
