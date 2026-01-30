import discord
import yt_dlp
import os
import zipfile
import shutil
from discord import File

TOKEN = os.getenv('DISCORD_TOKEN') # Defina isso no Railway
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def download_media(url, folder):
    ydl_opts = {
        'outtmpl': f'{folder}/%(title)s.%(ext)s',
        'format': 'best',
        'quiet': True,
        'nocheckcertificate': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if 'instagram.com' in message.content or 'tiktok.com' in message.content or 'youtube.com' in message.content:
        temp_dir = f"dl_{message.id}"
        os.makedirs(temp_dir, exist_ok=True)
        
        msg_status = await message.channel.send("⚔️ Iniciando a coleta da mídia, aguarde...")

        try:
            # Download
            download_media(message.content, temp_dir)
            
            # Criar ZIP
            zip_name = f"midia_{message.id}.zip"
            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), file)

            # Enviar para o Discord
            await message.channel.send(content=f"📦 Aqui está seu tesouro, fidalgo {message.author.mention}:", file=File(zip_name))
            
            # Limpeza de arquivos
            os.remove(zip_name)
            shutil.rmtree(temp_dir)
            await msg_status.delete()

        except Exception as e:
            await message.channel.send(f"❌ Lamentável, mas houve um erro: {e}")
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

client.run(TOKEN)
