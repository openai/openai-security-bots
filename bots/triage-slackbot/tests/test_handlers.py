import json
from unittest.mock import call, patch

import pytest
from triage_slackbot.handlers import (
    InboundRequestAcknowledgeHandler,
    InboundRequestHandler,
    InboundRequestRecategorizeHandler,
)
from triage_slackbot.openai_utils import openai


def get_mock_chat_completion_response(category: str):
    category_args = json.dumps({"category": category})
    return {
        "choices": [
            {
                "message": {
                    "function_call": {
                        "arguments": category_args,
                    }
                }
            }
        ]
    }


def assert_chat_completion_called(mock_chat_completion, mock_config):
    mock_chat_completion.create.assert_called_once_with(
        model="gpt-4-32k-0613",
        messages=[
            {
                "role": "system",
                "content": mock_config.openai_prompt,
            },
            {"role": "user", "content": "sample inbound request"},
        ],
        temperature=0,
        stream=False,
        functions=[
            {
                "name": "get_predicted_category",
                "description": "Predicts the category of an inbound request.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["appsec", "privacy", "physical_security"],
                            "description": "Predicted category of the inbound request",
                        }
                    },
                    "required": ["category"],
                },
            }
        ],
        function_call={"name": "get_predicted_category"},
    )


@patch.object(openai, "ChatCompletion")
async def test_inbound_request_handler_handle(
    mock_chat_completion,
    mock_config,
    mock_slack_client,
    mock_inbound_request,
):
    # Setup mocks
    mock_chat_completion.create.return_value = get_mock_chat_completion_response("appsec")

    # Call handler
    handler = InboundRequestHandler(mock_slack_client)
    await handler.maybe_handle(mock_inbound_request)

    # Assert that handler calls OpenAI API
    assert_chat_completion_called(mock_chat_completion, mock_config)

    mock_slack_client._client.assert_has_calls(
        [
            call.chat_getPermalink(channel="C12345", message_ts="t0"),
            call.chat_postMessage(
                channel="C23456",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Received an <mockpermalink|inbound message> in <#C12345>:",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": "Predicted category: Application Security",
                                "emoji": True,
                            },
                            {"type": "mrkdwn", "text": "Triaged to: <#C34567>"},
                            {
                                "type": "plain_text",
                                "text": "Triage updates in the :thread:",
                                "emoji": True,
                            },
                        ],
                    },
                ],
                text="New inbound request received",
            ),
            call.chat_postMessage(
                channel="C34567",
                thread_ts=None,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":wave: Hi, we received an <mockpermalink|inbound message> in <#C12345>, which was categorized as Application Security. Is this accurate?\n\n",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": ":thumbsup: Acknowledge this message and response directly to the inbound request.",
                                "emoji": True,
                            },
                            {
                                "type": "plain_text",
                                "text": ":thumbsdown: Recategorize this message, and if defined, I will route it to the appropriate on-call. If none applies, select Other and pick a channel that I will route the user to.",
                                "emoji": True,
                            },
                        ],
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "emoji": True,
                                    "text": "Acknowledge",
                                },
                                "style": "primary",
                                "value": "Application Security",
                                "action_id": "acknowledge_submit_action",
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "emoji": True,
                                    "text": "Inaccurate, recategorize",
                                },
                                "style": "danger",
                                "value": "recategorize",
                                "action_id": "recategorize_submit_action",
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "block_id": "recategorize_select_category_block",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Select a category from the dropdown list, or*",
                        },
                        "accessory": {
                            "type": "static_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select an item",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Privacy",
                                        "emoji": True,
                                    },
                                    "value": "privacy",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Physical Security",
                                        "emoji": True,
                                    },
                                    "value": "physical_security",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Other",
                                        "emoji": True,
                                    },
                                    "value": "other",
                                },
                            ],
                            "action_id": "recategorize_select_category_action",
                        },
                    },
                ],
                metadata={
                    "event_type": "notify_oncall",
                    "event_payload": {
                        "inbound_message_channel": "C12345",
                        "inbound_message_ts": "t0",
                        "feed_message_channel": "",
                        "feed_message_ts": "",
                        "inbound_message_url": "mockpermalink",
                        "predicted_category": "appsec",
                    },
                },
                text="Notify on-call for new inbound request",
            ),
        ]
    )


@patch.object(openai, "ChatCompletion")
async def test_inbound_request_handler_handle_autorespond(
    mock_chat_completion,
    mock_config,
    mock_slack_client,
    mock_inbound_request,
):
    # Setup mocks
    mock_chat_completion.create.return_value = get_mock_chat_completion_response(
        "physical_security"
    )

    # Call handler
    handler = InboundRequestHandler(mock_slack_client)
    await handler.maybe_handle(mock_inbound_request)

    # Assert that handler calls OpenAI API
    assert_chat_completion_called(mock_chat_completion, mock_config)

    mock_slack_client._client.assert_has_calls(
        [
            call.chat_getPermalink(channel="C12345", message_ts="t0"),
            call.chat_postMessage(
                channel="C23456",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Received an <mockpermalink|inbound message> in <#C12345>:",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": "Predicted category: Physical Security",
                                "emoji": True,
                            },
                            {
                                "type": "mrkdwn",
                                "text": "Triaged to: No on-call assigned",
                            },
                            {
                                "type": "plain_text",
                                "text": "Triage updates in the :thread:",
                                "emoji": True,
                            },
                        ],
                    },
                ],
                text="New inbound request received",
            ),
            call.chat_postMessage(
                channel="C12345",
                thread_ts="t0",
                text="Hi, thanks for reaching out! Looking for Physical or Office Security? You can reach out to physical-security@company.com.",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Hi, thanks for reaching out! Looking for Physical or Office Security? You can reach out to physical-security@company.com.",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": "If you feel strongly this is a Security issue, respond to this thread and someone from our team will get back to you.",
                                "emoji": True,
                            }
                        ],
                    },
                ],
            ),
            call.chat_getPermalink(channel="", message_ts=""),
            call.chat_postMessage(
                channel="",
                thread_ts="",
                text="<mockpermalink|Autoresponded> to inbound request.",
            ),
        ]
    )


async def test_inbound_request_acknowledge_handler(
    mock_slack_client,
    mock_notify_appsec_oncall_message,
):
    handler = InboundRequestAcknowledgeHandler(mock_slack_client)
    await handler.maybe_handle(mock_notify_appsec_oncall_message)
    mock_slack_client._client.assert_has_calls(
        [
            call.reactions_add(
                blocks=[],
                channel="C34567",
                ts="t2",
                text=":thumbsup: <@U1234567890> acknowledged the <https://myorg.slack.com/archives/C12345/p1234567890|inbound message> triaged to Application Security.",
            ),
            call.chat_postMessage(
                blocks=[],
                channel="C23456",
                thread_ts="t1",
                text=":thumbsup: <@U1234567890> acknowledged the inbound message triaged to Application Security.",
            ),
            call.conversations_history(channel="C23456", inclusive=True, latest="t1", limit=1),
            call.reactions_add(channel="C23456", name="thumbsup", timestamp="t1"),
        ]
    )


async def test_inbound_request_recategorize_to_listed_category_handler(
    mock_slack_client,
    mock_appsec_oncall_recategorize_to_privacy_message,
):
    handler = InboundRequestRecategorizeHandler(mock_slack_client)
    await handler.maybe_handle(mock_appsec_oncall_recategorize_to_privacy_message)
    mock_slack_client._client.assert_has_calls(
        [
            call.reactions_add(
                blocks=[],
                channel="C34567",
                ts="t3",
                text=":thumbsdown: <@U1234567890> reassigned the <https://myorg.slack.com/archives/C12345/p1234567890|inbound message> from Application Security to: Privacy.",
            ),
            call.reactions_add(channel="C23456", name="thumbsdown", timestamp="t1"),
            call.chat_postMessage(
                blocks=[],
                channel="C23456",
                thread_ts="t1",
                text=":thumbsdown: <@U1234567890> reassigned the inbound message from Application Security to: Privacy.",
            ),
            call.chat_postMessage(
                channel="C23456",
                thread_ts="t1",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":wave: Hi <@U12345>, is this assignment accurate?\n\n",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": ":thumbsup: Acknowledge this message and response directly to the inbound request.",
                                "emoji": True,
                            },
                            {
                                "type": "plain_text",
                                "text": ":thumbsdown: Recategorize this message, and if defined, I will route it to the appropriate on-call. If none applies, select Other and pick a channel that I will route the user to.",
                                "emoji": True,
                            },
                        ],
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "emoji": True,
                                    "text": "Acknowledge",
                                },
                                "style": "primary",
                                "value": "Privacy",
                                "action_id": "acknowledge_submit_action",
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "emoji": True,
                                    "text": "Inaccurate, recategorize",
                                },
                                "style": "danger",
                                "value": "recategorize",
                                "action_id": "recategorize_submit_action",
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "block_id": "recategorize_select_category_block",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Select a category from the dropdown list, or*",
                        },
                        "accessory": {
                            "type": "static_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select an item",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Physical Security",
                                        "emoji": True,
                                    },
                                    "value": "physical_security",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Other",
                                        "emoji": True,
                                    },
                                    "value": "other",
                                },
                            ],
                            "action_id": "recategorize_select_category_action",
                        },
                    },
                ],
                metadata={
                    "event_type": "notify_oncall",
                    "event_payload": {
                        "inbound_message_channel": "C12345",
                        "inbound_message_ts": "t0",
                        "feed_message_channel": "C23456",
                        "feed_message_ts": "t1",
                        "inbound_message_url": "https://myorg.slack.com/archives/C12345/p1234567890",
                        "predicted_category": "privacy",
                    },
                },
                text="Notify on-call for new inbound request",
            ),
        ]
    )


async def test_inbound_request_recategorize_to_other_category_handler(
    mock_slack_client,
    mock_appsec_oncall_recategorize_to_other_message,
):
    handler = InboundRequestRecategorizeHandler(mock_slack_client)
    await handler.maybe_handle(mock_appsec_oncall_recategorize_to_other_message)
    mock_slack_client._client.assert_has_calls(
        [
            call.reactions_add(
                blocks=[],
                channel="C34567",
                ts="t3",
                text=":thumbsdown: <@U1234567890> reassigned the <https://myorg.slack.com/archives/C12345/p1234567890|inbound message> from Application Security to: Other.",
            ),
            call.reactions_add(channel="C23456", name="thumbsdown", timestamp="t1"),
            call.chat_postMessage(
                blocks=[],
                channel="C23456",
                thread_ts="t1",
                text=":thumbsdown: <@U1234567890> reassigned the inbound message from Application Security to: Other.",
            ),
            call.chat_postMessage(
                channel="C12345",
                thread_ts="t0",
                text="Hi, thanks for reaching out! Our team looked at your request, and this is actually something that we don't own. We recommend reaching out to <#C11111> instead.",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Hi, thanks for reaching out! Our team looked at your request, and this is actually something that we don't own. We recommend reaching out to <#C11111> instead.",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": "If you feel strongly this is a Security issue, respond to this thread and someone from our team will get back to you.",
                                "emoji": True,
                            }
                        ],
                    },
                ],
            ),
            call.chat_getPermalink(channel="", message_ts=""),
            call.chat_postMessage(
                channel="C23456",
                thread_ts="t1",
                text="<mockpermalink|Autoresponded> to inbound request.",
            ),
        ]
    )


@pytest.mark.parametrize(
    "event_args_override",
    [
        # Channel is not inbound request channel
        {"channel": "c0"},
        # No text
        {"text": ""},
        # Bot message
        {"subtype": "bot_message"},
        # Thread response, not broadcasted
        {"thread_ts": "t0"},
    ],
)
@patch.object(openai, "ChatCompletion")
async def test_inbound_request_handler_skip_handle(
    mock_chat_completion, event_args_override, mock_slack_client, mock_inbound_request
):
    mock_inbound_request.event = {**mock_inbound_request.event, **event_args_override}
    handler = InboundRequestHandler(mock_slack_client)

    await handler.maybe_handle(mock_inbound_request)
    mock_chat_completion.create.assert_not_called()
