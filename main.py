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

# ================= SCAN POST =================

async def run_scan_post(ctx, start_date=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False

    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    post_channel = bot.get_channel(POST_CHANNEL_ID)

    if not download_channel or not post_channel:
        await ctx.send("❌ Erro: Canais não encontrados. Verifique as IDs no Railway.")
        return

    await ctx.send("📦 Coletando mídias do canal de download...")

    async for msg in download_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG:
            await ctx.send("🛑 Scan post cancelado")
            return

        if start_date and msg.created_at < start_date:
            continue

        if not msg.attachments:
            continue

        author_name = msg.author.display_name
        data_formatada = msg.created_at.strftime('%d/%m/%Y %H:%M')
        header = f"🎬 Vídeo enviado por: **{author_name}**"
        
        # Título caso o destino seja um Fórum
        thread_title = f"Post de {author_name} - {data_formatada}"

        for att in msg.attachments:
            try:
                file = await att.to_file()
                
                # Lógica para Fórum vs Canal de Texto
                if isinstance(post_channel, discord.ForumChannel):
                    await post_channel.create_thread(name=thread_title, content=header, file=file)
                else:
                    await post_channel.send(content=header, file=file)
                
                await msg.add_reaction("✅")
            except Exception as e:
                # Caso o arquivo seja muito grande (>25MB), envia apenas o link
                error_content = f"{header}\n🔗 Link da mídia: {att.url}\n⚠️ (Arquivo muito grande ou erro no upload)"
                
                if isinstance(post_channel, discord.ForumChannel):
                    await post_channel.create_thread(name=f"Link: {author_name}", content=error_content)
                else:
                    await post_channel.send(content=error_content)
                
                await msg.add_reaction("🧐")
                print(f"Erro ao processar anexo: {e}")

            await anti_rate()

    await ctx.send("✅ Scan post finalizado")

# ================= COMANDOS =================

@bot.command()
async def scan(ctx, *, arg=None):
    if ctx.channel.id != SCAN_CHANNEL_ID:
        return

    if arg and arg.startswith("post"):
        date = None
        parts = arg.split(" ", 1)
        if len(parts) == 2:
            date = parse_date(parts[1])

        await run_scan_post(ctx, date)
        return

    await ctx.send("ℹ️ Use `!scan post` ou `!scan post DD/MM/AAAA HH:MM`")

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
