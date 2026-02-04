import discord
import asyncio
import os
import re
from discord.ext import commands
from datetime import datetime, timezone, time

# ================= VARIÁVEIS =================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))
POST_CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID"))

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)
CANCEL_FLAG = False

# Regex para identificar URLs
URL_PATTERN = r'(https?://[^\s]+)'

# ================= UTILITÁRIOS =================
def parse_date(text):
    try:
        if text.lower() == "hoje":
            agora = datetime.now(timezone.utc)
            return datetime.combine(agora.date(), time.min).replace(tzinfo=timezone.utc)
        if "/" in text:
            return datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

async def anti_rate():
    await asyncio.sleep(1.4)

# ================= FUNÇÃO LINK =================

async def run_move_links(ctx, start_date=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False

    scan_channel = bot.get_channel(SCAN_CHANNEL_ID)
    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)

    if not scan_channel or not download_channel:
        await ctx.send("❌ Erro: Canais de Scan ou Download não configurados.")
        return

    await ctx.send(f"🔗 Capturando links em <#{SCAN_CHANNEL_ID}>...")

    async for msg in scan_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if start_date and msg.created_at < start_date: continue
        
        # Procura por links no conteúdo da mensagem
        links = re.findall(URL_PATTERN, msg.content)
        
        if links:
            try:
                # Monta a mensagem com os links encontrados e a menção do autor
                links_formatados = "\n".join(links)
                content = f"🔗 **Link enviado por:** {msg.author.mention}\n{links_formatados}"
                
                await download_channel.send(content=content)
                await msg.add_reaction("✅") # Reage no canal Scan
            except Exception as e:
                print(f"Erro ao mover link: {e}")
                await msg.add_reaction("❌")
            
            await anti_rate()

    await ctx.send("✅ Comando `!link` finalizado!")

# ================= COMANDOS =================

@bot.command()
async def link(ctx, *, arg=None):
    """
    Uso: !link ou !link hoje ou !link DD/MM/AAAA
    Move mensagens que contenham URLs do canal Scan para o Download.
    """
    if ctx.channel.id != SCAN_CHANNEL_ID: return
    date = parse_date(arg) if arg else None
    await run_move_links(ctx, date)

@bot.command()
async def downvideos(ctx, *, arg=None):
    # (Mantida a lógica anterior para anexos de vídeo)
    if ctx.channel.id != SCAN_CHANNEL_ID: return
    # ... (código anterior do downvideos)

@bot.command()
async def scan(ctx, *, arg=None):
    # (Mantida a lógica anterior para postagem no fórum)
    if ctx.channel.id != SCAN_CHANNEL_ID: return
    # ... (código anterior do scan post/link)

@bot.command()
async def cancelgeral(ctx):
    global CANCEL_FLAG
    CANCEL_FLAG = True
    await ctx.send("🛑 Cancelamento ativado.")

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")

if __name__ == "__main__":
    bot.run(TOKEN)
