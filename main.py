async def process_message(message):
    if message.author.bot:
        return

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
        # 🔒 pasta única por URL
        safe_name = str(abs(hash(url)))
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

                if os.path.isfile(file_path):
                    await download_channel.send(
                        content=f"📦 Enviado por <@{user_id}>",
                        file=discord.File(file_path)
                    )
                    os.remove(file_path)
                    files_sent += 1

            if files_sent == 0:
                await status_msg.edit(content="⚠️ Nenhum arquivo foi gerado.")
            else:
                await status_msg.edit(
                    content=f"✅ **Download concluído ({files_sent} arquivo(s))**"
                )

        except subprocess.CalledProcessError as e:
            await status_msg.edit(content="❌ **Erro ao baixar o conteúdo**")
            print(e)
