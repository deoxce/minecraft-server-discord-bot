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
client = commands.Bot(intents=intents, activity=activity, status=discord.Status.idle)
started = False
start_button_state = True
stop_button_state = False
panel: discord.Interaction = None
panel_message: discord.Message = None

@client.event
async def on_ready():
    print("ready")

@client.slash_command(name="server", description="server control panel", guild=discord.Object(id=config.guild_id))
async def server(ctx: discord.Interaction):
    global panel, start_button_state, stop_button_state, panel_message
    if panel is not None:
        await panel_message.delete()
    view = await control_panel(start_button_state, stop_button_state)
    panel = await ctx.response.send_message("control panel", view=view)
    panel_message = await panel.channel.fetch_message(panel.channel.last_message_id)

async def control_panel(start_button_state, stop_button_state):
    view = View(timeout=None)
    button_start = Button(label="start", style=discord.ButtonStyle.green, disabled=not start_button_state)
    button_stop = Button(label="stop", style=discord.ButtonStyle.red, disabled=not stop_button_state)
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

minecraft = client.create_group(name="minecraft", guild=discord.Object(id=config.guild_id))

@minecraft.command(name="start", description="start minecraft server", guild=discord.Object(id=config.guild_id))
async def mc_start(ctx: discord.Interaction):
    global started, panel, start_button_state, stop_button_state
    if not started:
        start_button_state = False
        os.startfile(config.run_bat)
        server = JavaServer.lookup(config.server_ip)
        if panel is not None:
            view = await control_panel(start_button_state, stop_button_state)
            await panel.edit_original_response(view=view)
        await ctx.response.send_message("server is starting")
        while not started:
            try:
                status = server.status()
                if status:
                    started = True
            except Exception:
                print("starting..")
        await ctx.channel.send("server started")
        print("server started")
        stop_button_state = True
        if panel is not None:
            view = await control_panel(start_button_state, stop_button_state)
            await panel.edit_original_response(view=view)
        await client.change_presence(status=discord.Status.online)
        await client.change_presence(activity=discord.Game(name="server online"))
        file = io.open(config.console, mode="r", encoding="utf-8")
        line = len(file.readlines()) - 1
        while started:
            line = await console_reader(line)
    else:
        await ctx.response.send_message("server is already running", ephemeral=True)

@minecraft.command(name="stop", description="stop minecraft server", guild=discord.Object(id=config.guild_id))
async def mc_stop(ctx: discord.Interaction):
    await client.change_presence(status=discord.Status.idle)
    await client.change_presence(activity=discord.Game(name="server offline"))
    try:
        with MCRcon(config.rcon_ip, config.rcon_pass) as mcr:
            mcr.command("stop")
            mcr.disconnect()
            await ctx.response.send_message("server stopped")
            print("server stopped")
            global started, panel, start_button_state, stop_button_state
            started = False
            start_button_state = True
            stop_button_state = False
            if panel is not None:
                view = await control_panel(start_button_state, stop_button_state)
                await panel.edit_original_response(view=view)
    except Exception:
        await ctx.response.send_message("server is already stopped", ephemeral=True)

@minecraft.command(name="status", description="server status", guild=discord.Object(id=config.guild_id))
async def mc_status(ctx: discord.Interaction, ip: str = config.server_ip):
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

@minecraft.command(name="render", description="render server map", guild=discord.Object(id=config.guild_id))
async def mc_render(ctx: discord.Interaction):
    await ctx.response.send_message("in developing")

@client.event
async def on_message(message: discord.Message):
    if message.author != client.user:
        if message.channel.id == config.chat_channel_id:
            if len(f"<{message.author.name}> {message.content}") < 800 and len(message.content) > 0:
                with MCRcon(config.rcon_ip, config.rcon_pass) as mcr:
                    mcr.command(f"tellraw @a [\"\",{{\"text\":\"<{message.author.name}>\",\"bold\":true,\"color\":\"#7289DA\",\"clickEvent\":{{\"action\":\"copy_to_clipboard\",\"value\":\"{message.author.name}#{message.author.discriminator}\"}},\"hoverEvent\":{{\"action\":\"show_text\",\"contents\":\"{message.author.name}#{message.author.discriminator}\"}}}},{{\"text\":\" {message.content}\"}}]")
                mcr.disconnect()
            else:
                await message.add_reaction("💀")
        if message.channel.id == config.console_channel_id:
            if 0 < len(message.content) < 256:
                with MCRcon(config.rcon_ip, config.rcon_pass) as mcr:
                    resp = mcr.command(message.content)
                    if resp == "Stopping the server":
                        resp = "server stopped"
                        print("server stopped")
                        global started, panel, start_button_state, stop_button_state
                        started = False
                        start_button_state = True
                        stop_button_state = False
                        if panel is not None:
                            view = await control_panel(start_button_state, stop_button_state)
                            await panel.edit_original_response(view=view)
                    await message.reply(resp, mention_author=False)
                mcr.disconnect()
            else:
                await message.add_reaction("💀")

async def console_reader(line):
    chat_channel = client.get_channel(config.chat_channel_id)
    console_channel = client.get_channel(config.console_channel_id)
    file = io.open(config.console, mode="r", encoding="utf-8")
    line_list = file.readlines()
    while line < len(line_list):
        if re.match(r"\[[0-9][0-9]:[0-9][0-9]:[0-9][0-9] INFO\]: (.+?) issued server command: /stop", line_list[line]):
            await console_channel.send(line_list[line])
            message = await console_channel.fetch_message(console_channel.last_message_id)
            await message.reply("server stopped")
            print("server stopped")
            global started, panel, start_button_state, stop_button_state
            started = False
            start_button_state = True
            stop_button_state = False
            if panel is not None:
                view = await control_panel(start_button_state, stop_button_state)
                await panel.edit_original_response(view=view)
            break
        nickname = re.search(r"<(.+?)>", line_list[line])
        if nickname is not None:
            await chat_channel.send(f"**{nickname.group(1)}**:{line_list[line][line_list[line].find('>') + 1:]}")
        else:
            await console_channel.send(line_list[line])
        line += 1
    await asyncio.sleep(0)
    return line

client.run(config.token)
