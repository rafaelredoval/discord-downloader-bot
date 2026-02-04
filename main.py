import discord
import asyncio
import os
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

# ================= FUNÇÕES DE EXECUÇÃO =================

async def run_downvideos(ctx, start_date=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False

    scan_channel = bot.get_channel(SCAN_CHANNEL_ID)
    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)

    if not scan_channel or not download_channel:
        await ctx.send("❌ Erro: Canais não configurados corretamente.")
        return

    await ctx.send(f"📥 Movendo vídeos de <#{SCAN_CHANNEL_ID}> para <#{DOWNLOAD_CHANNEL_ID}>...")

    async for msg in scan_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if start_date and msg.created_at < start_date: continue
        if not msg.attachments: continue

        for att in msg.attachments:
            if any(att.filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv']):
                try:
                    arquivo = await att.to_file()
                    await download_channel.send(content=f"🎬 Vídeo de: {msg.author.mention}", file=arquivo)
                    await msg.add_reaction("✅") # Reage no SCAN
                except:
                    await msg.add_reaction("❌")
                await anti_rate()
    await ctx.send("✅ !downvideos finalizado.")

async def run_scan_link(ctx, start_date=None):
    """Função para o comando !scan link: Baixa do Download e posta no Fórum"""
    global CANCEL_FLAG
    CANCEL_FLAG = False
    
    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    post_channel = bot.get_channel(POST_CHANNEL_ID)

    await ctx.send(f"🚀 Iniciando `!scan link` para o Fórum...")
    
    async for msg in download_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if start_date and msg.created_at < start_date: continue
        if not msg.attachments: continue

        # Título baseado na menção do usuário
        if msg.mentions:
            thread_title = f"@{msg.mentions[0].display_name}"
        else:
            thread_title = f"Post de {msg.author.display_name}"

        header = f"🎬 Vídeo enviado por: **{msg.author.display_name}**"

        for att in msg.attachments:
            try:
                arquivo = await att.to_file()
                
                if isinstance(post_channel, discord.ForumChannel):
                    await post_channel.create_thread(name=thread_title, content=header, file=arquivo)
                else:
                    await post_channel.send(content=f"**{thread_title}**\n{header}", file=arquivo)
                
                # REAÇÃO DE VERIFICADO: Reage na mensagem do canal de Download
                await msg.add_reaction("✅")
            except:
                await msg.add_reaction("🧐")
            
            await anti_rate()
            
    await ctx.send("✅ !scan link finalizado!")

# ================= COMANDOS =================

@bot.command()
async def downvideos(ctx, *, arg=None):
    if ctx.channel.id != SCAN_CHANNEL_ID: return
    date = parse_date(arg) if arg else None
    await run_downvideos(ctx, date)

@bot.command()
async def scan(ctx, *, arg=None):
    """
    Uso: 
    !scan post [hoje/data] -> Antigo
    !scan link [hoje/data] -> Novo (baixa e reage com tick)
    """
    if ctx.channel.id != SCAN_CHANNEL_ID: return
    if not arg:
        await ctx.send("ℹ️ Use `!scan link hoje` ou `!scan link DD/MM/AAAA`")
        return

    # Lógica para separar "link" ou "post" do restante do argumento (data)
    parts = arg.split(" ", 1)
    comando_tipo = parts[0].lower()
    data_str = parts[1] if len(parts) > 1 else None
    date = parse_date(data_str) if data_str else None

    if comando_tipo == "link":
        await run_scan_link(ctx, date)
    elif comando_tipo == "post":
        # Mantido para compatibilidade, faz o mesmo que o link agora
        await run_scan_link(ctx, date)

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
