"""Discord title entry; interpretation and confirmation remain in n8n."""
import time
import discord


class RequestTitleModal(discord.ui.Modal, title='What would you like to watch?'):
    title_input = discord.ui.TextInput(label='Movie or series title',
        placeholder='The Matrix from 1999, or Severance', max_length=1600)

    def __init__(self, client, owner):
        super().__init__(timeout=300)
        self.client, self.owner, self.deadline = client, owner, time.time()+300

    async def on_submit(self, interaction):
        if str(interaction.user.id) != self.owner or time.time() >= self.deadline:
            await interaction.response.send_message('This request form expired. Use /request to reopen.', ephemeral=True)
            return
        await self.client.request_command(interaction, str(self.title_input.value))
