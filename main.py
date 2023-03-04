import discord
import discord.utils
from discord.ui import Button, View
from discord.ext import commands
from mcstatus import JavaServer
from mcrcon import MCRcon
from datetime import datetime
import config
import os
import asyncio
import io
import re

intents = discord.Intents.all()
intents.message_content = True
client = commands.Bot(intents=intents)
started = False
start_button_state = True
stop_button_state = False
restart_button_state = False
panel: discord.Interaction = None
panel_message: discord.Message = None
console_output = False
global_interaction: discord.Interaction = None
stop_already_called = False
nickname = None
console_thread: discord.Thread = None
start_time = None
restart = False

@client.check
async def guild_only(ctx: discord.Interaction):
    if not ctx.guild:
        await ctx.response.send_message("this command cannot be used in private messages")
        raise commands.NoPrivateMessage
    return True

@client.event
async def on_ready():
    global panel, start_button_state, stop_button_state, panel_message
    await client.get_channel(config.control_panel_channel_id).purge(limit=100)
    view = await create_buttons(start_button_state, stop_button_state, restart_button_state)
    embed = await create_embed()
    panel = await client.get_channel(config.control_panel_channel_id).send(view=view, embed=embed)
    panel_message = panel
    print("ready")

async def create_embed():
    embed = discord.Embed(title="deoxce.online", description=f"version: Paper 1.19.2\nnumber of players: 0/20\ndescription: горгород", color=5793266)
    embed.set_thumbnail(url="https://media.discordapp.net/attachments/1079418060471029811/1079418094570713219/9ad038f8dad28f1da51442938f5f1d83.jpg")
    embed.set_image(url="https://i.imgur.com/7PLfKFI.gif")
    return embed

async def create_buttons(start_button_state, stop_button_state, restart_button_state):
    view = View(timeout=None)
    button_start = Button(label="ᅠᅠ►︎ᅠᅠ", style=discord.ButtonStyle.blurple, disabled=not start_button_state)
    button_stop = Button(label="ᅠᅠ◼︎ᅠᅠ", style=discord.ButtonStyle.blurple, disabled=not stop_button_state)
    button_restart = Button(label="ᅠᅠ↺︎ᅠᅠ", style=discord.ButtonStyle.blurple, disabled=not restart_button_state)
    if config.dynmap:
        button_render = Button(label="ᅠᅠ☲︎ᅠ", style=discord.ButtonStyle.blurple, url=f'http://{config.server_ip}:{config.dynmap_port}')
    else:
        button_render = Button(label="render", style=discord.ButtonStyle.blurple)
        button_render.callback = server_map
    button_start.callback = server_start
    button_stop.callback = server_stop
    button_restart.callback = server_restart
    view.add_item(button_start)
    view.add_item(button_stop)
    view.add_item(button_restart)
    view.add_item(button_render)
    return view

def permission_check(func):
    async def wrapper(ctx: discord.Interaction):
        role = discord.utils.find(lambda r: r.name == config.server_admin_role_name, ctx.message.guild.roles)
        if role in ctx.user.roles:
            await func(ctx)
        else:
            await ctx.response.send_message("you do not have permission", ephemeral=True)
    return wrapper

@permission_check
@client.slash_command(name="start", description="start minecraft server", guild=discord.Object(id=config.guild_id))
async def server_start(ctx: discord.Interaction):
    global started, panel, start_button_state, stop_button_state, panel_message, console_output, console_thread, start_time, restart_button_state, restart
    if not started:
        start_button_state = False
        view = await create_buttons(start_button_state, stop_button_state, restart_button_state)
        embed = await create_embed()
        await panel_message.edit(view=view)
        if panel_message.thread:
            if config.console_archiving is True:
                panel = await panel_message.channel.send(view=view, embed=embed)
                await panel_message.delete()
                panel_message = panel
        os.startfile(config.run_bat)
        if restart is False:
            await ctx.response.defer(ephemeral=False, invisible=False)
        print("server is starting")
        server = JavaServer.lookup(f"{config.server_ip}:{config.server_port}", timeout=3)
        while not started:
            try:
                status = server.status()
                if status:
                    started = True
            except Exception:
                print("starting..")
        console_thread = await panel_message.create_thread(name="console")
        start_time = datetime.now()
        await ctx.delete_original_response()
        restart = False
        print("server started")
        stop_button_state = True
        if config.console_archiving is False:
            restart_button_state = True
        view = await create_buttons(start_button_state, stop_button_state, restart_button_state)
        await panel_message.edit(view=view)
        file = io.open(config.console, mode="r", encoding="utf-8")
        line = len(file.readlines()) - 1
        console_output = True
        while started:
            line = await console_reader(line)
    else:
        await ctx.response.send_message("server is already running", ephemeral=True)

@permission_check
@client.slash_command(name="stop", description="stop minecraft server", guild=discord.Object(id=config.guild_id))
async def server_stop(ctx: discord.Interaction):
    global stop_already_called
    if not stop_already_called:
        try:
            with MCRcon(config.server_ip, config.rcon_pass) as mcr:
                global global_interaction, restart
                await stop()
                stop_already_called = True
                mcr.command("stop")
                mcr.disconnect()
                if restart is False:
                    await ctx.response.defer(ephemeral=False, invisible=False)
                    global_interaction = ctx
        except Exception:
            await ctx.response.send_message("server is already stopped", ephemeral=True)

@permission_check
@client.slash_command(name="restart", description="restart minecraft server", guild=discord.Object(id=config.guild_id))
async def server_restart(ctx: discord.Interaction):
    if started == True:
        global restart
        restart = True
        await ctx.response.defer(ephemeral=False, invisible=False)
        await server_stop(ctx)
        while True:
            await asyncio.sleep(0)
            if started == False:
                await server_start(ctx)
                break

@client.slash_command(name="map", description="server map", guild=discord.Object(id=config.guild_id))
async def server_map(ctx: discord.Interaction):
    if config.dynmap:
        await ctx.response.send_message(f'http://{config.server_ip}:{config.dynmap_port}')
    else:
        await ctx.response.send_message("in developing")

async def stop():
    global console_output, stop_button_state, restart_button_state, panel_message, console_thread, start_time
    print("server is stopping")
    console_output = False
    stop_button_state = False
    restart_button_state = False
    view = await create_buttons(start_button_state, stop_button_state, restart_button_state)
    await panel_message.edit(view=view)
    if config.console_archiving is True:
        await console_thread.edit(name=start_time, archived=True, locked=True)
    else:
        await panel_message.thread.delete()

@client.event
async def on_message(message: discord.Message):
    global console_thread
    if message.author != client.user:
        if message.channel.id == config.chat_channel_id:
            if len(f"<{message.author.name}> {message.content}") < 800 and len(message.content) > 0:
                with MCRcon(config.server_ip, config.rcon_pass) as mcr:
                    mcr.command(f"tellraw @a [\"\",{{\"text\":\"<{message.author.name}>\",\"bold\":true,\"color\":\"#7289DA\",\"clickEvent\":{{\"action\":\"copy_to_clipboard\",\"value\":\"{message.author.name}#{message.author.discriminator}\"}},\"hoverEvent\":{{\"action\":\"show_text\",\"contents\":\"{message.author.name}#{message.author.discriminator}\"}}}},{{\"text\":\" {message.content}\"}}]")
                mcr.disconnect()
            else:
                await message.add_reaction("💀")
        if console_thread and message.channel.id == console_thread.id:
            if 0 < len(message.content) < 256:
                with MCRcon(config.server_ip, config.rcon_pass) as mcr:
                    resp = mcr.command(message.content)
                    if resp == "Stopping the server":
                        await stop()
                    elif resp:
                        await message.reply(resp, mention_author=False)
                mcr.disconnect()
            else:
                await message.add_reaction("💀")

async def console_reader(line):
    global started, start_button_state, stop_button_state, panel_message, console_output, global_interaction, stop_already_called, nickname, console_thread, restart_button_state, restart
    chat_channel = client.get_channel(config.chat_channel_id)
    file = io.open(config.console, mode="r", encoding="utf-8")
    line_list = file.readlines()
    while line < len(line_list):
        if re.match(r"\[[0-9][0-9]:[0-9][0-9]:[0-9][0-9] INFO\]: (.+?) issued server command: /stop", line_list[line]):
            await stop()
            await console_thread.send(line_list[line])
        if re.match(r"\[[0-9][0-9]:[0-9][0-9]:[0-9][0-9] INFO\]: Closing Server", line_list[line]):
            if global_interaction is not None:
                await global_interaction.delete_original_response()
            global_interaction = None
            stop_already_called = False
            started = False
            print("server stopped")
            if restart is False:
                start_button_state = True
            view = await create_buttons(start_button_state, stop_button_state, restart_button_state)
            await panel_message.edit(view=view)
            break
        if console_output:
            nickname = re.search(r"<(.+?)>", line_list[line])
            if nickname is not None:
                await chat_channel.send(f"**{nickname.group(1)}**:{line_list[line][line_list[line].find('>') + 1:]}")
            await console_thread.send(line_list[line])
        line += 1
    await asyncio.sleep(0)
    return line

client.run(config.token)