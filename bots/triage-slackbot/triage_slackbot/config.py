import os
import typing as t

import toml
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from pydantic.functional_validators import AfterValidator, BeforeValidator
from triage_slackbot.category import OTHER_KEY, RequestCategory

_CONFIG = None


def convert_categories(v: t.List[t.Dict]):
    categories = {}

    for category in v:
        categories[category["key"]] = category
    return categories


def validate_channel(channel_id: str) -> str:
    if not channel_id.startswith("C"):
        raise ValueError("channel ID must start with 'C'")
    return channel_id


class Config(BaseModel):
    # OpenAI organization ID associated with OpenAI API key.
    openai_organization_id: str

    # OpenAI prompt to categorize the request.
    openai_prompt: str

    # Slack channel where inbound requests are received.
    inbound_request_channel_id: t.Annotated[str, AfterValidator(validate_channel)]

    # Slack channel where triage updates are posted.
    feed_channel_id: t.Annotated[str, AfterValidator(validate_channel)]

    # Valid categories for inbound requests to be triaged into.
    categories: t.Annotated[t.Dict[str, RequestCategory], BeforeValidator(convert_categories)]

    # Enables "Other" category, which will allow triager to
    # route the request to a specific conversation.
    other_category_enabled: bool

    @model_validator(mode="after")
    def check_category_keys(config: "Config") -> "Config":
        if config.other_category_enabled:
            if OTHER_KEY in config.categories:
                raise ValidationError("other category is reserved and cannot be used")

        category_keys = set(config.categories.keys())
        if len(category_keys) != len(config.categories):
            raise ValidationError("category keys must be unique")

        return config


def load_config(path: str):
    load_dotenv()

    with open(path) as f:
        cfg = toml.loads(f.read())
        config = Config(**cfg)

        if config.other_category_enabled:
            other_category = RequestCategory(
                key=OTHER_KEY,
                display_name=OTHER_KEY.capitalize(),
                oncall_slack_id=None,
                autorespond=True,
                autorespond_message="Our team looked at your request, and this is actually something that we don't own. We recommend reaching out to {} instead.",
            )
            config.categories[other_category.key] = other_category

    global _CONFIG
    _CONFIG = config
    return _CONFIG


def get_config() -> Config:
    global _CONFIG
    if _CONFIG is None:
        raise Exception("config not initialized, call load_config() first")
    return _CONFIG
