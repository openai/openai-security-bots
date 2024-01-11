# in tests/test_handlers.py
from unittest.mock import AsyncMock, MagicMock, patch
from collections import namedtuple

import pytest
from incident_response_slackbot.handlers import (
    InboundDirectMessageHandler,
    InboundIncidentStartChatHandler,
    InboundIncidentDoNothingHandler,
    InboundIncidentEndChatHandler,
)


@pytest.mark.asyncio
async def test_send_message_to_channel(mock_slack_client, mock_config):
    # Arrange
    handler = InboundDirectMessageHandler(slack_client=mock_slack_client)
    mock_event = {"text": "mock_event_text", "user_profile": {"name": "mock_user_name"}}
    mock_message_ts = "mock_message_ts"

    # Act
    await handler.send_message_to_channel(mock_event, mock_message_ts)

    # Assert
    mock_slack_client.post_message.assert_called_once_with(
        channel=mock_config.feed_channel_id,
        text="Received message from <@mock_user_name>:\n> mock_event_text",
        thread_ts=mock_message_ts,
    )


@pytest.mark.asyncio
async def test_end_chat(mock_slack_client, mock_config):
    # Define the return value for get_original_blocks
    mock_slack_client.get_original_blocks.return_value = [
        {"type": "section", "block_id": "block1"},
        {"type": "actions", "block_id": "block2"},
        {"type": "section", "block_id": "block3"},
    ]

    # Create an instance of the handler
    handler = InboundDirectMessageHandler(slack_client=mock_slack_client)

    # Call the end_chat method
    await handler.end_chat("12345")

    # Assert that update_message was called with the correct arguments
    mock_slack_client.update_message.assert_called_once()

    # Get the actual call arguments
    args, kwargs = mock_slack_client.update_message.call_args

    # Check the blocks argument
    assert kwargs["blocks"] == [
        {"type": "section", "block_id": "block1"},
        {"type": "section", "block_id": "block3"},
        {
            "type": "section",
            "block_id": "end_chat_automatically",
            "text": {
                "type": "mrkdwn",
                "text": "The chat was automatically ended from SecurityBot review. :done_:",
                "verbatim": True,
            },
        },
    ]


@pytest.mark.asyncio
async def test_nudge_user(mock_slack_client, mock_config, mock_generate_awareness_question):
    # Create an instance of the handler
    handler = InboundDirectMessageHandler(slack_client=mock_slack_client)

    # Call the nudge_user method
    await handler.nudge_user("user123", "12345")

    # Assert that post_message was called twice with the correct arguments
    assert mock_slack_client.post_message.call_count == 2
    mock_slack_client.post_message.assert_any_call(channel="user123", text="Mock question")
    mock_slack_client.post_message.assert_any_call(
        channel=handler.config.feed_channel_id,
        text="Sent message to <@user123>:\n> Mock question",
        thread_ts="12345",
    )


@pytest.mark.asyncio
async def test_incident_start_chat_handle(mock_slack_client, mock_config):
    # Create an instance of the handler
    handler = InboundIncidentStartChatHandler(slack_client=mock_slack_client)

    # Create a mock args object
    args = MagicMock()
    args.body = {
        "container": {"message_ts": "12345"},
        "user": {"name": "test_user", "id": "user123"},
    }

    # Mock the DATABASE.get_user_id method
    with patch(
        "incident_response_slackbot.handlers.DATABASE.get_user_id", return_value="alert_user123"
    ) as mock_get_user_id, patch(
        "incident_response_slackbot.handlers.create_greeting",
        new_callable=AsyncMock,
        return_value="greeting message",
    ) as mock_create_greeting, patch.object(
        handler._slack_client, "get_thread_messages", new_callable=AsyncMock
    ), patch.object(
        handler._slack_client, "update_message", new_callable=AsyncMock
    ), patch.object(
        handler._slack_client,
        "get_user_display_name",
        new_callable=AsyncMock,
        return_value="username",
    ), patch.object(
        handler._slack_client, "post_message", new_callable=AsyncMock
    ):
        # Call the handle method
        await handler.handle(args)

        # Assert that the slack client methods were called with the correct arguments
        handler._slack_client.get_thread_messages.assert_called_once_with(
            channel=mock_config.feed_channel_id, thread_ts="12345"
        )
        handler._slack_client.update_message.assert_called_once()
        handler._slack_client.get_user_display_name.assert_called_once_with("alert_user123")

        # Assert that post_message was called twice
        assert handler._slack_client.post_message.call_count == 2

        # Assert that post_message was called with the correct arguments
        handler._slack_client.post_message.assert_any_call(
            channel="alert_user123", text="greeting message"
        )


@pytest.mark.asyncio
async def test_do_nothing_handle(mock_slack_client, mock_config):
    # Create an instance of the handler
    handler = InboundIncidentDoNothingHandler(slack_client=mock_slack_client)

    # Create a mock args object
    args = MagicMock()
    args.body = {
        "user": {"id": "user123"},
        "message": {"ts": "12345", "blocks": [{"type": "actions"}, {"type": "section"}]},
    }

    # Call the handle method
    await handler.handle(args)

    # Assert that the slack client update_message method was called with the correct arguments
    mock_slack_client.update_message.assert_called_once_with(
        channel=mock_config.feed_channel_id,
        blocks=[
            {"type": "section"},
            {
                "type": "section",
                "block_id": "do_nothing",
                "text": {
                    "type": "mrkdwn",
                    "text": "<@user123> decided that no action was necessary :done_:",
                    "verbatim": True,
                },
            },
        ],
        ts="12345",
        text="Do Nothing action selected",
    )


@pytest.mark.asyncio
async def test_end_chat_handle(mock_slack_client, mock_config, mock_get_thread_summary):
    # Mock the Slack client and the database
    with patch(
        "incident_response_slackbot.handlers.Database", new_callable=AsyncMock
    ) as MockDatabase:
        # Instantiate the handler
        handler = InboundIncidentEndChatHandler(slack_client=mock_slack_client)

        # Define a namedtuple for args
        Args = namedtuple("Args", ["body"])

        # Instantiate the args object
        args = Args(body={"user": {"id": "user_id"}, "message": {"ts": "message_ts"}})

        # Mock the get_user_id method of the database to return a user id
        MockDatabase.get_user_id.return_value = "alert_user_id"

        # Call the handle method
        await handler.handle(args)

        # Assert that the correct methods were called with the expected arguments
        mock_slack_client.get_original_blocks.assert_called_once_with(
            "message_ts", mock_config.feed_channel_id
        )
        mock_slack_client.update_message.assert_called()
        mock_slack_client.post_message.assert_called()
