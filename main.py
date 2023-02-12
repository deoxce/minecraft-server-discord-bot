import discord
from discord.ext import commands
from mcrcon import MCRcon
import config
import os
import asyncio
import io
import re

intents = discord.Intents.default()
intents.message_content = True
activity = discord.Game(name = "server offline")
client = commands.Bot(intents = intents, activity = activity, status = discord.Status.idle)

minecraft = client.create_group(name = "minecraft", guild = discord.Object(id = config.guild_id))

@minecraft.command(name = "start", description = "start minecraft server", guild = discord.Object(id = config.guild_id))
async def mc_start(ctx: discord.Interaction):
    await ctx.response.send_message("server is started")
    await client.change_presence(status = discord.Status.online)
    await client.change_presence(activity = discord.Game(name = f"server online"))
    os.startfile(config.run_bat)
    await asyncio.sleep(5)
    line = 63
    while True:
        line = await console_reader(line)

@minecraft.command(name = "stop", description = "stop minecraft server", guild = discord.Object(id = config.guild_id))
async def mc_stop(ctx: discord.Interaction):
    await client.change_presence(status = discord.Status.idle)
    await client.change_presence(activity = discord.Game(name = f"server offline"))
    with MCRcon(config.rcon_ip, config.rcon_pass) as mcr:
        mcr.command('stop')
        mcr.disconnect()
        await ctx.response.send_message("server stopped")

filezilla = client.create_group(name = "filezilla", guild = discord.Object(id = config.guild_id))

@filezilla.command(name = "start", description = "start FTP server", guild = discord.Object(id = config.guild_id))
async def fz_start(ctx: discord.Interaction):
    await ctx.response.send_message("FTP server is started")
    os.startfile(config.ftp_start)

@filezilla.command(name = "stop", description = "stop FTP server", guild = discord.Object(id = config.guild_id))
async def fz_stop(ctx: discord.Interaction):
    await ctx.response.send_message("FTP server stopped")
    os.startfile(config.ftp_stop)

@client.event
async def on_message(message: discord.Message):
    if message.author != client.user and (message.channel.id == config.chat_channel_id or message.channel.id == config.console_channel_id):
        if len(f"<{message.author.name}> {message.content}") < 800 and len(message.content) > 0:
            with MCRcon(config.rcon_ip, config.rcon_pass) as mcr:
                if message.channel.id == config.chat_channel_id:
                    mcr.command(f"tellraw @a [\"\",{{\"text\":\"<{message.author.name}>\",\"bold\":true,\"color\":\"#7289DA\",\"clickEvent\":{{\"action\":\"copy_to_clipboard\",\"value\":\"{message.author.name}#{message.author.discriminator}\"}},\"hoverEvent\":{{\"action\":\"show_text\",\"contents\":\"{message.author.name}#{message.author.discriminator}\"}}}},{{\"text\":\" {message.content}\"}}]")
                if message.channel.id == config.console_channel_id:
                    r = mcr.command(message.content)
                    await message.reply(r)
            mcr.disconnect()
        else:
            await message.add_reaction('💀')

async def console_reader(line):
    chat_channel = client.get_channel(config.chat_channel_id)
    console_channel = client.get_channel(config.console_channel_id)
    file = io.open(config.console, mode = "r", encoding = "utf-8")
    line_list = file.readlines()
    while line < len(line_list):
        nickname = re.search(r"<(.+?)>", line_list[line])
        if nickname != None:
            await chat_channel.send(f"**{nickname.group(1)}**:{line_list[line][line_list[line].find('>') + 1:]}")
        else:
            await console_channel.send(line_list[line])
        line += 1
    await asyncio.sleep(0)
    return line

client.run(config.token)
