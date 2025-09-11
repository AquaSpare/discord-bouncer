# Carmen Discord Bouncer Bot

A Discord bot that acts as a bouncer for a bar in Stockholm called Carmen. It uses AI to assess if users are sober enough to enter the bar’s voice channel.

## Setup

1. Install dependencies:
   ```sh
   uv sync
   ```

2. Set environment variables in a `.env` file:
   ```
   AZURE_OPENAI_API_KEY=
   DISCORD_API_KEY=
   DISCORD_ANNOUNCE_CHANNEL_ID=
   DISCORD_VOICE_CHANNEL_ID=
   DISCORD_GUILD_ID=
   DISCORD_QUEUE_CHANNEL_ID=
   ```

3. Run the bot:
   ```sh
   python main.py
   ```

## Features

- AI-powered sobriety assessment via DM
- Blacklist for users denied entry
- Voice channel queue management

---
See [mybot/bot.py](mybot/bot.py) and [mybot/agent.py](mybot/agent.py) for core logic.