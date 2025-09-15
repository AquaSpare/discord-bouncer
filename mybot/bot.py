# bot.py
import discord
from discord import Message
from discord.ext import commands
from pydantic_ai import ImageUrl

from mybot.agent import Desicion, DiscordMetadata, agent
from mybot.database import SQLiteHistoryDB
from mybot.settings import settings


class GatekeeperCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: SQLiteHistoryDB):
        self.bot = bot
        self.db = db

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"We have logged in as {self.bot.user}")
        channel = self.bot.get_channel(settings.DISCORD_ANNOUNCE_CHANNEL_ID)
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

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.DMChannel):
            return

        guild = self.bot.get_guild(settings.DISCORD_GUILD_ID)
        if not guild:
            return await message.channel.send("Server not found.")

        member = guild.get_member(message.author.id)

        print(member.display_avatar)
        print(member.display_name)

        if not member:
            return await message.channel.send("Could not find you in the server.")

        queue_channel = guild.get_channel(settings.DISCORD_QUEUE_CHANNEL_ID)
        bar_channel = guild.get_channel(settings.DISCORD_VOICE_CHANNEL_ID)

        if not (queue_channel and isinstance(queue_channel, discord.VoiceChannel)):
            return await message.channel.send("Queue voice channel not found.")
        if not (bar_channel and isinstance(bar_channel, discord.VoiceChannel)):
            return await message.channel.send("Bar voice channel not found.")

        user_key = str(message.author.id)

        # Check blacklist from DB
        if await self.db.is_blacklisted(user_key):
            return await message.channel.send(
                "Sorry you ain't getting in today mate, go home and get some sleep"
            )

        # Ensure user is in the queue VC
        if not (
            member.voice
            and member.voice.channel
            and member.voice.channel.id == queue_channel.id
        ):
            return await message.channel.send(
                f"Please join the queue voice channel first: {queue_channel.name}"
            )

        try:
            # Load history for this user
            history = await self.db.get_messages(user_key)

            # Run agent with history
            result = await agent.run(
                [message.content, ImageUrl(member.display_avatar.url)],
                message_history=history,
                deps=DiscordMetadata(discord_username=member.display_name),
            )

            # Save the new messages (append-only row)
            await self.db.add_messages(user_key, result.new_messages_json())

            # Act on decision
            match result.output.desicion:
                case Desicion.let_in:
                    await member.move_to(bar_channel)
                case Desicion.dont_let_in:
                    await self.db.set_blacklisted(user_key, True)

            # Respond with agent text
            await message.channel.send(result.output.response)

        except Exception as e:
            await message.channel.send(f"Could not move you to the voice channel: {e}")


async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    # Create DB and inject into Cog
    db = await SQLiteHistoryDB.open()
    await bot.add_cog(GatekeeperCog(bot, db))

    try:
        await bot.start(settings.DISCORD_API_KEY)
    finally:
        await db.close()
