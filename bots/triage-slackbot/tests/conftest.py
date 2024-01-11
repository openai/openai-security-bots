import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai_slackbot.clients.slack import SlackClient
from triage_slackbot.category import RequestCategory
from triage_slackbot.config import load_config
from triage_slackbot.handlers import MessageTemplatePath

##########################
##### HELPER METHODS #####
##########################


def bot_message_extra_data():
    return {
        "bot_id": "bot_id",
        "bot_profile": {"id": "bot_profile_id"},
        "team": "team",
        "type": "type",
        "user": "user",
    }


def recategorize_message_data(
    *,
    ts,
    channel_id,
    user,
    message,
    category,
    conversation=None,
):
    return MagicMock(
        ack=AsyncMock(),
        body={
            "actions": ["recategorize_submit_action"],
            "container": {
                "message_ts": ts,
                "channel_id": channel_id,
            },
            "user": user,
            "message": message,
            "state": {
                "values": {
                    "recategorize_select_category_block": {
                        "recategorize_select_category_action": {
                            "selected_option": {
                                "value": category,
                            }
                        }
                    },
                    "recategorize_select_conversation_block": {
                        "recategorize_select_conversation_action": {
                            "selected_conversation": conversation,
                        }
                    },
                }
            },
        },
    )


####################
##### FIXTURES #####
####################


@pytest.fixture(autouse=True)
def mock_config():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "test_config.toml")
    return load_config(config_path)


@pytest.fixture()
def mock_post_message_response():
    return AsyncMock(
        return_value=MagicMock(
            ok=True,
            data={
                "ok": True,
                "channel": "",
                "ts": "",
                "message": {
                    "blocks": [],
                    "text": "",
                    "ts": "",
                    **bot_message_extra_data(),
                },
            },
        )
    )


@pytest.fixture()
def mock_generic_slack_response():
    return AsyncMock(return_value=MagicMock(ok=True, data={"ok": True}))


@pytest.fixture()
def mock_conversations_history_response():
    return AsyncMock(
        return_value=MagicMock(
            ok=True,
            data={
                "ok": True,
                "messages": [
                    {
                        "blocks": [],
                        "text": "",
                        "ts": "",
                        **bot_message_extra_data(),
                    }
                ],
            },
        )
    )


@pytest.fixture()
def mock_get_permalink_response():
    return AsyncMock(
        return_value={
            "ok": True,
            "permalink": "mockpermalink",
        },
    )


@pytest.fixture
def mock_slack_asyncwebclient(
    mock_conversations_history_response,
    mock_generic_slack_response,
    mock_post_message_response,
    mock_get_permalink_response,
):
    with patch("slack_sdk.web.async_client.AsyncWebClient", autospec=True) as mock_client:
        wc = mock_client.return_value
        wc.reactions_add = mock_generic_slack_response
        wc.chat_update = mock_generic_slack_response
        wc.conversations_history = mock_conversations_history_response
        wc.chat_postMessage = mock_post_message_response
        wc.chat_getPermalink = mock_get_permalink_response
        yield wc


@pytest.fixture
def mock_slack_client(mock_slack_asyncwebclient):
    template_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../triage_slackbot/templates"
    )
    return SlackClient(mock_slack_asyncwebclient, template_path)


@pytest.fixture
def mock_inbound_request_channel_id(mock_config):
    return mock_config.inbound_request_channel_id


@pytest.fixture
def mock_feed_channel_id(mock_config):
    return mock_config.feed_channel_id


@pytest.fixture
def mock_appsec_oncall_slack_channel_id(mock_config):
    return mock_config.categories["appsec"].oncall_slack_id


@pytest.fixture
def mock_privacy_oncall_slack_user_id(mock_config):
    return mock_config.categories["privacy"].oncall_slack_id


@pytest.fixture
def mock_appsec_oncall_slack_user():
    return {"id": "U1234567890"}


@pytest.fixture
def mock_appsec_oncall_slack_user_id(mock_appsec_oncall_slack_user):
    return mock_appsec_oncall_slack_user["id"]


@pytest.fixture
def mock_inbound_request_ts():
    return "t0"


@pytest.fixture
def mock_feed_message_ts():
    return "t1"


@pytest.fixture
def mock_notify_appsec_oncall_message_ts():
    return "t2"


@pytest.fixture
def mock_appsec_oncall_recategorize_ts():
    return "t3"


@pytest.fixture
def mock_inbound_request(mock_inbound_request_channel_id, mock_inbound_request_ts):
    return MagicMock(
        ack=AsyncMock(),
        event={
            "channel": mock_inbound_request_channel_id,
            "text": "sample inbound request",
            "thread_ts": None,
            "ts": mock_inbound_request_ts,
        },
    )


@pytest.fixture
def mock_inbound_request_permalink(mock_inbound_request_channel_id):
    return f"https://myorg.slack.com/archives/{mock_inbound_request_channel_id}/p1234567890"


@pytest.fixture
async def mock_notify_appsec_oncall_message_data(
    mock_slack_client,
    mock_config,
    mock_inbound_request_channel_id,
    mock_inbound_request_permalink,
    mock_inbound_request_ts,
    mock_feed_channel_id,
    mock_feed_message_ts,
    mock_appsec_oncall_slack_channel_id,
    mock_notify_appsec_oncall_message_ts,
):
    appsec_key = "appsec"
    remaining_categories = [c for c in mock_config.categories.values() if c.key != appsec_key]
    blocks = mock_slack_client.render_blocks_from_template(
        MessageTemplatePath.notify_oncall_channel.value,
        {
            "inbound_message_url": mock_inbound_request_permalink,
            "inbound_message_channel": mock_inbound_request_channel_id,
            "predicted_category": mock_config.categories[appsec_key].display_name,
            "options": RequestCategory.to_block_options(remaining_categories),
        },
    )

    return {
        "ok": True,
        "channel": mock_appsec_oncall_slack_channel_id,
        "ts": mock_notify_appsec_oncall_message_ts,
        "message": {
            "blocks": blocks,
            "text": "Notify on-call for new inbound request",
            "metadata": {
                "event_type": "notify_oncall",
                "event_payload": {
                    "inbound_message_channel": mock_inbound_request_channel_id,
                    "inbound_message_ts": mock_inbound_request_ts,
                    "feed_message_channel": mock_feed_channel_id,
                    "feed_message_ts": mock_feed_message_ts,
                    "inbound_message_url": mock_inbound_request_permalink,
                    "predicted_category": appsec_key,
                },
            },
            "ts": mock_notify_appsec_oncall_message_ts,
            **bot_message_extra_data(),
        },
    }


@pytest.fixture
def mock_notify_appsec_oncall_message(
    mock_notify_appsec_oncall_message_data,
    mock_appsec_oncall_slack_channel_id,
    mock_appsec_oncall_slack_user,
):
    return MagicMock(
        ack=AsyncMock(),
        body={
            "actions": ["acknowledge_submit_action"],
            "container": {
                "message_ts": mock_notify_appsec_oncall_message_data["ts"],
                "channel_id": mock_appsec_oncall_slack_channel_id,
            },
            "user": mock_appsec_oncall_slack_user,
            "message": mock_notify_appsec_oncall_message_data["message"],
        },
    )


@pytest.fixture
def mock_appsec_oncall_recategorize_to_privacy_message(
    mock_appsec_oncall_recategorize_ts,
    mock_appsec_oncall_slack_channel_id,
    mock_appsec_oncall_slack_user,
    mock_notify_appsec_oncall_message_data,
):
    return recategorize_message_data(
        ts=mock_appsec_oncall_recategorize_ts,
        channel_id=mock_appsec_oncall_slack_channel_id,
        user=mock_appsec_oncall_slack_user,
        message=mock_notify_appsec_oncall_message_data["message"],
        category="privacy",
    )


@pytest.fixture
def mock_appsec_oncall_recategorize_to_other_message(
    mock_appsec_oncall_recategorize_ts,
    mock_appsec_oncall_slack_channel_id,
    mock_appsec_oncall_slack_user,
    mock_notify_appsec_oncall_message_data,
):
    return recategorize_message_data(
        ts=mock_appsec_oncall_recategorize_ts,
        channel_id=mock_appsec_oncall_slack_channel_id,
        user=mock_appsec_oncall_slack_user,
        message=mock_notify_appsec_oncall_message_data["message"],
        category="other",
        conversation="C11111",
    )
