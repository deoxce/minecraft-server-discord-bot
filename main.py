import discord
from discord.ext import commands
from config import token, rconpass, rconip, serverstart, fzstart, fzstop, console
import os
import asyncio
import io
from mcrcon import MCRcon
import sys
import re

intents = discord.Intents.default()
intents.message_content = True
activity = discord.Game(name="сервер выключен")
client = commands.Bot(intents=intents,activity=activity, status=discord.Status.idle)

minecraft = client.create_group(name = "minecraft", guild = discord.Object(id = 1064616038383231047))

#@client.event
#async def on_ready():
#    await client.change_presence(status = discord.Status.online)

@minecraft.command(name = "start", description = "запуск майнкрафт сервера", guild = discord.Object(id = 1064616038383231047))
async def mc_start(ctx: discord.Interaction):
    await ctx.response.send_message("сервер запускается")
    await client.change_presence(status=discord.Status.online)
    await client.change_presence(activity=discord.Game(name=f"сервер включен"))
    os.startfile(serverstart)
    await asyncio.sleep(5)
    i = 63
    while True:
        i = await consolelinereader(i)

@minecraft.command(name = "stop", description = "остановка майнкрафт сервера", guild = discord.Object(id = 1064616038383231047))
async def mc_stop(ctx: discord.Interaction):
    await client.change_presence(status=discord.Status.idle)
    await client.change_presence(activity=discord.Game(name=f"сервер выключен"))
    with MCRcon(rconip, rconpass) as mcr:
        mcr.command('stop')
        mcr.disconnect()
        await ctx.response.send_message("сервер остановлен")

filezilla = client.create_group(name = "filezilla", guild = discord.Object(id = 1064616038383231047))

@filezilla.command(name = "start", description = "запуск фтп сервера", guild = discord.Object(id = 1064616038383231047))
async def fz_start(ctx: discord.Interaction):
    await ctx.response.send_message("сервер запущен")
    os.startfile(fzstart)

@filezilla.command(name = "stop", description = "остановка фтп сервера", guild = discord.Object(id = 1064616038383231047))
async def fz_stop(ctx: discord.Interaction):
    await ctx.response.send_message("сервер остановлен")
    os.startfile(fzstop)

@client.event
async def on_message(message: discord.Message):
    if message.author != client.user and message.channel.id == 1071333955187523654:
        with MCRcon(rconip, rconpass) as mcr:
            print(message.content)
            if len(f"<{message.author.name}> {message.content}") < 800:
                if len(message.content) > 0:
                    if message.content[0] == '!':
                        mcr.command(message.content[1:])
                    else:
                        mcr.command(f"tellraw @a [\"\",{{\"text\":\"<{message.author.name}>\",\"bold\":true,\"color\":\"#7289DA\",\"clickEvent\":{{\"action\":\"copy_to_clipboard\",\"value\":\"{message.author.name}#{message.author.discriminator}\"}},\"hoverEvent\":{{\"action\":\"show_text\",\"contents\":\"{message.author.name}#{message.author.discriminator}\"}}}},{{\"text\":\" {message.content}\"}}]")
            else:
                await message.add_reaction('💀')
            mcr.disconnect()

async def consolelinereader(i):
    file = io.open(console, mode="r", encoding="utf-8")
    lines = file.readlines()
    while i < len(lines):
        if re.match(r"\[[0-9][0-9]:[0-9][0-9]:[0-9][0-9] INFO\]: ", lines[i]):
            lines[i] = re.split(r"\[[0-9][0-9]:[0-9][0-9]:[0-9][0-9] INFO\]: ", lines[i])[1].replace("[Not Secure] ", "")
        if 'Stopping the server' in lines[i]:
            i = sys.maxsize
            break
        channel = client.get_channel(1071333955187523654)
        if ("Thread RCON Client" in lines[i]) == False:
            #if "!" in lines[i]:
            #    lines[i] = lines[i][lines[i].find("!") + 1 : ]
            await channel.send(lines[i])
        i += 1
    await asyncio.sleep(0)
    return i

client.run(token)
