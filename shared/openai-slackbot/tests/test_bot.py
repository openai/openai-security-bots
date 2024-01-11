import pytest


async def test_start_bot(
    mock_slack_app, mock_socket_mode_handler, mock_message_handler, mock_action_handler
):
    from openai_slackbot.bot import start_bot

    await start_bot(
        openai_organization_id="org-id",
        slack_message_handler=mock_message_handler.__class__,
        slack_action_handlers=[mock_action_handler.__class__],
        slack_template_path="/path/to/templates",
    )

    mock_slack_app.event.assert_called_once_with("message")
    mock_slack_app.action.assert_called_once_with("mock_action")
    mock_socket_mode_handler.start_async.assert_called_once()
