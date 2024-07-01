import discord
from discord.ext import commands, tasks
import asyncio
import os
import io
from keep_alive import keep_alive  # Import the keep_alive function
import logging

# Load environment variable securely (assuming .env file exists)
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

print(f"Loaded BOT_TOKEN: {BOT_TOKEN}")

# Channel IDs (replace with your actual channel IDs)
SOURCE_CHANNEL_IDS = [
    863803391239127090,
    1248563358995709962
    # Add more source channel IDs here as needed
]
DESTINATION_CHANNEL_IDS = [
    1248563406101942282,
    1248574132417724518,
    1248623054226067577
]

NOTIFY_CHANNEL_ID = 1228948429019811940
ROLE_IDS_CHANNEL_ID = 1228948547827925104
COMMAND_CHANNEL_ID = 1228986706632380416

ROLE_IDS = {
    'THS': 1228968673352355930,
    'HDWLK': 1228968453986324581,
    'PGBM': 1228968582445269133,
    'OMA': 1231220871805538456
}

SERIES_NAMES = {
    'THS': 'The High Society',
    'HDWLK': 'How Did We get here Lee Jikyung',
    'OMA': 'Office Menace Alert',
    'PGBM': 'Playing a game with my busty Manager'
}

MENTION_IDS = [1236547725747556392, 1228969150039457833]

logging.basicConfig(level=logging.DEBUG)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

class ForwardingBot(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.last_message_ids = {channel_id: None for channel_id in SOURCE_CHANNEL_IDS}
        self.forwarded_messages = {}  # Dictionary to keep track of forwarded messages
        self.forward_task.start()

    async def process_message(self, message):
        if message.attachments:
            content = message.content.strip() if message.content else ""
            attachment = message.attachments[0]
            file_content = await attachment.read()

            for destination_channel_id in DESTINATION_CHANNEL_IDS:
                destination_channel = self.bot.get_channel(destination_channel_id)
                if not destination_channel:
                    continue

                try:
                    if content:
                        forwarded_message = await destination_channel.send(content=content)
                    forwarded_image = await destination_channel.send(file=discord.File(io.BytesIO(file_content), filename=attachment.filename, spoiler=attachment.is_spoiler()))

                    self.forwarded_messages[message.id] = (message.channel.id, destination_channel_id)  # Store the forwarded message details
                except discord.HTTPException as e:
                    logging.error(f"HTTPException while forwarding message: {e}")
                    if e.status == 429:
                        retry_after = e.response.headers.get('Retry-After')
                        await asyncio.sleep(float(retry_after))
                        await self.process_message(message)
        else:
            await asyncio.sleep(3)
            updated_message = await message.channel.fetch_message(message.id)
            if updated_message.attachments:
                await self.process_message(updated_message)

    @tasks.loop(seconds=10)
    async def forward_task(self):
        for source_channel_id in SOURCE_CHANNEL_IDS:
            source_channel = self.bot.get_channel(source_channel_id)
            if not source_channel:
                continue

            async for message in source_channel.history(limit=1):
                if self.last_message_ids[source_channel_id] is None or message.id != self.last_message_ids[source_channel_id]:
                    self.last_message_ids[source_channel_id] = message.id
                    # Check if the message has already been forwarded from another source channel
                    if message.id not in self.forwarded_messages:
                        await self.process_message(message)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.id in self.forwarded_messages:
            source_channel_id, destination_channel_id = self.forwarded_messages[message.id]
            if source_channel_id in SOURCE_CHANNEL_IDS:
                destination_channel = self.bot.get_channel(destination_channel_id)
                if destination_channel:
                    try:
                        forwarded_message = await destination_channel.fetch_message(message.id)
                        await forwarded_message.delete()
                    except discord.HTTPException:
                        pass
                del self.forwarded_messages[message.id]

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info(f'Logged in as {self.bot.user} (ID: {self.bot.user.id})')
        logging.info('------')

    @commands.command(name='notify')
    async def notify_command(self, ctx, series_abbreviation: str, chapter_number: int, vip_duration: int):
        if ctx.channel.id != COMMAND_CHANNEL_ID:
            return

        if series_abbreviation not in SERIES_NAMES or series_abbreviation not in ROLE_IDS:
            await ctx.send(f"Unknown series abbreviation: {series_abbreviation}")
            return

        series_name = SERIES_NAMES[series_abbreviation]
        role_id = ROLE_IDS[series_abbreviation]

        # Notify immediately
        notify_channel = self.bot.get_channel(NOTIFY_CHANNEL_ID)
        if notify_channel:
            mention_str = " ".join([f"<@&{mention_id}>" for mention_id in MENTION_IDS])
            await notify_channel.send(f"{series_name} ({series_abbreviation}) has been released for {mention_str}")

        # Notify after VIP duration
        await asyncio.sleep(vip_duration * 60)  # Convert minutes to seconds
        role_notify_channel = self.bot.get_channel(ROLE_IDS_CHANNEL_ID)
        if role_notify_channel:
            await role_notify_channel.send(f"{series_name} ({series_abbreviation}) chapter {chapter_number} has been released for <@&{role_id}>")

        # Notify in the specific series channel
        series_channel = self.bot.get_channel(ROLE_IDS[series_abbreviation])
        if series_channel:
            await series_channel.send(f"{series_name} ({series_abbreviation}) Chapter {chapter_number} has been released <@&{role_id}>")

bot.add_cog(ForwardingBot(bot))

if __name__ == '__main__':
    keep_alive()  # Call the keep_alive function to start the Flask server
    try:
        bot.run(BOT_TOKEN)
    except discord.HTTPException as e:
        logging.error(f"HTTPException: {e.response.status}, {e.response.reason}, {e.text}")
        logging.error(f"Failed to run the bot: {e}")
