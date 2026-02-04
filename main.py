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
            # Define o início do dia atual (00:00:00) em UTC
            agora = datetime.now(timezone.utc)
            return datetime.combine(agora.date(), time.min).replace(tzinfo=timezone.utc)
        if "/" in text:
            return datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

async def anti_rate():
    # Pausa para evitar atingir o limite de requisições do Discord
    await asyncio.sleep(1.4)

# ================= FUNÇÕES DE EXECUÇÃO =================

async def run_downvideos(ctx, start_date=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False

    scan_channel = bot.get_channel(SCAN_CHANNEL_ID)
    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)

    if not scan_channel or not download_channel:
        await ctx.send("❌ Erro: IDs dos canais não configuradas corretamente.")
        return

    await ctx.send(f"📥 Coletando vídeos de <#{SCAN_CHANNEL_ID}>...")

    async for msg in scan_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG:
            await ctx.send("🛑 Download cancelado pelo usuário.")
            return

        # Filtro de data (ex: mensagens enviadas após 00:00 de hoje)
        if start_date and msg.created_at < start_date:
            continue

        if not msg.attachments:
            continue

        for att in msg.attachments:
            # Filtro para garantir que apenas vídeos sejam movidos
            extensoes_video = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
            if any(att.filename.lower().endswith(ext) for ext in extensoes_video):
                try:
                    # Converte o anexo em um arquivo para o upload
                    arquivo = await att.to_file()
                    
                    # Envia para o canal de texto de Download
                    await download_channel.send(
                        content=f"🎬 Vídeo de: {msg.author.mention}", 
                        file=arquivo
                    )
                    
                    # Reação no canal SCAN para marcar como concluído
                    await msg.add_reaction("📥")
                except Exception as e:
                    print(f"Erro ao mover arquivo: {e}")
                
                await anti_rate()

    await ctx.send("✅ Comando `!downvideos` finalizado com sucesso.")

async def run_scan_post(ctx, start_date=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False
    
    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    post_channel = bot.get_channel(POST_CHANNEL_ID)

    await ctx.send("📦 Iniciando postagens no Fórum...")
    
    async for msg in download_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if start_date and msg.created_at < start_date: continue
        if not msg.attachments: continue

        # Define o título do tópico no fórum
        if msg.mentions:
            # Usa o nome legível da primeira pessoa mencionada
            thread_title = f"@{msg.mentions[0].display_name}"
        else:
            thread_title = f"Post de {msg.author.display_name}"

        header = f"🎬 Vídeo enviado por: **{msg.author.display_name}**"

        for att in msg.attachments:
            try:
                arquivo = await att.to_file()
                
                # Se o destino for um Fórum, cria um novo tópico (Thread)
                if isinstance(post_channel, discord.ForumChannel):
                    await post_channel.create_thread(name=thread_title, content=header, file=arquivo)
                else:
                    # Se for canal de texto comum, apenas envia a mensagem
                    await post_channel.send(content=f"**{thread_title}**\n{header}", file=arquivo)
                
                await msg.add_reaction("✅")
            except:
                await msg.add_reaction("🧐")
            
            await anti_rate()
            
    await ctx.send("✅ Scan Post finalizado!")

# ================= COMANDOS =================

@bot.command()
async def downvideos(ctx, *, arg=None):
    """Varre o canal SCAN e move vídeos para o canal de DOWNLOAD (Texto)."""
    if ctx.channel.id != SCAN_CHANNEL_ID: 
        return
    
    date = parse_date(arg) if arg else None
    await run_downvideos(ctx, date)

@bot.command()
async def scan(ctx, *, arg=None):
    """Varre o canal DOWNLOAD e posta no FÓRUM."""
    if ctx.channel.id != SCAN_CHANNEL_ID: 
        return
        
    if arg and arg.startswith("post"):
        date = None
        parts = arg.split(" ", 1)
        if len(parts) == 2:
            date = parse_date(parts[1])
        await run_scan_post(ctx, date)
    else:
        await ctx.send("ℹ️ Use `!scan post` ou `!scan post hoje`")

@bot.command()
async def cancelgeral(ctx):
    """Interrompe qualquer processo em execução."""
    global CANCEL_FLAG
    CANCEL_FLAG = True
    await ctx.send("🛑 Cancelamento solicitado. O bot irá parar após concluir a subida atual.")

# ================= READY =================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado com sucesso como {bot.user}")

if __name__ == "__main__":
    bot.run(TOKEN)
