# This example requires the 'message_content' intent.


import discord
from discord import Message

from agent import Desicion, agent
from settings import settings

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Needed to move members

client = discord.Client(intents=intents)

user_histories = {}
blacklist = []


@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")
    channel = client.get_channel(settings.DISCORD_ANNOUNCE_CHANNEL_ID)
    if channel and hasattr(channel, "send"):
        await channel.send(
            "The bar is now open! Enter the queue and message me to request entry."
        )
    elif channel:
        print(
            f"Channel with ID {settings.DISCORD_ANNOUNCE_CHANNEL_ID} is not a text channel or thread."
        )
    else:
        print(f"Channel with ID {settings.DISCORD_ANNOUNCE_CHANNEL_ID} not found.")


@client.event
async def on_message(message: Message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Only handle private messages (DMs)
    if not isinstance(message.channel, discord.DMChannel):
        return

    user_id = message.author.id
    guild = client.get_guild(settings.DISCORD_GUILD_ID)
    if not guild:
        await message.channel.send("Server not found.")
        return

    member = guild.get_member(user_id)
    if not member:
        await message.channel.send("Could not find you in the server.")
        return

    queue_channel = guild.get_channel(settings.DISCORD_QUEUE_CHANNEL_ID)
    bar_channel = guild.get_channel(settings.DISCORD_VOICE_CHANNEL_ID)

    if not (queue_channel and isinstance(queue_channel, discord.VoiceChannel)):
        await message.channel.send("Queue voice channel not found.")
        return
    if not (bar_channel and isinstance(bar_channel, discord.VoiceChannel)):
        await message.channel.send("Bar voice channel not found.")
        return

    if user_id in blacklist:
        return await message.channel.send(
            "Sorry you aint getting in today mate, go home and get some sleep"
        )

    # Check if user is in the queue channel
    if not (
        member.voice
        and member.voice.channel
        and member.voice.channel.id == queue_channel.id
    ):
        await message.channel.send(
            f"Please join the queue voice channel first: {queue_channel.name}"
        )
        return

    # Move user to bar channel
    try:
        result = await agent.run(
            message.content, message_history=user_histories.get(user_id)
        )
        user_histories[user_id] = result.all_messages()

        match result.output.desicion:
            case Desicion.let_in:
                await member.move_to(bar_channel)
            case Desicion.dont_let_in:
                blacklist.append(user_id)

        await message.channel.send(result.output.response)
    except Exception as e:
        await message.channel.send(f"Could not move you to the voice channel: {e}")


client.run(settings.DISCORD_API_KEY)
