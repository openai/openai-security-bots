from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai_slackbot.clients.slack import SlackClient
from openai_slackbot.handlers import BaseActionHandler, BaseMessageHandler


@pytest.fixture
def mock_slack_app():
    with patch("slack_bolt.app.async_app.AsyncApp") as mock_app:
        yield mock_app.return_value


@pytest.fixture
def mock_socket_mode_handler():
    with patch(
        "slack_bolt.adapter.socket_mode.async_handler.AsyncSocketModeHandler"
    ) as mock_handler:
        mock_handler_object = mock_handler.return_value
        mock_handler_object.start_async = AsyncMock()
        yield mock_handler_object


@pytest.fixture
def mock_openai():
    mock_openai = MagicMock()
    with patch.dict("sys.modules", openai=mock_openai):
        yield mock_openai


@pytest.fixture
def mock_slack_asyncwebclient():
    with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client:
        yield mock_client.return_value


@pytest.fixture
def mock_slack_client(mock_slack_asyncwebclient):
    return SlackClient(mock_slack_asyncwebclient, "template_path")


@pytest.fixture
def mock_message_handler(mock_slack_client):
    return MockMessageHandler(mock_slack_client)


@pytest.fixture
def mock_action_handler(mock_slack_client):
    return MockActionHandler(mock_slack_client)


class MockMessageHandler(BaseMessageHandler):
    def __init__(self, slack_client):
        super().__init__(slack_client)
        self.mock_handler = AsyncMock()

    async def should_handle(self, args):
        return args.event["subtype"] != "bot_message"

    async def handle(self, args):
        await self.mock_handler(args)


class MockActionHandler(BaseActionHandler):
    def __init__(self, slack_client):
        super().__init__(slack_client)
        self.mock_handler = AsyncMock()

    async def handle(self, args):
        await self.mock_handler(args)

    @property
    def action_id(self):
        return "mock_action"
