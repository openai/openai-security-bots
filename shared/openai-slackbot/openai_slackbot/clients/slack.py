import json
import os
import typing as t
from logging import getLogger

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

logger = getLogger(__name__)


class SlackMessage(BaseModel):
    app_id: t.Optional[str] = None
    blocks: t.Optional[t.List[t.Any]] = None
    bot_id: t.Optional[str] = None
    bot_profile: t.Optional[t.Dict[str, t.Any]] = None
    team: str
    text: str
    ts: str
    type: str
    user: t.Optional[str] = None


class CreateSlackMessageResponse(BaseModel):
    ok: bool
    channel: str
    ts: str
    message: SlackMessage


class SlackClient:
    """
    SlackClient wraps the Slack AsyncWebClient implementation and
    provides some additional functionality specific to the Slackbot
    implementation.
    """

    def __init__(self, client: AsyncWebClient, template_path: str) -> None:
        self._client = client
        self._jinja = self._init_jinja(template_path)

    async def get_message_link(self, **kwargs) -> str:
        response = await self._client.chat_getPermalink(**kwargs)
        if not response["ok"]:
            raise Exception(f"Failed to get Slack message link: {response['error']}")
        return response["permalink"]

    async def get_message(self, channel: str, ts: str) -> t.Optional[t.Dict[str, t.Any]]:
        """Follows: https://api.slack.com/messaging/retrieving."""
        result = await self._client.conversations_history(
            channel=channel,
            inclusive=True,
            latest=ts,
            limit=1,
        )
        return result["messages"][0] if result["messages"] else None

    async def post_message(self, **kwargs) -> CreateSlackMessageResponse:
        response = await self._client.chat_postMessage(**kwargs)
        if not response["ok"]:
            raise Exception(f"Failed to post Slack message: {response['error']}")

        assert isinstance(response.data, dict)
        return CreateSlackMessageResponse(**response.data)

    async def update_message(self, **kwargs) -> t.Dict[str, t.Any]:
        response = await self._client.chat_update(**kwargs)
        if not response["ok"]:
            raise Exception(f"Failed to update Slack message: {response['error']}")

        assert isinstance(response.data, dict)
        return response.data

    async def add_reaction(self, **kwargs) -> t.Dict[str, t.Any]:
        try:
            response = await self._client.reactions_add(**kwargs)
        except SlackApiError as e:
            if e.response["error"] == "already_reacted":
                return {}
            raise e

        assert isinstance(response.data, dict)
        return response.data

    async def get_thread_messages(self, channel: str, thread_ts: str) -> t.List[t.Dict[str, t.Any]]:
        response = await self._client.conversations_replies(channel=channel, ts=thread_ts)
        if not response["ok"]:
            raise Exception(f"Failed to get thread messages: {response['error']}")

        assert isinstance(response.data, dict)
        return response.data["messages"]

    async def get_user_display_name(self, user_id: str) -> str:
        response = await self._client.users_info(user=user_id)
        if not response["ok"]:
            raise Exception(f"Failed to get user info: {response['error']}")
        return response["user"]["profile"]["display_name"]

    async def get_original_blocks(self, thread_ts: str, channel: str) -> None:
        """Given a thread_ts, get original message block"""
        response = await self._client.conversations_replies(
            channel=channel,
            ts=thread_ts,
        )
        try:
            messages = response.get("messages", [])
            if not messages:
                raise ValueError(f"Error fetching original message for thread_ts {thread_ts}")
            blocks = messages[0].get("blocks")
            if not blocks:
                raise ValueError(f"Error fetching original message for thread_ts {thread_ts}")
            return blocks
        except Exception as e:
            logger.exception(f"Error fetching original message for thread_ts {thread_ts}: {e}")

    def render_blocks_from_template(self, template_filename: str, context: t.Dict = {}) -> t.Any:
        rendered_template = self._jinja.get_template(template_filename).render(context)
        return json.loads(rendered_template)

    def _init_jinja(self, template_path: str):
        templates_dir = os.path.join(template_path)
        return Environment(loader=FileSystemLoader(templates_dir))
