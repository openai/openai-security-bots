import os
from logging import getLogger

from incident_response_slackbot.config import load_config, get_config
from incident_response_slackbot.db.database import Database
from openai_slackbot.clients.slack import CreateSlackMessageResponse, SlackClient
from openai_slackbot.utils.envvars import string
from slack_bolt.app.async_app import AsyncApp

logger = getLogger(__name__)

DATABASE = Database()

load_config()
config = get_config()

async def post_alert(alert):
    """
    This function posts an alert to the Slack channel.
    It first initializes the Slack client with the bot token and template path.
    Then, it extracts the user_id, alert_name, and properties from the alert.
    Finally, it posts the alert to the Slack channel and sends the initial details.

    Args:
        alert (dict): The alert to be posted. It should contain 'user_id', 'name', and 'properties'.
    """

    slack_bot_token = string("SLACK_BOT_TOKEN")
    app = AsyncApp(token=slack_bot_token)
    slack_template_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "../incident_response_slackbot/templates",
    )
    slack_client = SlackClient(app.client, slack_template_path)

    # Extracting the user_id, alert_name, and properties from the alert
    user_id = alert.get("user_id")
    alert_name = alert.get("name")
    properties = alert.get("properties")

    message = await incident_feed_begin(
        slack_client=slack_client, user_id=user_id, alert_name=alert_name
    )

    DATABASE.add(user_id, message.ts)

    await initial_details(slack_client=slack_client, message=message, properties=properties)


async def incident_feed_begin(
    *, slack_client: SlackClient, user_id: str, alert_name: str
) -> CreateSlackMessageResponse:
    """
    This function begins the incident feed by posting the initial alert message.
    It first renders the blocks from the template with the user_id and alert_name.
    Then, it posts the message to the Slack channel.

    Args:
        slack_client (SlackClient): The Slack client.
        user_id (str): The Slack user ID.
        alert_name (str): The name of the alert.

    Returns:
        CreateSlackMessageResponse: The response from creating the Slack message.

    Raises:
        Exception: If the initial alert message fails to post.
    """

    try:
        blocks = slack_client.render_blocks_from_template(
            "messages/incident_alert.j2",
            {
                "user_id": user_id,
                "alert_name": alert_name,
            },
        )
        message = await slack_client.post_message(
            channel=config.feed_channel_id,
            blocks=blocks,
            text=f"{alert_name} via <@{user_id}>",
        )
        return message

    except Exception:
        logger.exception("Initial alert feed message failed")


def get_alert_details(**kwargs) -> str:
    """
    This function returns the alert details for each key in the
    property. Each alert could have different properties.
    """
    content = ""
    for key, value in kwargs.items():
        line = f"The value of {key} for this alert is {value}. "
        content += line
    if content:
        return content
    return "No details available for this alert."


async def initial_details(*, slack_client: SlackClient, message, properties):
    """
    This function posts the initial details of an alert to a Slack thread.

    Args:
        slack_client (SlackClient): The Slack client.
        message: The initial alert message.
        properties: The properties of the alert.
    """
    thread_ts = message.ts
    details = get_alert_details(**properties)

    await slack_client.post_message(
        channel=config.feed_channel_id, text=f"{details}", thread_ts=thread_ts
    )
