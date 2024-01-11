import asyncio
import os

from incident_response_slackbot.config import load_config, get_config
from incident_response_slackbot.handlers import (
    InboundDirectMessageHandler,
    InboundIncidentDoNothingHandler,
    InboundIncidentEndChatHandler,
    InboundIncidentStartChatHandler,
)
from openai_slackbot.bot import start_bot

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    load_config(os.path.join(current_dir, "config.toml"))

    message_handler = InboundDirectMessageHandler
    action_handlers = [
        InboundIncidentStartChatHandler,
        InboundIncidentDoNothingHandler,
        InboundIncidentEndChatHandler,
    ]

    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

    config = get_config()
    asyncio.run(
        start_bot(
            openai_organization_id=config.openai_organization_id,
            slack_message_handler=message_handler,
            slack_action_handlers=action_handlers,
            slack_template_path=template_path,
        )
    )
