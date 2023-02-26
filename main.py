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
activity = discord.Game(name="server offline")
client = commands.Bot(intents=intents, activity=activity)
started = False
start_button_state = True
stop_button_state = False
panel: discord.Interaction = None
panel_message: discord.Message = None
console_output = False
global_interaction: discord.Interaction = None
stop_already_called = False
nickname = None
find_stop = False

@client.event
async def on_ready():
    print("ready")

async def control_panel(start_button_state, stop_button_state):
    view = View(timeout=None)
    button_start = Button(label="start", style=discord.ButtonStyle.green, disabled=not start_button_state)
    button_stop = Button(label="stop", style=discord.ButtonStyle.red, disabled=not stop_button_state)
    button_status = Button(label="status", style=discord.ButtonStyle.blurple)
    if config.dynmap:
        button_render = Button(label="render", style=discord.ButtonStyle.blurple, url=f'http://{config.server_ip}:{config.dynmap_port}')
    else:
        button_render = Button(label="render", style=discord.ButtonStyle.blurple)
        button_render.callback = mc_render
    button_start.callback = mc_start
    button_stop.callback = mc_stop
    button_status.callback = mc_status
    view.add_item(button_start)
    view.add_item(button_stop)
    view.add_item(button_status)
    view.add_item(button_render)
    return view

server_group = client.create_group(name="server", guild=discord.Object(id=config.guild_id))

@server_group.command(name="panel", description="server control panel", guild=discord.Object(id=config.guild_id))
async def server(ctx: discord.Interaction):
    global panel, start_button_state, stop_button_state, panel_message
    if panel is not None:
        await panel_message.delete()
    view = await control_panel(start_button_state, stop_button_state)
    panel = await ctx.response.send_message("control panel", view=view)
    panel_message = await panel.original_response()
    #panel_message = await panel.channel.fetch_message(panel.channel.last_message_id)
    #print(panel.channel.last_message_id, panel.message.reference.message_id)

@server_group.command(name="start", description="start minecraft server", guild=discord.Object(id=config.guild_id))
async def mc_start(ctx: discord.Interaction):
    global started, panel, start_button_state, stop_button_state, panel_message, console_output
    if not started:
        start_button_state = False
        os.startfile(config.run_bat)
        server = JavaServer.lookup(f"{config.server_ip}:{config.server_port}", timeout=0.05)
        if panel is not None:
            view = await control_panel(start_button_state, stop_button_state)
            await panel_message.edit(view=view)
        print("server is starting")
        await ctx.response.defer(ephemeral=False, invisible=False)
        while not started:
            await asyncio.sleep(0)
            try:
                status = server.status()
                if status:
                    started = True
            except Exception:
                print("starting..")
        await ctx.followup.send("server started")
        print("server started")
        stop_button_state = True
        if panel is not None:
            view = await control_panel(start_button_state, stop_button_state)
            await panel_message.edit(view=view)
        await client.change_presence(activity=discord.Game(name="server online"))
        file = io.open(config.console, mode="r", encoding="utf-8")
        line = len(file.readlines()) - 1
        console_output = True
        while started:
            line = await console_reader(line)
    else:
        await ctx.response.send_message("server is already running", ephemeral=True)

@server_group.command(name="stop", description="stop minecraft server", guild=discord.Object(id=config.guild_id))
async def mc_stop(ctx: discord.Interaction):
    global stop_already_called
    await client.change_presence(activity=discord.Game(name="server offline"))
    if not stop_already_called:
        try:
            with MCRcon(config.server_ip, config.rcon_pass) as mcr:
                global started, panel, start_button_state, stop_button_state, panel_message, console_output, global_interaction
                console_output = False
                stop_button_state = False
                stop_already_called = True
                if panel is not None:
                    view = await control_panel(start_button_state, stop_button_state)
                    await panel_message.edit(view=view)
                mcr.command("stop")
                mcr.disconnect()
                global_interaction = ctx
                await ctx.response.defer(ephemeral=False, invisible=False)
                print("server is stopping")
        except Exception:
            await ctx.response.send_message("server is already stopped", ephemeral=True)

@server_group.command(name="status", description="server status", guild=discord.Object(id=config.guild_id))
async def mc_status(ctx: discord.Interaction, ip: str = f"{config.server_ip}:{config.server_port}"):
    if ip.find(":") == -1:
        ip += ":25565"
    server = JavaServer.lookup(ip, timeout=2)
    server_online = False
    try:
        status = server.status()
        server_online = True
        await ctx.response.send_message(f"**ip:** {ip}\n**version:** {status.version.name}\n**description:** {status.description}\n**number of players:** {status.players.online}/{status.players.max}")
    except Exception:
        await ctx.response.send_message(f"server {ip} offline")
    if server_online:
        try:
            query = server.query()
            await ctx.channel.send(f"**map: **{query.map}\n**brand: **{query.software.brand}\n**plugins: **{', '.join(query.software.plugins)}\n**players list: **{', '.join(query.players.names)}")
        except Exception:
            pass

@server_group.command(name="render", description="render server map", guild=discord.Object(id=config.guild_id))
async def mc_render(ctx: discord.Interaction):
    if config.dynmap:
        await ctx.response.send_message(f'http://{config.server_ip}:{config.dynmap_port}')
    else:
        await ctx.response.send_message("in developing")

@client.event
async def on_message(message: discord.Message):
    if message.author != client.user:
        if message.channel.id == config.chat_channel_id:
            if len(f"<{message.author.name}> {message.content}") < 800 and len(message.content) > 0:
                with MCRcon(config.server_ip, config.rcon_pass) as mcr:
                    mcr.command(f"tellraw @a [\"\",{{\"text\":\"<{message.author.name}>\",\"bold\":true,\"color\":\"#7289DA\",\"clickEvent\":{{\"action\":\"copy_to_clipboard\",\"value\":\"{message.author.name}#{message.author.discriminator}\"}},\"hoverEvent\":{{\"action\":\"show_text\",\"contents\":\"{message.author.name}#{message.author.discriminator}\"}}}},{{\"text\":\" {message.content}\"}}]")
                mcr.disconnect()
            else:
                await message.add_reaction("💀")
        if message.channel.id == config.console_channel_id:
            if 0 < len(message.content) < 256:
                with MCRcon(config.server_ip, config.rcon_pass) as mcr:
                    resp = mcr.command(message.content)
                    if resp == "Stopping the server":
                        global started, panel, start_button_state, stop_button_state, panel_message, console_output
                        console_output = False
                        stop_button_state = False
                        if panel is not None:
                            view = await control_panel(start_button_state, stop_button_state)
                            await panel_message.edit(view=view)
                        resp = "server is stopping"
                        print("server is stopping")
                    await message.reply(resp, mention_author=False)
                mcr.disconnect()
            else:
                await message.add_reaction("💀")

async def console_reader(line):
    global started, panel, start_button_state, stop_button_state, panel_message, console_output, global_interaction, stop_already_called, nickname
    chat_channel = client.get_channel(config.chat_channel_id)
    console_channel = client.get_channel(config.console_channel_id)
    file = io.open(config.console, mode="r", encoding="utf-8")
    line_list = file.readlines()
    while line < len(line_list):
        if re.match(r"\[[0-9][0-9]:[0-9][0-9]:[0-9][0-9] INFO\]: (.+?) issued server command: /stop", line_list[line]):
            console_output = False
            stop_button_state = False
            if panel is not None:
                view = await control_panel(start_button_state, stop_button_state)
                await panel_message.edit(view=view)
            await console_channel.send(line_list[line])
            message = await console_channel.fetch_message(console_channel.last_message_id)
            await message.reply("server is stopping")
            print("server is stopping") 
        if re.match(r"\[[0-9][0-9]:[0-9][0-9]:[0-9][0-9] INFO\]: Closing Server", line_list[line]):
            await global_interaction.followup.send("server stopped")
            print("server stopped") 
            stop_already_called = False
            started = False
            start_button_state = True
            if panel is not None:
                view = await control_panel(start_button_state, stop_button_state)
                await panel_message.edit(view=view)
            break
        if console_output:
            if re.match(r"\[[0-9][0-9]:[0-9][0-9]:[0-9][0-9] INFO\]: <(.+?)>", line_list[line]):
                nickname = re.search(r"<(.+?)>", line_list[line])
            if nickname is not None:
                await chat_channel.send(f"**{nickname.group(1)}**:{line_list[line][line_list[line].find('>') + 1:]}")
            else:
                await console_channel.send(line_list[line])
        line += 1
    await asyncio.sleep(0)
    return line

find = client.create_group(name="find", guild=discord.Object(id=config.guild_id))

@find.command(name="ip", description="find ip", guild=discord.Object(id=config.guild_id))
async def ip(ctx: discord.Interaction):
    await ctx.response.send_message("in developing")

@find.command(name="ngrok", description="find ngrok", guild=discord.Object(id=config.guild_id))
async def ngrok(ctx: discord.Interaction, first_index: int = 0, last_index: int = 7, first_port: int = 10000, last_port: int = 20000):
    await ctx.response.send_message(f"search started from {first_index}.tcp.eu.ngrok.io:{first_port} to {last_index}.tcp.eu.ngrok.io:{last_port}")
    await find_ngrok(ctx, first_index, last_index, first_port, last_port)

async def find_ngrok(ctx: discord.Interaction, first_index, last_index, first_port, last_port):
    global find_stop
    for i in range(first_index, last_index):
        for port in range(first_port, last_port):
            await asyncio.sleep(0)
            if find_stop is True:
                find_stop = False
                return
            server = JavaServer.lookup(f"{i}.tcp.eu.ngrok.io:{port}", timeout=0.05)
            try:
                status = server.status()
                serverinfo = f"ip: {i}.tcp.eu.ngrok.io:{port} | players count: {status.players.online} | version: {status.version.name} | description: {status.description}"
                await ctx.channel.send(serverinfo)
            except Exception:
                pass
    await ctx.channel.send("search finished")

@find.command(name="stop", description="stop search", guild=discord.Object(id=config.guild_id))
async def ngrok(ctx: discord.Interaction):
    global find_stop
    find_stop = True
    await ctx.response.send_message("search stopped")

client.run(config.token)
