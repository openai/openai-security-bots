import os
import typing as t

import toml
from dotenv import load_dotenv
from pydantic import BaseModel

_CONFIG = None


class Config(BaseModel):
    # OpenAI organization ID associated with OpenAI API key.
    openai_organization_id: str

    # Slack channel where triage alerts are posted.
    feed_channel_id: str


def load_config(config_path: str = None) -> Config:
    load_dotenv()

    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.toml")
    with open(config_path) as f:
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
