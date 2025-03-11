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
        "description": "Determines if the user has answered whether they were aware, what that response is, and if they need more context.",
        "parameters": {
            "type": "object",
            "properties": {
                "has_answered": {
                    "type": "boolean",
                    "description": "Determine whether user answered the question of whether they were aware.",
                },
                "is_aware": {
                    "type": "boolean",
                    "description": "Determine whether user was aware of the alert details.",
                },
                "needs_context": {
                    "type": "boolean",
                    "description": "Determine whether user is asking for more context or clarification about the alert.",
                }
            },
            "required": ["has_answered", "is_aware", "needs_context"],
        },
    }
]


async def get_user_awareness(inbound_direct_message: str) -> dict:
    """
    This function uses the OpenAI Chat Completion API to determine whether user was aware
    and if they need more context.
    Returns a dictionary with keys: has_answered (bool), is_aware (bool), needs_context (bool)
    """
    # Define the prompt
    prompt = f"""
    You are a helpful cybersecurity AI analyst assistant. Your task is to analyze the following user message:
    "{inbound_direct_message}"

    Determine:
    1. If the user is asking for more information or context about the alert
    2. If the user has answered whether they were aware of the alert
    3. If they have answered, whether they were aware or not

    VERY IMPORTANT: If the message contains ANY of these patterns, you MUST set needs_context to true:
    - Questions (e.g., "what?", "which alert?", "what do you mean?")
    - Requests for information (e.g., "can you tell me more", "I need more info", "provide more details")
    - Expressions of confusion (e.g., "I don't understand", "I'm not sure what you mean")
    - Any response that isn't clearly about awareness
    - Any message that seems unclear or ambiguous
    - Requests for help or clarification
    
    You must be very liberal in setting needs_context to true. If there's any doubt, set it to true.
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

    function_args = json.loads(response.choices[0].message.function_call.arguments)
    
    # Force needs_context to true for common patterns
    if any(pattern in inbound_direct_message.lower() for pattern in [
        "what", "tell me more", "more info", "help", "context", "details",
        "don't understand", "not sure", "?"
    ]):
        function_args["needs_context"] = True
    
    # Ensure all required keys exist with default values
    return {
        "has_answered": function_args.get("has_answered", False),
        "is_aware": function_args.get("is_aware", False),
        "needs_context": function_args.get("needs_context", True)  # Default to True if not present
    }


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
