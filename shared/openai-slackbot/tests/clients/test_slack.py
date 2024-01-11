from unittest.mock import AsyncMock, MagicMock

import pytest
from openai_slackbot.clients.slack import CreateSlackMessageResponse
from slack_sdk.errors import SlackApiError


async def test_get_message_link_success(mock_slack_client):
    mock_slack_client._client.chat_getPermalink = AsyncMock(
        return_value={
            "ok": True,
            "channel": "C123456",
            "permalink": "https://myorg.slack.com/archives/C123456/p1234567890",
        }
    )
    link = await mock_slack_client.get_message_link(channel="channel", message_ts="message_ts")
    mock_slack_client._client.chat_getPermalink.assert_called_once_with(
        channel="channel", message_ts="message_ts"
    )
    assert link == "https://myorg.slack.com/archives/C123456/p1234567890"


async def test_get_message_link_failed(mock_slack_client):
    mock_slack_client._client.chat_getPermalink = AsyncMock(
        return_value={"ok": False, "error": "failed"}
    )
    with pytest.raises(Exception):
        await mock_slack_client.get_message_link(channel="channel", message_ts="message_ts")
        mock_slack_client._client.chat_getPermalink.assert_called_once_with(
            channel="channel", message_ts="message_ts"
        )


async def test_post_message_success(mock_slack_client):
    mock_message_data = {
        "ok": True,
        "channel": "C234567",
        "ts": "ts",
        "message": {
            "bot_id": "bot_id",
            "bot_profile": {"id": "bot_profile_id"},
            "team": "team",
            "text": "text",
            "ts": "ts",
            "type": "type",
            "user": "user",
        },
    }
    mock_response = MagicMock(data=mock_message_data)
    mock_response.__getitem__.side_effect = mock_message_data.__getitem__
    mock_slack_client._client.chat_postMessage = AsyncMock(return_value=mock_response)

    response = await mock_slack_client.post_message(channel="C234567", text="text")
    assert response == CreateSlackMessageResponse(**mock_message_data)


async def test_post_message_failed(mock_slack_client):
    mock_slack_client._client.chat_postMessage = AsyncMock(
        return_value={"ok": False, "error": "failed"}
    )
    with pytest.raises(Exception):
        await mock_slack_client.post_message(channel="channel", text="text")
        mock_slack_client._client.chat_postMessage.assert_called_once_with(
            channel="channel", text="text"
        )


async def test_update_message_success(mock_slack_client):
    mock_message_data = {
        "ok": True,
        "channel": "C234567",
        "ts": "ts",
        "message": {
            "bot_id": "bot_id",
            "bot_profile": {"id": "bot_profile_id"},
            "team": "team",
            "text": "text",
            "ts": "ts",
            "type": "type",
            "user": "user",
        },
    }
    mock_response = MagicMock(data=mock_message_data)
    mock_response.__getitem__.side_effect = mock_message_data.__getitem__
    mock_slack_client._client.chat_update = AsyncMock(return_value=mock_response)

    response = await mock_slack_client.update_message(channel="C234567", ts="ts", text="text")
    assert response == mock_message_data


async def test_update_message_failed(mock_slack_client):
    mock_slack_client._client.chat_update = AsyncMock(return_value={"ok": False, "error": "failed"})
    with pytest.raises(Exception):
        await mock_slack_client.update_message(channel="channel", ts="ts", text="text")
        mock_slack_client._client.chat_update.assert_called_once_with(
            channel="channel", ts="ts", text="text"
        )


async def test_add_reaction_success(mock_slack_client):
    mock_response_data = {"ok": True}
    mock_response = MagicMock(data=mock_response_data)
    mock_response.__getitem__.side_effect = mock_response_data.__getitem__
    mock_slack_client._client.reactions_add = AsyncMock(return_value=mock_response)
    await mock_slack_client.add_reaction(channel="channel", name="thumbsup", timestamp="timestamp")


async def test_add_reaction_already_reacted(mock_slack_client):
    mock_slack_client._client.reactions_add = AsyncMock(
        side_effect=SlackApiError("already_reacted", {"error": "already_reacted"})
    )
    response = await mock_slack_client.add_reaction(
        channel="channel", name="thumbsup", timestamp="timestamp"
    )
    assert response == {}


async def test_add_reaction_failed(mock_slack_client):
    mock_slack_client._client.reactions_add = AsyncMock(
        side_effect=SlackApiError("failed", {"error": "invalid_reaction"})
    )
    with pytest.raises(Exception):
        await mock_slack_client.add_reaction(
            channel="channel", name="thumbsup", timestamp="timestamp"
        )
