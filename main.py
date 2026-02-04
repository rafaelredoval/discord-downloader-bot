import discord
import asyncio
import os
from discord.ext import commands
from datetime import datetime, timezone

# ================= VARIÁVEIS =================

TOKEN = os.getenv("DISCORD_TOKEN")

SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))
POST_CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID"))
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", 0))

# ================= BOT =================

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)

CANCEL_FLAG = False

# ================= UTIL =================

def parse_date(text):
    try:
        if "/" in text:
            return datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

async def anti_rate():
    await asyncio.sleep(1.4)

# ================= LÓGICA DE DOWNLOAD/MOVE =================

async def run_downvideos(ctx, start_date=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False

    scan_channel = bot.get_channel(SCAN_CHANNEL_ID)
    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)

    if not scan_channel or not download_channel:
        await ctx.send("❌ Erro: Canais de Scan ou Download não encontrados.")
        return

    await ctx.send(f"📥 Iniciando coleta de vídeos em <#{SCAN_CHANNEL_ID}>...")

    async for msg in scan_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG:
            await ctx.send("🛑 Comando !downvideos cancelado.")
            return

        if start_date and msg.created_at < start_date:
            continue

        if not msg.attachments:
            continue

        # Identifica quem enviou o vídeo original
        author_mention = msg.author.mention
        content_with_mention = f"Enviado por: {author_mention}"

        for att in msg.attachments:
            # Filtra apenas extensões de vídeo comuns
            if any(att.filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv']):
                try:
                    file = await att.to_file()
                    # Envia para o canal de download mantendo o @ do autor no corpo da mensagem
                    await download_channel.send(content=content_with_mention, file=file)
                    await msg.add_reaction("📥") # Reação para indicar que foi processado
                except Exception as e:
                    await ctx.send(f"⚠️ Erro ao mover vídeo de {msg.author.display_name}: {e}")
                
                await anti_rate()

    await ctx.send("✅ Todos os vídeos foram movidos para o canal de download.")

# ================= COMANDOS =================

@bot.command()
async def downvideos(ctx, *, date_str=None):
    """Varre o canal SCAN e move os vídeos para o canal DOWNLOAD."""
    if ctx.channel.id != SCAN_CHANNEL_ID:
        return

    date = None
    if date_str:
        date = parse_date(date_str)
        if not date:
            await ctx.send("❌ Formato de data inválido. Use `DD/MM/AAAA HH:MM` ou `AAAA-MM-DD`.")
            return

    await run_downvideos(ctx, date)

@bot.command()
async def scan(ctx, *, arg=None):
    if ctx.channel.id != SCAN_CHANNEL_ID:
        return

    if arg and arg.startswith("post"):
        date = None
        parts = arg.split(" ", 1)
        if len(parts) == 2:
            date = parse_date(parts[1])

        # Importante: run_scan_post deve estar definido conforme as interações anteriores
        try:
            from main import run_scan_post
            await run_scan_post(ctx, date)
        except:
            await ctx.send("⚠️ Erro ao chamar a função de scan post.")
        return

    await ctx.send("ℹ️ Use `!scan post` ou `!downvideos [DATA]`")

@bot.command()
async def cancelgeral(ctx):
    global CANCEL_FLAG
    CANCEL_FLAG = True
    await ctx.send("🛑 Cancelamento geral ativado")

# ================= READY =================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

if __name__ == "__main__":
    bot.run(TOKEN)
