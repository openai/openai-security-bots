from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.parametrize("subtype, should_handle", [("message", True), ("bot_message", False)])
async def test_message_handler(mock_message_handler, subtype, should_handle):
    args = MagicMock(
        ack=AsyncMock(),
        event={"type": "message", "subtype": subtype, "channel": "channel", "ts": "ts"},
    )

    await mock_message_handler.maybe_handle(args)
    args.ack.assert_awaited_once()
    if should_handle:
        mock_message_handler.mock_handler.assert_awaited_once_with(args)
    else:
        mock_message_handler.mock_handler.assert_not_awaited()

    assert mock_message_handler.logging_extra(args) == {
        "type": "message",
        "subtype": subtype,
        "channel": "channel",
        "ts": "ts",
    }


async def test_action_handler(mock_action_handler):
    args = MagicMock(
        ack=AsyncMock(),
        body={
            "type": "type",
            "actions": ["action"],
        },
    )

    await mock_action_handler.maybe_handle(args)
    args.ack.assert_awaited_once()
    mock_action_handler.mock_handler.assert_awaited_once_with(args)

    assert mock_action_handler.logging_extra(args) == {
        "action_type": "type",
        "action": "action",
    }
