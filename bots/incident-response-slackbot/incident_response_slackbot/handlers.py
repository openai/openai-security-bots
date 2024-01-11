import os
import pickle
import typing as t
from enum import Enum
from logging import getLogger

from incident_response_slackbot.config import load_config, get_config
from incident_response_slackbot.db.database import Database
from incident_response_slackbot.openai_utils import (
    create_greeting,
    generate_awareness_question,
    get_thread_summary,
    get_user_awareness,
    messages_to_string,
)
from openai_slackbot.handlers import BaseActionHandler, BaseMessageHandler

logger = getLogger(__name__)

DATABASE = Database()

class InboundDirectMessageHandler(BaseMessageHandler):
    """
    Handles Direct Messages for incident response use cases
    """

    def __init__(self, slack_client):
        super().__init__(slack_client)
        self.config = get_config()

    async def should_handle(self, args):
        return True

    async def handle(self, args):
        event = args.event
        user_id = event.get("user")

        if not DATABASE.user_exists(user_id):
            # If the user_id does not exist, they're not part of an active chat
            return

        message_ts = DATABASE.get_ts(user_id)
        await self.send_message_to_channel(event, message_ts)

        user_awareness = await get_user_awareness(event["text"])
        logger.info(f"User awareness decision: {user_awareness}")

        if user_awareness["has_answered"]:
            await self.handle_user_response(user_id, message_ts)
        else:
            await self.nudge_user(user_id, message_ts)

    async def send_message_to_channel(self, event, message_ts):
        # Send the received message to the monitoring channel
        await self._slack_client.post_message(
            channel=self.config.feed_channel_id,
            text=f"Received message from <@{event['user_profile']['name']}>:\n> {event['text']}",
            thread_ts=message_ts,
        )

    async def handle_user_response(self, user_id, message_ts):
        # User has answered the question
        messages = await self._slack_client.get_thread_messages(
            channel=self.config.feed_channel_id,
            thread_ts=message_ts,
        )

        # Send the end message to the user
        thank_you = "Thanks for your time!"
        await self._slack_client.post_message(
            channel=user_id,
            text=thank_you,
        )

        # Send message to the channel
        await self._slack_client.post_message(
            channel=self.config.feed_channel_id,
            text=f"Sent message to <@{user_id}>:\n> {thank_you}",
            thread_ts=message_ts,
        )

        summary = await get_thread_summary(messages)

        # Send message to the channel
        await self._slack_client.post_message(
            channel=self.config.feed_channel_id,
            text=f"Here is the summary of the chat:\n> {summary}",
            thread_ts=message_ts,
        )

        DATABASE.delete(user_id)

        await self.end_chat(message_ts)

    async def end_chat(self, message_ts):
        original_blocks = await self._slack_client.get_original_blocks(
            message_ts, self.config.feed_channel_id
        )

        # Remove action buttons and add "Chat has ended" text
        new_blocks = [block for block in original_blocks if block.get("type") != "actions"]

        # Add the "Chat has ended" text
        new_blocks.append(
            {
                "type": "section",
                "block_id": "end_chat_automatically",
                "text": {
                    "type": "mrkdwn",
                    "text": f"The chat was automatically ended from SecurityBot review. :done_:",
                    "verbatim": True,
                },
            }
        )

        await self._slack_client.update_message(
            channel=self.config.feed_channel_id,
            blocks=new_blocks,
            ts=message_ts,
            text="Ended chat automatically",
        )

    async def nudge_user(self, user_id, message_ts):
        # User has not answered the question

        nudge_message = await generate_awareness_question()
        # Send the greeting message to the user
        await self._slack_client.post_message(
            channel=user_id,
            text=nudge_message,
        )

        # Send message to the channel
        await self._slack_client.post_message(
            channel=self.config.feed_channel_id,
            text=f"Sent message to <@{user_id}>:\n> {nudge_message}",
            thread_ts=message_ts,
        )


class InboundIncidentStartChatHandler(BaseActionHandler):
    def __init__(self, slack_client):
        super().__init__(slack_client)
        self.config = get_config()

    @property
    def action_id(self):
        return "start_chat_submit_action"

    async def handle(self, args):
        body = args.body
        original_message = body["container"]
        original_message_ts = original_message["message_ts"]
        alert_user_id = DATABASE.get_user_id(original_message_ts)
        user = body["user"]

        logger.info(f"Handling inbound incident start chat action from {user['name']}")

        # Update the blocks and elements
        blocks = self.update_blocks(body, alert_user_id)

        # Add the "Started a chat" text
        blocks.append(self.create_chat_start_section(user["id"]))

        messages = await self._slack_client.get_thread_messages(
            channel=self.config.feed_channel_id,
            thread_ts=original_message_ts,
        )

        message = await self._slack_client.update_message(
            channel=self.config.feed_channel_id,
            blocks=blocks,
            ts=original_message_ts,
            text=messages[0]["text"],
        )

        text_messages = messages_to_string(messages)
        logger.info(f"Alert and detail: {text_messages}")

        username = await self._slack_client.get_user_display_name(alert_user_id)
        greeting_message = await create_greeting(username, text_messages)
        logger.info(f"generated greeting message: {greeting_message}")

        # Send the greeting message to the user and to the channel
        await self.send_greeting_message(alert_user_id, greeting_message, original_message_ts)

        logger.info(f"Succesfully started chat with user: {username}")

        return message

    def update_blocks(self, body, alert_user_id):
        body_copy = body.copy()
        new_elements = []
        for block in body_copy.get("message", {}).get("blocks", []):
            if block.get("type") == "actions":
                for element in block.get("elements", []):
                    if element.get("action_id") == "do_nothing_submit_action":
                        element["action_id"] = "end_chat_submit_action"
                        element["text"]["text"] = "End Chat"
                        element["value"] = alert_user_id
                    new_elements.append(element)
                block["elements"] = new_elements
        return body_copy.get("message", {}).get("blocks", [])

    def create_chat_start_section(self, user_id):
        return {
            "type": "section",
            "block_id": "started_chat",
            "text": {
                "type": "mrkdwn",
                "text": f"<@{user_id}> started a chat.",
                "verbatim": True,
            },
        }

    async def send_greeting_message(self, alert_user_id, greeting_message, original_message_ts):
        # Send the greeting message to the user
        await self._slack_client.post_message(
            channel=alert_user_id,
            text=greeting_message,
        )

        # Send message to the channel
        await self._slack_client.post_message(
            channel=self.config.feed_channel_id,
            text=f"Sent message to <@{alert_user_id}>:\n> {greeting_message}",
            thread_ts=original_message_ts,
        )


class InboundIncidentDoNothingHandler(BaseActionHandler):
    """
    Handles incoming alerts and decides whether to take no action.
    This will close the alert and mark the status as complete.
    """

    def __init__(self, slack_client):
        super().__init__(slack_client)
        self.config = get_config()

    @property
    def action_id(self):
        return "do_nothing_submit_action"

    async def handle(self, args):
        body = args.body
        user_id = body["user"]["id"]
        original_message_ts = body["message"]["ts"]

        # Remove action buttons and add "Chat has ended" text
        new_blocks = [
            block
            for block in body.get("message", {}).get("blocks", [])
            if block.get("type") != "actions"
        ]

        # Add the "Chat has ended" text
        new_blocks.append(
            {
                "type": "section",
                "block_id": "do_nothing",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{user_id}> decided that no action was necessary :done_:",
                    "verbatim": True,
                },
            }
        )

        await self._slack_client.update_message(
            channel=self.config.feed_channel_id,
            blocks=new_blocks,
            ts=original_message_ts,
            text="Do Nothing action selected",
        )


class InboundIncidentEndChatHandler(BaseActionHandler):
    """
    Ends the chat manually
    """

    def __init__(self, slack_client):
        super().__init__(slack_client)
        self.config = get_config()

    @property
    def action_id(self):
        return "end_chat_submit_action"

    async def handle(self, args):
        body = args.body
        user_id = body["user"]["id"]
        message_ts = body["message"]["ts"]

        alert_user_id = DATABASE.get_user_id(message_ts)

        original_blocks = await self._slack_client.get_original_blocks(
            message_ts, self.config.feed_channel_id
        )

        # Remove action buttons and add "Chat has ended" text
        new_blocks = [block for block in original_blocks if block.get("type") != "actions"]

        # Add the "Chat has ended" text
        new_blocks.append(
            {
                "type": "section",
                "block_id": "end_chat_manually",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{user_id}> has ended the chat :done_:",
                    "verbatim": True,
                },
            }
        )

        await self._slack_client.update_message(
            channel=self.config.feed_channel_id,
            blocks=new_blocks,
            ts=message_ts,
            text="Ended chat automatically",
        )

        # User has answered the question
        messages = await self._slack_client.get_thread_messages(
            channel=self.config.feed_channel_id,
            thread_ts=message_ts,
        )

        thank_you = "Thanks for your time!"
        await self._slack_client.post_message(
            channel=alert_user_id,
            text=thank_you,
        )

        # Send message to the channel
        await self._slack_client.post_message(
            channel=self.config.feed_channel_id,
            text=f"Sent message to <@{alert_user_id}>:\n> {thank_you}",
            thread_ts=message_ts,
        )

        summary = await get_thread_summary(messages)

        # Send message to the channel
        await self._slack_client.post_message(
            channel=self.config.feed_channel_id,
            text=f"Here is the summary of the chat:\n> {summary}",
            thread_ts=message_ts,
        )

        DATABASE.delete(user_id)
