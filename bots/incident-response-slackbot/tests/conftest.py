import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import toml
from incident_response_slackbot.config import load_config
from pydantic import ValidationError

####################
##### FIXTURES #####
####################


@pytest.fixture(autouse=True)
def mock_config():
    # Load the test config
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "test_config.toml")
    try:
        config = load_config(config_path)
    except ValidationError as e:
        print(f"Error validating the config: {e}")
        raise
    return config


@pytest.fixture()
def mock_slack_client():
    # Mock the Slack client
    slack_client = MagicMock()
    slack_client.post_message = AsyncMock()
    slack_client.update_message = AsyncMock()
    slack_client.get_original_blocks = AsyncMock()
    slack_client.get_thread_messages = AsyncMock()

    return slack_client


@pytest.fixture(autouse=True)
@patch("openai.ChatCompletion.create")
def mock_chat_completion(mock_create):
    mock_create.return_value = {
        "id": "chatcmpl-1234567890",
        "object": "chat.completion",
        "created": 1640995200,
        "model": "gpt-4-32k",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "This is a mock response from the OpenAI API.",
                },
                "finish_reason": "stop",
                "index": 0,
            }
        ],
    }
    yield


@pytest.fixture
def mock_generate_awareness_question():
    with patch(
        "incident_response_slackbot.handlers.generate_awareness_question",
        new_callable=AsyncMock,
    ) as mock_generate_question:
        mock_generate_question.return_value = "Mock question"
        yield mock_generate_question


@pytest.fixture
def mock_get_thread_summary():
    with patch(
        "incident_response_slackbot.handlers.get_thread_summary",
        new_callable=AsyncMock,
    ) as mock_get_summary:
        mock_get_summary.return_value = "Mock summary"
        yield mock_get_summary
