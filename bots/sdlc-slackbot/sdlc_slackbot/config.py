import os
import typing as t

import toml
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from pydantic.functional_validators import AfterValidator, BeforeValidator

_CONFIG = None


def validate_channel(channel_id: str) -> str:
    if not channel_id.startswith("C"):
        raise ValueError("channel ID must start with 'C'")
    return channel_id


class Config(BaseModel):
    # OpenAI organization ID associated with OpenAI API key.
    openai_organization_id: str

    context_limit: int

    # OpenAI prompts
    base_prompt: str
    initial_prompt: str
    update_prompt: str
    summary_prompt: str

    reviewing_message: str
    recoverable_error_message: str
    irrecoverable_error_message: str

    # Slack channel for notifications
    notification_channel_id: t.Annotated[str, AfterValidator(validate_channel)]


def load_config(path: str):
    load_dotenv()

    with open(path) as f:
        cfg = toml.loads(f.read())
        config = Config(**cfg)

    global _CONFIG
    _CONFIG = config
    return _CONFIG


def get_config() -> Config:
    global _CONFIG
    if _CONFIG is None:
        raise Exception("config not initialized, call load_config() first")
    return _CONFIG
