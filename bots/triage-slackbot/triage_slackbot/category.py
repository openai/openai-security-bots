import typing as t

from pydantic import BaseModel, ValidationError, model_validator

OTHER_KEY = "other"


class RequestCategory(BaseModel):
    # Key used to identify the category in the config.
    key: str

    # Display name of the category.
    display_name: str

    # Slack ID of the user or channel to route the request to.
    # If user is specified, user will be tagged on the message
    # in the feed channel.
    oncall_slack_id: t.Optional[str] = None

    # If true, no manual triage is required for this category
    # and that the bot will autorespond to the inbound request.
    autorespond: bool = False

    # Message to send when autoresponding to the inbound request.
    autorespond_message: t.Optional[str] = None

    @model_validator(mode="after")
    def check_autorespond(self) -> "RequestCategory":
        if self.autorespond and not self.autorespond_message:
            raise ValidationError("autorespond_message must be set if autorespond is True")
        return self

    @property
    def route_to_channel(self) -> bool:
        return (self.oncall_slack_id or "").startswith("C")

    @classmethod
    def to_block_options(cls, categories: t.List["RequestCategory"]) -> t.Dict[str, str]:
        return dict((c.key, c.display_name) for c in categories)

    def is_other(self) -> bool:
        return self.key == OTHER_KEY
