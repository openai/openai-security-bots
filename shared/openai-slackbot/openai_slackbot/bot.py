import typing as t
from logging import getLogger

import openai
from openai_slackbot.clients.slack import SlackClient
from openai_slackbot.handlers import BaseActionHandler, BaseMessageHandler
from openai_slackbot.utils.envvars import string
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.app.async_app import AsyncApp

logger = getLogger(__name__)


async def register_app_handlers(
    *,
    app: AsyncApp,
    message_handler: t.Type[BaseMessageHandler],
    action_handlers: t.List[t.Type[BaseActionHandler]],
    slack_client: SlackClient,
):
    if message_handler:
        app.event("message")(message_handler(slack_client).maybe_handle)

    if action_handlers:
        for action_handler in action_handlers:
            handler = action_handler(slack_client)
            app.action(handler.action_id)(handler.maybe_handle)


async def init_bot(
    *,
    openai_organization_id: str,
    slack_message_handler: t.Type[BaseMessageHandler],
    slack_action_handlers: t.List[t.Type[BaseActionHandler]],
    slack_template_path: str,
):
    slack_bot_token = string("SLACK_BOT_TOKEN")
    openai_api_key = string("OPENAI_API_KEY")

    # Init OpenAI API
    openai.organization = openai_organization_id
    openai.api_key = openai_api_key

    # Init slack bot
    app = AsyncApp(token=slack_bot_token)
    slack_client = SlackClient(app.client, slack_template_path)
    await register_app_handlers(
        app=app,
        message_handler=slack_message_handler,
        action_handlers=slack_action_handlers,
        slack_client=slack_client,
    )

    return app


async def start_app(app):
    socket_app_token = string("SOCKET_APP_TOKEN")
    handler = AsyncSocketModeHandler(app, socket_app_token)
    await handler.start_async()


async def start_bot(
    *,
    openai_organization_id: str,
    slack_message_handler: t.Type[BaseMessageHandler],
    slack_action_handlers: t.List[t.Type[BaseActionHandler]],
    slack_template_path: str,
):
    app = await init_bot(
        openai_organization_id=openai_organization_id,
        slack_message_handler=slack_message_handler,
        slack_action_handlers=slack_action_handlers,
        slack_template_path=slack_template_path,
    )

    await start_app(app)
