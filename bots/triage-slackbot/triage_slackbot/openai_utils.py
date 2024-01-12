import json
from functools import cache

import openai
from triage_slackbot.category import OTHER_KEY, RequestCategory
from triage_slackbot.config import get_config


@cache
def predict_category_functions(categories: list[RequestCategory]) -> list[dict]:
    return [
        {
            "name": "get_predicted_category",
            "description": "Predicts the category of an inbound request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            category.key for category in categories if category.key != OTHER_KEY
                        ],
                        "description": "Predicted category of the inbound request",
                    },
                },
                "required": ["category"],
            },
        }
    ]


async def get_predicted_category(inbound_request_content: str) -> str:
    """
    This function uses the OpenAI Chat Completion API to predict the category of an inbound request.
    """
    config = get_config()

    # Define the prompt
    messages = [
        {"role": "system", "content": config.openai_prompt},
        {"role": "user", "content": inbound_request_content},
    ]

    # Call the API
    response = openai.chat.completions.create(
        model="gpt-4-32k",
        messages=messages,
        temperature=0,
        stream=False,
        functions=predict_category_functions(config.categories.values()),
        function_call={"name": "get_predicted_category"},
    )

    function_args = json.loads(response.choices[0].message.function_call.arguments)  # type: ignore
    return function_args["category"]
