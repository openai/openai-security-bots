import json
import os
from logging import getLogger

# import anthropic
import openai

logger = getLogger(__name__)


def get_form_input(values, *fields):
    ret = {}
    for f in fields:
        container = values[f][f + "_input"]
        value = container.get("value")
        if value:
            ret[f] = container["value"]
        else:
            for key, item in container.items():
                if key.startswith("selected_") and item:
                    ret[f] = item
                    break
    return ret


def plain_text(text):
    return dict(type="plain_text", text=text)


def field(type, placeholder, **kwargs):
    return dict(type=type, placeholder=plain_text(placeholder), **kwargs)


def input_block(block_id, label, element):
    if "action_id" not in element:
        element["action_id"] = block_id + "_input"

    return dict(
        type="input",
        block_id=block_id,
        label=plain_text(label),
        element=element,
    )


def submit_block(action_id):
    return dict(
        type="actions",
        elements=[
            dict(
                type="button",
                text=plain_text("Submit"),
                action_id=action_id,
                style="primary",
            )
        ],
    )


def ask_ai(prompt, context):
    # return ask_claude(prompt, context) # YOU CAN USE CLAUDE HERE
    response = ask_gpt(prompt, context)

    # Removing leading and trailing backticks and whitespace
    clean_response = response.strip("`\n ")

    # Check if 'json' is at the beginning and remove it
    if clean_response.lower().startswith("json"):
        clean_response = clean_response[4:].strip()

    # Remove a trailing } if it exists
    if clean_response.endswith("}}"):
        clean_response = clean_response[:-1]  # Remove the last character

    logger.info(clean_response)

    try:
        parsed_response = json.loads(clean_response)
        return parsed_response
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from ask_gpt: {response}\nError: {e}")
        return None


def ask_gpt(prompt, context):
    response = openai.chat.completions.create(
        model="gpt-4-32k",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": context},
        ],
    )
    return response.choices[0].message.content


def ask_claude(prompt, context):
    client = anthropic.Anthropic(api_key=os.environ["CLAUDE_API_KEY"])
    message = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content
