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
panel: discord.Interaction = None
control_panel_id = None
view = None

@client.event
async def on_ready():
    print("ready")

@client.slash_command(name="server", description="server control panel", guild=discord.Object(id=config.guild_id))
async def server(ctx: discord.Interaction):
    global panel
    if panel is not None:
        await panel.delete_original_response()
    global view
    if view == None:
        view = Menu()
    panel = await ctx.response.send_message("control panel", view=view)
    current_channel = client.get_channel(ctx.channel_id)
    global control_panel_id
    control_panel_id = current_channel.last_message_id

class Menu(View):
    @discord.ui.button(label="start", style=discord.ButtonStyle.green, disabled=False, custom_id="start_button")
    async def start_button_callback(self, button: discord.ui.Button, ctx: discord.Interaction):
        stop_button = [x for x in self.children if x.custom_id == "stop_button"][0]
        button.disabled = True
        await ctx.response.edit_message(view=self)
        await mc_start(ctx, stop_button, self)

    @discord.ui.button(label="stop", style=discord.ButtonStyle.red, disabled=True, custom_id="stop_button")
    async def stop_button_callback(self, button: discord.ui.Button, ctx: discord.Interaction):
        start_button = [x for x in self.children if x.custom_id == "start_button"][0]
        button.disabled = True
        await ctx.response.edit_message(view=self)
        await mc_stop(ctx, start_button, self)

    @discord.ui.button(label="status", style=discord.ButtonStyle.blurple)
    async def status_button_callback(self, button: discord.ui.Button, ctx: discord.Interaction):
        await mc_status(ctx)

    @discord.ui.button(label="render", style=discord.ButtonStyle.blurple)
    async def render_button_callback(self, button: discord.ui.Button, ctx: discord.Interaction):
        await mc_render(ctx)

minecraft = client.create_group(name="minecraft", guild=discord.Object(id=config.guild_id))

#@minecraft.command(name="start", description="start minecraft server", guild=discord.Object(id=config.guild_id))
async def mc_start(ctx: discord.Interaction, stop_button, self):
    global started
    if not started:
        os.startfile(config.run_bat)
        server = JavaServer.lookup(config.server_ip)
        await ctx.followup.send("server is starting")
        while not started:
            try:
                status = server.status()
                if status:
                    started = True
            except Exception:
                print("starting..")
        await ctx.channel.send("server started")
        print("server started")
        stop_button.disabled = False
        global view
        view = self
        await ctx.followup.edit_message(control_panel_id, view=self)
        await client.change_presence(status=discord.Status.online)
        await client.change_presence(activity=discord.Game(name="server online"))
        file = io.open(config.console, mode="r", encoding="utf-8")
        line = len(file.readlines()) - 1
        while started:
            line = await console_reader(line)
    else:
        await ctx.response.send_message("server is already running", ephemeral=True)

#@minecraft.command(name="stop", description="stop minecraft server", guild=discord.Object(id=config.guild_id))
async def mc_stop(ctx: discord.Interaction, start_button, self):
    await client.change_presence(status=discord.Status.idle)
    await client.change_presence(activity=discord.Game(name="server offline"))
    try:
        with MCRcon(config.rcon_ip, config.rcon_pass) as mcr:
            mcr.command("stop")
            mcr.disconnect()
            global started
            started = False
            await ctx.followup.send("server stopped")
            print("server stopped")
            start_button.disabled = False
            global view
            view = self
            await ctx.followup.edit_message(control_panel_id, view=self)
    except Exception:
        await ctx.response.send_message("server is already stopped", ephemeral=True)

@minecraft.command(name="status", description="server status", guild=discord.Object(id=config.guild_id))
async def mc_status(ctx: discord.Interaction, ip: str = config.server_ip):
    if ip.find(":") == -1:
        ip += ":25565"
    server = JavaServer.lookup(ip, timeout=1)
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
                        global started
                        started = False
                        print("server stopped")
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
            global started
            started = False
            await console_channel.send(line_list[line])
            message = await console_channel.fetch_message(console_channel.last_message_id)
            await message.reply("server stopped")
            print("server stopped")
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
