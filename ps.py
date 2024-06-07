import discord
from discord.ext import tasks
import asyncio
import os
import io
from keep_alive import keep_alive  # Import the keep_alive function

# Load environment variable securely (assuming .env file exists)
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

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

class ForwardingBot(discord.Client):

    def __init__(self):
        from discord import Intents
        intents = Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.last_message_ids = {channel_id: None for channel_id in SOURCE_CHANNEL_IDS}
        self.forwarded_messages = {}  # Dictionary to keep track of forwarded messages

    async def process_message(self, message):
        if message.attachments:
            content = message.content.strip() if message.content else ""
            attachment = message.attachments[0]
            file_content = await attachment.read()

            for destination_channel_id in DESTINATION_CHANNEL_IDS:
                destination_channel = self.get_channel(destination_channel_id)
                if not destination_channel:
                    continue

                try:
                    if content:
                        forwarded_message = await destination_channel.send(content=content)
                    forwarded_image = await destination_channel.send(file=discord.File(io.BytesIO(file_content), filename=attachment.filename, spoiler=attachment.is_spoiler()))

                    self.forwarded_messages[message.id] = (message.channel.id, destination_channel_id)  # Store the forwarded message details
                except discord.HTTPException:
                    continue
        else:
            await asyncio.sleep(3)
            updated_message = await message.channel.fetch_message(message.id)
            if updated_message.attachments:
                await self.process_message(updated_message)

    @tasks.loop(seconds=10)
    async def forward_task(self):
        for source_channel_id in SOURCE_CHANNEL_IDS:
            source_channel = self.get_channel(source_channel_id)
            if not source_channel:
                continue

            async for message in source_channel.history(limit=1):
                if self.last_message_ids[source_channel_id] is None or message.id != self.last_message_ids[source_channel_id]:
                    self.last_message_ids[source_channel_id] = message.id
                    # Check if the message has already been forwarded from another source channel
                    if message.id not in self.forwarded_messages:
                        await self.process_message(message)

    async def on_message_delete(self, message):
        if message.id in self.forwarded_messages:
            source_channel_id, destination_channel_id = self.forwarded_messages[message.id]
            if source_channel_id in SOURCE_CHANNEL_IDS:
                destination_channel = self.get_channel(destination_channel_id)
                if destination_channel:
                    try:
                        forwarded_message = await destination_channel.fetch_message(message.id)
                        await forwarded_message.delete()
                    except discord.HTTPException:
                        pass
                del self.forwarded_messages[message.id]

    async def on_ready(self):
        self.forward_task.start()

if __name__ == '__main__':
    keep_alive()  # Call the keep_alive function to start the Flask server
    bot = ForwardingBot()
    bot.run(BOT_TOKEN)
