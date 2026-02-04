import discord
import asyncio
import os
from discord.ext import commands
from datetime import datetime, timezone
from moviepy.editor import VideoFileClip

# ================= VARIÁVEIS =================

TOKEN = os.getenv("DISCORD_TOKEN")

SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
POST_CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID")) # ID do Fórum

# ================= BOT =================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================= UTIL =================

def format_duration(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours}h {minutes}m {seconds}s"

# ================= COMANDOS =================

@bot.command()
async def total_tempo(ctx):
    """Varre o fórum e soma a duração de todos os vídeos anexados."""
    if ctx.channel.id != SCAN_CHANNEL_ID:
        return

    forum_channel = bot.get_channel(POST_CHANNEL_ID)
    
    if not isinstance(forum_channel, discord.ForumChannel):
        await ctx.send("❌ O canal configurado como POST_CHANNEL_ID não é um fórum.")
        return

    status_msg = await ctx.send("⏳ Iniciando varredura no fórum... Isso pode demorar dependendo da quantidade de vídeos.")
    
    total_seconds = 0.0
    videos_contados = 0
    erros = 0

    # Varre todos os posts (threads) do fórum
    for thread in forum_channel.threads:
        async for msg in thread.history(limit=None, oldest_first=True):
            for att in msg.attachments:
                # Verifica se o anexo é um vídeo (extensões comuns)
                if any(att.filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv']):
                    temp_filename = f"temp_{att.id}_{att.filename}"
                    try:
                        # Baixa o vídeo temporariamente para ler o cabeçalho
                        await att.save(temp_filename)
                        
                        with VideoFileClip(temp_filename) as clip:
                            total_seconds += clip.duration
                        
                        videos_contados += 1
                        os.remove(temp_filename) # Apaga logo após ler
                    except Exception as e:
                        print(f"Erro ao ler vídeo {att.filename}: {e}")
                        erros += 1
                        if os.path.exists(temp_filename):
                            os.remove(temp_filename)

    # Varre também os posts arquivados
    async for thread in forum_channel.archived_threads(limit=None):
        async for msg in thread.history(limit=None, oldest_first=True):
            for att in msg.attachments:
                if any(att.filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv']):
                    temp_filename = f"temp_{att.id}_{att.filename}"
                    try:
                        await att.save(temp_filename)
                        with VideoFileClip(temp_filename) as clip:
                            total_seconds += clip.duration
                        videos_contados += 1
                        os.remove(temp_filename)
                    except Exception as e:
                        erros += 1
                        if os.path.exists(temp_filename):
                            os.remove(temp_filename)

    tempo_final = format_duration(total_seconds)
    
    await status_msg.edit(content=(
        f"✅ **Varredura Finalizada!**\n"
        f"🎬 Total de vídeos analisados: `{videos_contados}`\n"
        f"⏱️ Tempo total acumulado: **{tempo_final}**\n"
        f"⚠️ Falhas ao processar: `{erros}`"
    ))

# ================= READY =================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

if __name__ == "__main__":
    bot.run(TOKEN)
