import abc
import typing as t
from logging import getLogger

from openai_slackbot.clients.slack import SlackClient

logger = getLogger(__name__)


class BaseHandler(abc.ABC):
    def __init__(self, slack_client: SlackClient) -> None:
        self._slack_client = slack_client

    async def maybe_handle(self, args):
        await args.ack()

        logging_extra = self.logging_extra(args)
        try:
            should_handle = await self.should_handle(args)
            logger.info(
                f"Handler: {self.__class__.__name__}, should handle: {should_handle}",
                extra=logging_extra,
            )
            if should_handle:
                await self.handle(args)
        except Exception:
            logger.exception("Failed to handle event", extra=logging_extra)

    @abc.abstractmethod
    async def should_handle(self, args) -> bool:
        ...

    @abc.abstractmethod
    async def handle(self, args):
        ...

    @abc.abstractmethod
    def logging_extra(self, args) -> t.Dict[str, t.Any]:
        ...


class BaseMessageHandler(BaseHandler):
    def logging_extra(self, args) -> t.Dict[str, t.Any]:
        fields = {}
        for field in ["type", "subtype", "channel", "ts"]:
            fields[field] = args.event.get(field)
        return fields


class BaseActionHandler(BaseHandler):
    @abc.abstractproperty
    def action_id(self) -> str:
        ...

    async def should_handle(self, args) -> bool:
        return True

    def logging_extra(self, args) -> t.Dict[str, t.Any]:
        return {
            "action_type": args.body.get("type"),
            "action": args.body.get("actions", [])[0],
        }
