import asyncio
import hashlib
import json
import os
import re
import threading
import time
from logging import getLogger

import validate
import validators
from database import *
from gdoc import gdoc_get
from openai_slackbot.bot import init_bot, start_app
from openai_slackbot.utils.envvars import string
from peewee import *
from playhouse.db_url import *
from playhouse.shortcuts import model_to_dict
from sdlc_slackbot.config import get_config, load_config
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from utils import *

logger = getLogger(__name__)


async def send_update_notification(input, gpt_response):
    msg = f"""
    Project {input['project_name']} has been updated and has a new decision:

    This project {gpt_response['decision']}. {gpt_response['justification']}
    """

    await app.client.chat_postMessage(channel=config.notification_channel_id, text=msg)


def hash_content(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


url_pat = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+\b(?!>)"
)


def extract_urls(text):
    logger.info(f"extracting urls from {text}")
    urls = re.findall(url_pat, text)
    return [url for url in urls if validators.url(url)]


async def async_fetch_slack(url):
    parts = url.split("/")
    channel = parts[-2]
    ts = parts[-1]
    ts = ts[1:]  # trim p
    seconds = ts[:-6]
    nanoseconds = ts[-6:]
    result = await app.client.conversations_replies(channel=channel, ts=f"{seconds}.{nanoseconds}")
    return " ".join(message.get("text", "") for message in result.data.get("messages", []))


content_fetchers = [
    (
        lambda u: u.startswith(("https://docs.google.com/document", "docs.google.com/document")),
        gdoc_get,
    ),
    (lambda u: "slack.com/archives" in u, async_fetch_slack),
]


async def fetch_content(url):
    for condition, fetcher in content_fetchers:
        if condition(url):
            if asyncio.iscoroutinefunction(fetcher):
                return await fetcher(url)  # Await the result if it's a coroutine function
            else:
                return fetcher(url)  # Call it directly if it's not a coroutine function


form = [
    input_block(
        "project_name",
        "Project Name",
        field("plain_text_input", "Enter the project name"),
    ),
    input_block(
        "project_description",
        "Project Description",
        field("plain_text_input", "Enter the project description", multiline=True),
    ),
    input_block(
        "links_to_resources",
        "Links to Resources",
        field("plain_text_input", "Enter links to resources", multiline=True),
    ),
    input_block("point_of_contact", "Point of Contact", field("users_select", "Select a user")),
    input_block(
        "estimated_go_live_date",
        "Estimated Go Live Date",
        field("datepicker", "Select a date"),
    ),
    submit_block("submit_form"),
]


def decision_msg(response):
    return f"Thanks for your response! Based on this input, we've decided that this project \
            {response['decision']}. {response['justification']}."


skip_params = set(
    [
        "id",
        "project_name",
        "links_to_resources",
        "point_of_contact",
        "estimated_go_live_date",
    ]
)

multiple_whitespace_pat = re.compile(r"\s+")


def model_params_to_str(params):
    ss = (v for k, v in params.items() if k not in skip_params)
    return re.sub(multiple_whitespace_pat, " ", "\n".join(map(str, ss))).strip()


def summarize_params(params):
    summary = {}
    for k, v in params.items():
        if k not in skip_params:
            summary[k] = ask_gpt(
                config.base_prompt + config.summary_prompt, v[: config.context_limit]
            )
        else:
            summary[k] = v

    return summary


async def handle_app_mention_events(say, event):
    logger.info("App mention event received:", event)
    await say(blocks=form, thread_ts=event["ts"])


async def handle_message_events(say, message):
    logger.info("message: ", message)
    if message["channel_type"] == "im":
        await say(blocks=form, thread_ts=message["ts"])


def get_response_with_retry(prompt, context, max_retries=1):
    prompt = prompt.strip().replace("\n", " ")
    retries = 0
    while retries <= max_retries:
        try:
            response = json.loads(ask_gpt(prompt, context))
            return response
        except json.JSONDecodeError as e:
            logger.error(f"JSON error on attempt {retries + 1}: {e}")
            retries += 1
            if retries > max_retries:
                return {}


async def submit_form(ack, body, say):
    await ack()

    try:
        ts = body["container"]["message_ts"]
        values = body["state"]["values"]
        params = get_form_input(
            values,
            "project_name",
            "project_description",
            "links_to_resources",
            "point_of_contact",
            "estimated_go_live_date",
        )

        validate.required(params, "project_name", "project_description", "point_of_contact")

        await say(text=config.reviewing_message, thread_ts=ts)

        try:
            assessment = Assessment.create(**params, user_id=body["user"]["id"])
        except IntegrityError as e:
            raise validate.ValidationError("project_name", "must be unique")

        resources = []
        for url in extract_urls(params.get("links_to_resources", "")):
            content = await fetch_content(url)
            if content:
                params[url] = content
                resources.append(
                    dict(
                        assessment=assessment,
                        url=url,
                        content_hash=hash_content(content),
                    )
                )
        Resource.insert_many(resources).execute()

        context = model_params_to_str(params)
        if len(context) > config.context_limit:
            logger.info(f"context too long: {len(context)}. Summarizing...")
            summarized_context = summarize_params(params)
            context = model_params_to_str(summarized_context)
            # FIXME: is there a better way to handle this? currently, if the summary is still too long
            # we just give up and cut it off
            if len(context) > config.context_limit:
                logger.info(f"Summarized context too long: {len(context)}. Cutting off...")
                context = context[: config.context_limit]

        response = get_response_with_retry(config.base_prompt + config.initial_prompt, context)
        if not response:
            return

        if response["outcome"] == "decision":
            assessment.update(**response).execute()
            say(text=decision_msg(response), thread_ts=ts)
        elif response["outcome"] == "followup":
            db_questions = [dict(assessment=assessment, question=q) for q in response["questions"]]
            Question.insert_many(db_questions).execute()

            form = []
            for i, q in enumerate(response["questions"]):
                form.append(
                    input_block(
                        f"question_{i}",
                        q,
                        field("plain_text_input", "...", multiline=True),
                    )
                )
            form.append(submit_block(f"submit_followup_questions_{assessment.id}"))

            await say(blocks=form, thread_ts=ts)
    except validate.ValidationError as e:
        await say(text=f"{e.field}: {e.issue}", thread_ts=ts)
    except Exception as e:
        import traceback

        traceback.print_exc()
        await say(text=config.irrecoverable_error_message, thread_ts=ts)


async def submit_followup_questions(ack, body, say):
    await ack()

    try:
        assessment_id = int(body["actions"][0]["action_id"].split("_")[-1])
        ts = body["container"]["message_ts"]
        assessment = Assessment.get(Assessment.id == assessment_id)
        params = model_to_dict(assessment)
        followup_questions = [q.question for q in assessment.questions]
    except Exception as e:
        logger.error(f"Failed to find params for user {body['user']['id']}", e)
        await say(text=config.recoverable_error_message, thread_ts=ts)
        return

    try:
        await say(text=config.reviewing_message, thread_ts=ts)

        values = body["state"]["values"]
        for i, q in enumerate(followup_questions):
            params[q] = values[f"question_{i}"][f"question_{i}_input"]["value"]

        for question in assessment.questions:
            question.answer = params[question.question]
            question.save()

        context = model_params_to_str(params)
        response = json.loads(ask_gpt(config.base_prompt, context))

        assessment.update(**response).execute()
        await say(text=decision_msg(response), thread_ts=ts)

    except Exception as e:
        logger.error(f"error: {e} processing followup questions: {json.dumps(body, indent=2)}")
        await say(text=config.irrecoverable_error_message, thread_ts=ts)


def update_resources():
    while True:
        time.sleep(monitor_thread_sleep_seconds)
        try:
            for assessment in Assessment.select():
                logger.info(f"checking {assessment.project_name} for updates")

                assessment_params = model_to_dict(assessment)
                new_params = assessment_params.copy()

                changed = False

                for resource in assessment.resources:
                    new_content = asyncio.run(fetch_content(resource.url))
                    if resource.content_hash != hash_content(new_content):
                        new_params[resource.url] = new_content
                        changed = True

                    if not changed:
                        continue

                    old_context = model_params_to_str(assessment_params)
                    new_context = model_params_to_str(new_params)

                    context = f"""
                    Here is your previous context:
                    {old_context}

                    Here is your previous decision:
                    {assessment.decision}
                    {assessment.justification}

                    Here is the updated content:
                    {new_context}
                    """

                    new_response = json.loads(
                        ask_gpt(config.base_prompt + config.update_prompt, context)
                    )

                    if new_response["outcome"] == "unchanged":
                        continue

                    assessment.update(**new_response).execute()
                    resource.content_hash = hash_content(new_content)
                    resource.save()

                    asyncio.run(send_update_notification(assessment_params, new_response))
        except Exception as e:
            logger.error(f"error: {e} updating resources")


monitor_thread_sleep_seconds = 3

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    load_config(os.path.join(current_dir, "config.toml"))

    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

    config = get_config()

    message_handler = []
    action_handlers = []
    view_submission_handlers = []

    app = asyncio.run(
        init_bot(
            openai_organization_id=config.openai_organization_id,
            slack_message_handler=message_handler,
            slack_action_handlers=action_handlers,
            slack_template_path=template_path,
        )
    )

    # Register your custom event handlers
    app.event("app_mention")(handle_app_mention_events)
    app.message()(handle_message_events)

    app.action("submit_form")(submit_form)
    app.action(re.compile("submit_followup_questions.*"))(submit_followup_questions)

    t = threading.Thread(target=update_resources)
    t.start()

    # Start the app
    asyncio.run(start_app(app))
