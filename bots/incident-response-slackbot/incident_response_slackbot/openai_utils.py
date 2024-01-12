import json

import openai
from incident_response_slackbot.config import load_config, get_config

load_config()
config = get_config()

# Convert slack threaded messages to string
def messages_to_string(messages):
    text_messages = " ".join([message["text"] for message in messages if "text" in message])
    return text_messages


async def get_clean_output(completion: str) -> str:
    return completion.choices[0].message.content


async def create_greeting(username, details):
    if not openai.api_key:
        raise Exception("OpenAI API key not found.")

    prompt = f"""
    You are a helpful cybersecurity AI analyst assistant to the security team that wants to keep
    your company secure. You just received an alert with the following details:
    {details}
    Without being accusatory, gently ask the user, whose name is {username} in a casual tone if they were aware
    about the topic of the alert.
    Keep the message brief, not more than 3 or 4 sentences.
    Do not end with a signature. End with a question.
    """

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": ""},
    ]

    completion = openai.chat.completions.create(
        model="gpt-4-32k",
        messages=messages,
        temperature=0.3,
        stream=False,
    )
    response = await get_clean_output(completion)
    return response


aware_decision_function = [
    {
        "name": "is_user_aware",
        "description": "Determines if the user has answered whether they were aware, and what that response is.",
        "parameters": {
            "type": "object",
            "properties": {
                "has_answered": {
                    "type": "boolean",
                    "description": "Determine whether user answered the quesiton of whether they were aware.",
                },
                "is_aware": {
                    "type": "boolean",
                    "description": "Determine whether user was aware of the alert details.",
                },
            },
            "required": ["has_answered", "is_aware"],
        },
    }
]


async def get_user_awareness(inbound_direct_message: str) -> str:
    """
    This function uses the OpenAI Chat Completion API to determine whether user was aware.
    """
    # Define the prompt
    prompt = f"""
    You are a helpful cybersecurity AI analyst assistant to the security team that wants to keep
    your company secure. You just received an alert and are having a chat with the user whether
    they were aware about the details of an alert. Based on the chat so far, determine whether
    the user has answered the question of whether they were aware of the alert details, and whether
    they were aware or not.
    """

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": inbound_direct_message},
    ]

    # Call the API
    response = openai.chat.completions.create(
        model="gpt-4-32k",
        messages=messages,
        temperature=0,
        stream=False,
        functions=aware_decision_function,
        function_call={"name": "is_user_aware"},
    )

    function_args = json.loads(response.choices[0].message.function_call.arguments)  # type: ignore
    return function_args


async def get_thread_summary(messages):
    if not openai.api_key:
        raise Exception("OpenAI API key not found.")

    text_messages = messages_to_string(messages)

    prompt = f"""
    You are a helpful cybersecurity AI analyst assistant to the security team that wants to keep
    your company secure. The following is a conversation that you had with the user.
    Please summarize the following conversation, and note whether the user was aware or not aware
    of the alert, and whether they acted suspiciously when answering:
    {text_messages}
    """

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": ""},
    ]

    completion = openai.chat.completions.create(
        model="gpt-4-32k",
        messages=messages,
        temperature=0.3,
        stream=False,
    )
    response = await get_clean_output(completion)
    return response


async def generate_awareness_question():
    if not openai.api_key:
        raise Exception("OpenAI API key not found.")

    prompt = f"""
    You are a helpful cybersecurity AI analyst assistant to the security team that wants to keep
    your company secure. You have received an alert regarding the user you're chatting with, and
    you have asked whether the user was aware of the alert. The user has not answered the question,
    so now you are asking the user again whether they were aware of the alert. You ask in a gentle,
    kind, and casual tone. You keep it short, to two sentences at most. You end with a question.
    """

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": ""},
    ]

    completion = openai.chat.completions.create(
        model="gpt-4-32k",
        messages=messages,
        temperature=0.5,
        stream=False,
    )
    response = await get_clean_output(completion)
    return response
