import discord
from discord.ui import Button, View
from discord.ext import commands
from mcstatus import JavaServer
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
started = False

@client.event
async def on_ready():
    view = await control_panel()
    bot_channel = client.get_channel(config.bot_channel_id)
    await bot_channel.send("control panel", view=view)

@client.slash_command(name = "server", description = "server control panel", guild = discord.Object(id = config.guild_id))
async def server(ctx: discord.Interaction):
    view = await control_panel()
    await ctx.response.send_message("control panel", view=view)

async def control_panel():
    view = View()
    button_start = Button(label="start", style=discord.ButtonStyle.green)
    button_stop = Button(label="stop", style=discord.ButtonStyle.red)
    button_status = Button(label="status", style=discord.ButtonStyle.blurple)
    button_render = Button(label="render", style=discord.ButtonStyle.blurple)
    button_start.callback = mc_start
    button_stop.callback = mc_stop
    button_status.callback = mc_status
    button_render.callback = mc_render
    view.add_item(button_start)
    view.add_item(button_stop)
    view.add_item(button_status)
    view.add_item(button_render)
    return view

minecraft = client.create_group(name = "minecraft", guild = discord.Object(id = config.guild_id))

@minecraft.command(name = "start", description = "start minecraft server", guild = discord.Object(id = config.guild_id))
async def mc_start(ctx: discord.Interaction):
    global started
    os.startfile(config.run_bat)
    server = JavaServer.lookup(config.server_ip, timeout = 3)
    await ctx.response.send_message("server is starting")
    while not started:
        try:
            status = server.status()
            if status: 
                started = True
        except Exception: 
            print("starting..")
    await ctx.channel.send("server started")
    await client.change_presence(status = discord.Status.online)
    await client.change_presence(activity = discord.Game(name = f"server online"))
    file = io.open(config.console, mode = "r", encoding = "utf-8")
    line = len(file.readlines()) - 1
    while started:
        line = await console_reader(line)

@minecraft.command(name = "stop", description = "stop minecraft server", guild = discord.Object(id = config.guild_id))
async def mc_stop(ctx: discord.Interaction):
    global started
    await client.change_presence(status = discord.Status.idle)
    await client.change_presence(activity = discord.Game(name = f"server offline"))
    with MCRcon(config.rcon_ip, config.rcon_pass) as mcr:
        mcr.command('stop')
        mcr.disconnect()
        started = False
        await ctx.response.send_message("server stopped")

@minecraft.command(name = "status", description = "server status", guild = discord.Object(id = 1064616038383231047))
async def mc_status(ctx: discord.Interaction, ip: str = config.server_ip):
    if ip.find(":") == -1:
        ip += ":25565"
    server = JavaServer.lookup(ip, timeout = 1)
    try:
        status = server.status()
        await ctx.response.send_message(f"ip: {ip}\nversion: {status.version.name}\ndescription: {status.description}\nplayers: {status.players.online}")
    except Exception:
        await ctx.response.send_message(f"server {ip} offline")

@minecraft.command(name = "render", description = "render server map", guild = discord.Object(id = 1064616038383231047))
async def mc_render(ctx: discord.Interaction):
    await ctx.response.send_message("in developing")

@client.event
async def on_message(message: discord.Message):
    global started
    if message.author != client.user and (message.channel.id == config.chat_channel_id or message.channel.id == config.console_channel_id):
        if len(f"<{message.author.name}> {message.content}") < 800 and len(message.content) > 0:
            try: 
                with MCRcon(config.rcon_ip, config.rcon_pass) as mcr:
                    if message.channel.id == config.chat_channel_id:
                        mcr.command(f"tellraw @a [\"\",{{\"text\":\"<{message.author.name}>\",\"bold\":true,\"color\":\"#7289DA\",\"clickEvent\":{{\"action\":\"copy_to_clipboard\",\"value\":\"{message.author.name}#{message.author.discriminator}\"}},\"hoverEvent\":{{\"action\":\"show_text\",\"contents\":\"{message.author.name}#{message.author.discriminator}\"}}}},{{\"text\":\" {message.content}\"}}]")
                    if message.channel.id == config.console_channel_id:
                        resp = mcr.command(message.content)
                        if resp == "Stopping the server":
                            resp = "server stopped"
                            started = False
                        await message.reply(resp, mention_author = False)
                mcr.disconnect()
            except Exception:
                pass
        else:
            await message.add_reaction('💀')

async def console_reader(line):
    global started
    chat_channel = client.get_channel(config.chat_channel_id)
    console_channel = client.get_channel(config.console_channel_id)
    file = io.open(config.console, mode = "r", encoding = "utf-8")
    line_list = file.readlines()
    while line < len(line_list):
        if re.match(r"\[[0-9][0-9]:[0-9][0-9]:[0-9][0-9] INFO\]: (.+?) issued server command: /stop", line_list[line]):
            started = False
            await console_channel.send(line_list[line])
            message = await console_channel.fetch_message(console_channel.last_message_id)
            await message.reply("server stopped")
            break
        nickname = re.search(r"<(.+?)>", line_list[line])
        if nickname != None:
            await chat_channel.send(f"**{nickname.group(1)}**:{line_list[line][line_list[line].find('>') + 1:]}")
        else:
            await console_channel.send(line_list[line])
        line += 1
    await asyncio.sleep(0)
    return line

client.run(config.token)
