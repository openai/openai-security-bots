# in tests/test_openai_utils.py
from unittest.mock import patch

import pytest
from incident_response_slackbot.openai_utils import get_user_awareness


@pytest.mark.asyncio
@patch("openai.ChatCompletion.create")
async def test_get_user_awareness(mock_create):
    # Arrange
    mock_create.return_value = {
        "choices": [
            {
                "message": {
                    "function_call": {"arguments": '{"has_answered": true, "is_aware": false}'}
                }
            }
        ]
    }
    inbound_direct_message = "mock_inbound_direct_message"

    # Act
    result = await get_user_awareness(inbound_direct_message)

    # Assert
    assert result == {"has_answered": True, "is_aware": False}
