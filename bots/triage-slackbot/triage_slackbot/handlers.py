import typing as t
from enum import Enum
from logging import getLogger

from openai_slackbot.clients.slack import CreateSlackMessageResponse, SlackClient
from openai_slackbot.handlers import BaseActionHandler, BaseHandler, BaseMessageHandler
from openai_slackbot.utils.slack import (
    RenderedSlackBlock,
    block_id_exists,
    extract_text_from_event,
    get_block_by_id,
    remove_block_id_if_exists,
    render_slack_id_to_mention,
    render_slack_url,
)
from triage_slackbot.category import RequestCategory
from triage_slackbot.config import get_config
from triage_slackbot.openai_utils import get_predicted_category

logger = getLogger(__name__)


class BlockId(str, Enum):
    # Block that will be rendered if on-call recagorizes inbound request but doesn't select a new category.
    empty_category_warning = "empty_category_warning_block"

    # Block that will be rendreed if on-call recategorizes inbound request to "Other" but doesn't select a conversation.
    empty_conversation_warning = "empty_conversation_warning_block"

    # Block that will be rendered to show on-call all the remaining categories to route to.
    recategorize_select_category = "recategorize_select_category_block"

    # Block that will be rendered to show on-call all the conversations they can reroute the user
    # to, if they select "Other" as the category.
    recategorize_select_conversation = "recategorize_select_conversation_block"


class MessageTemplatePath(str, Enum):
    # Template for feed channel message that summarizes triage updates.
    feed = "messages/feed.j2"

    # Template for message that notifies oncall about inbound request in the same channel as the feed channel.
    notify_oncall_in_feed = "messages/notify_oncall_in_feed.j2"

    # Template for message that notifies oncall about inbound request in a different channel from the feed channel.
    notify_oncall_channel = "messages/notify_oncall_channel.j2"

    # Template for message that will autorespond to inbound requests.
    autorespond = "messages/autorespond.j2"


BlockIdToTemplatePath: t.Dict[BlockId, str] = {
    BlockId.empty_category_warning: "blocks/empty_category_warning.j2",
    BlockId.empty_conversation_warning: "blocks/empty_conversation_warning.j2",
    BlockId.recategorize_select_conversation: "blocks/select_conversation.j2",
}


class InboundRequestHandlerMixin(BaseHandler):
    def __init__(self, slack_client: SlackClient) -> None:
        super().__init__(slack_client)
        self.config = get_config()

    def render_block_if_not_exists(
        self, *, block_id: BlockId, blocks: t.List[RenderedSlackBlock]
    ) -> t.List[RenderedSlackBlock]:
        if not block_id_exists(blocks, block_id):
            template_path = BlockIdToTemplatePath[block_id]
            block = self._slack_client.render_blocks_from_template(template_path)
            blocks.append(block)
        return blocks

    def get_selected_category(self, body: t.Dict[str, t.Any]) -> t.Optional[RequestCategory]:
        category = (
            body["state"]
            .get("values", {})
            .get(BlockId.recategorize_select_category, {})
            .get("recategorize_select_category_action", {})
            .get("selected_option", {})
            or {}
        ).get("value")

        if not category:
            return None

        return self.config.categories[category]

    def get_selected_conversation(self, body: t.Dict[str, t.Any]) -> t.Optional[str]:
        return (
            body["state"]
            .get("values", {})
            .get(BlockId.recategorize_select_conversation, {})
            .get("recategorize_select_conversation_action", {})
            .get("selected_conversation")
        )

    async def notify_oncall(
        self,
        *,
        predicted_category: RequestCategory,
        selected_conversation: t.Optional[str],
        remaining_categories: t.List[RequestCategory],
        inbound_message_channel: str,
        inbound_message_ts: str,
        feed_message_channel: str,
        feed_message_ts: str,
        inbound_message_url: str,
    ) -> None:
        autoresponded = await self._maybe_autorespond(
            predicted_category,
            selected_conversation,
            inbound_message_channel,
            inbound_message_ts,
            feed_message_channel,
            feed_message_ts,
        )

        if autoresponded:
            logger.info(f"Autoresponded to inbound request: {inbound_message_url}")
            return

        # This metadata will continue to be passed along to the subsequent
        # notify on-call messages.
        metadata = {
            "event_type": "notify_oncall",
            "event_payload": {
                "inbound_message_channel": inbound_message_channel,
                "inbound_message_ts": inbound_message_ts,
                "feed_message_channel": feed_message_channel,
                "feed_message_ts": feed_message_ts,
                "inbound_message_url": inbound_message_url,
                "predicted_category": predicted_category.key,
            },
        }

        block_args = {
            "predicted_category": predicted_category,
            "remaining_categories": remaining_categories,
            "inbound_message_channel": inbound_message_channel,
        }

        if predicted_category.route_to_channel:
            channel = predicted_category.oncall_slack_id
            thread_ts = None  # This will be a new message, not a thread.
            blocks = await self._get_notify_oncall_channel_blocks(
                **block_args,
                inbound_message_url=inbound_message_url,
            )
        else:
            channel = feed_message_channel
            thread_ts = feed_message_ts  # Post this as a thread reply to the original feed message.
            blocks = await self._get_notify_oncall_in_feed_blocks(**block_args)

        await self._slack_client.post_message(
            channel=channel,
            thread_ts=thread_ts,
            blocks=blocks,
            metadata=metadata,
            text="Notify on-call for new inbound request",
        )

    async def _get_notify_oncall_in_feed_blocks(
        self,
        *,
        predicted_category: RequestCategory,
        remaining_categories: t.List[RequestCategory],
        inbound_message_channel: str,
    ):
        oncall_mention = self._get_oncall_mention(predicted_category)
        predicted_category_display_name = predicted_category.display_name
        oncall_greeting = (
            f":wave: Hi {oncall_mention}"
            if oncall_mention
            else f"No on-call defined for {predicted_category_display_name}"
        )

        return self._slack_client.render_blocks_from_template(
            MessageTemplatePath.notify_oncall_in_feed.value,
            {
                "predicted_category": predicted_category_display_name,
                "oncall_greeting": oncall_greeting,
                "options": RequestCategory.to_block_options(remaining_categories),
                "inbound_message_channel": inbound_message_channel,
            },
        )

    async def _get_notify_oncall_channel_blocks(
        self,
        *,
        predicted_category: RequestCategory,
        remaining_categories: t.List[RequestCategory],
        inbound_message_channel: str,
        inbound_message_url: str,
    ):
        return self._slack_client.render_blocks_from_template(
            MessageTemplatePath.notify_oncall_channel.value,
            {
                "inbound_message_url": inbound_message_url,
                "inbound_message_channel": inbound_message_channel,
                "predicted_category": predicted_category.display_name,
                "options": RequestCategory.to_block_options(remaining_categories),
            },
        )

    def _get_oncall_mention(self, predicted_category: RequestCategory) -> t.Optional[str]:
        oncall_slack_id = predicted_category.oncall_slack_id
        return render_slack_id_to_mention(oncall_slack_id) if oncall_slack_id else None

    async def _maybe_autorespond(
        self,
        predicted_category: RequestCategory,
        selected_conversation: t.Optional[str],
        inbound_message_channel: str,
        inbound_message_ts: str,
        feed_message_channel: str,
        feed_message_ts: str,
    ) -> bool:
        if not predicted_category.autorespond:
            return False

        text = "Hi, thanks for reaching out!"
        if predicted_category.autorespond_message:
            rendered_selected_conversation = (
                render_slack_id_to_mention(selected_conversation) if selected_conversation else None
            )
            text += (
                f" {predicted_category.autorespond_message.format(rendered_selected_conversation)}"
            )

        blocks = self._slack_client.render_blocks_from_template(
            MessageTemplatePath.autorespond.value, {"text": text}
        )
        message = await self._slack_client.post_message(
            channel=inbound_message_channel,
            thread_ts=inbound_message_ts,
            text=text,
            blocks=blocks,
        )
        message_link = await self._slack_client.get_message_link(
            channel=message.channel, message_ts=message.ts
        )

        # Post an update to the feed channel.
        feed_message = (
            f"{render_slack_url(url=message_link, text='Autoresponded')} to inbound request."
        )
        await self._slack_client.post_message(
            channel=feed_message_channel, thread_ts=feed_message_ts, text=feed_message
        )

        return True


class InboundRequestHandler(BaseMessageHandler, InboundRequestHandlerMixin):
    """
    Handles inbound requests in inbound request channel.
    """

    async def handle(self, args):
        event = args.event

        channel = event.get("channel")
        ts = event.get("ts")

        logging_extra = self.logging_extra(args)

        text = extract_text_from_event(event)
        if not text:
            logger.info("No text in event, done processing", extra=logging_extra)
            return

        predicted_category = await self._predict_category(text)
        logger.info(f"Predicted category: {predicted_category}", extra=logging_extra)

        message_link = await self._slack_client.get_message_link(channel=channel, message_ts=ts)
        feed_message = await self._update_feed(
            predicted_category=predicted_category,
            message_channel=channel,
            message_link=message_link,
        )
        logger.info(
            f"Updated feed channel for inbound message link: {message_link}",
            extra=logging_extra,
        )

        remaining_categories = [
            r for r in self.config.categories.values() if r != predicted_category
        ]
        await self.notify_oncall(
            predicted_category=predicted_category,
            selected_conversation=None,
            remaining_categories=remaining_categories,
            inbound_message_channel=channel,
            inbound_message_ts=ts,
            feed_message_channel=feed_message.channel,
            feed_message_ts=feed_message.ts,
            inbound_message_url=message_link,
        )
        logger.info("Notified on-call", extra=logging_extra)

    async def should_handle(self, args):
        event = args.event

        return (
            event["channel"] == self.config.inbound_request_channel_id
            and
            # Don't respond to messages in threads (with the exception of thread replies
            # that are also sent to the channel)
            (
                (
                    event.get("thread_ts") is None
                    and (not event.get("subtype") or event.get("subtype") == "file_share")
                )
                or event.get("subtype") == "thread_broadcast"
            )
        )

    async def _predict_category(self, body) -> RequestCategory:
        predicted_category = await get_predicted_category(body)
        return self.config.categories[predicted_category]

    async def _update_feed(
        self,
        *,
        predicted_category: RequestCategory,
        message_channel: str,
        message_link: str,
    ) -> CreateSlackMessageResponse:
        oncall_mention = self._get_oncall_mention(predicted_category) or "No on-call assigned"
        blocks = self._slack_client.render_blocks_from_template(
            MessageTemplatePath.feed.value,
            {
                "predicted_category": predicted_category.display_name,
                "inbound_message_channel": message_channel,
                "inbound_message_url": message_link,
                "oncall_mention": oncall_mention,
            },
        )

        message = await self._slack_client.post_message(
            channel=self.config.feed_channel_id,
            blocks=blocks,
            text="New inbound request received",
        )
        return message


class InboundRequestAcknowledgeHandler(BaseActionHandler, InboundRequestHandlerMixin):
    """
    Once InboundRequestHandler has predicted the category of an inbound request
    and notifies the corresponding on-call, this handler will be called if on-call
    acknowledges the prediction, i.e. they think the prediction is accurate.
    """

    @property
    def action_id(self):
        return "acknowledge_submit_action"

    async def handle(self, args):
        body = args.body

        notify_oncall_msg = body["container"]
        notify_oncall_msg_ts = notify_oncall_msg["message_ts"]
        notify_oncall_msg_channel = notify_oncall_msg["channel_id"]

        feed_message_metadata = body["message"].get("metadata", {}).get("event_payload", {})
        feed_message_ts = feed_message_metadata["feed_message_ts"]
        feed_message_channel = feed_message_metadata["feed_message_channel"]
        inbound_message_url = feed_message_metadata["inbound_message_url"]
        predicted_category = feed_message_metadata["predicted_category"]

        # Oncall that was notified.
        user = body["user"]

        await self._slack_client.update_message(
            blocks=[],
            channel=notify_oncall_msg_channel,
            ts=notify_oncall_msg_ts,
            # If oncall is notified in the feed channel, don't need to include
            # the inbound message URL since oncall will be notified in the feed
            # message thread, and the URL is already in the original message.
            text=self._get_message(
                user=user,
                category=predicted_category,
                inbound_message_url=inbound_message_url,
                with_url=notify_oncall_msg_channel != feed_message_channel,
            ),
        )

        # If oncall gets notified in a separate channel and not the feed channel,
        # update the feed thread with the acknowledgment.
        if notify_oncall_msg_channel != feed_message_channel:
            await self._slack_client.post_message(
                blocks=[],
                channel=feed_message_channel,
                thread_ts=feed_message_ts,
                text=self._get_message(
                    user=user,
                    category=predicted_category,
                    inbound_message_url=inbound_message_url,
                    with_url=False,
                ),
            )

        feed_message = await self._slack_client.get_message(
            channel=feed_message_channel, ts=feed_message_ts
        )
        if feed_message:
            # If the original message has been thumbs-downed, this means
            # that the bot's original prediction is wrong, so don't thumbs
            # up the feed message.
            wrong_original_prediction = any(
                [r["name"] == "-1" for r in feed_message.get("reactions", [])]
            )

            if not wrong_original_prediction:
                await self._slack_client.add_reaction(
                    channel=feed_message_channel,
                    name="thumbsup",
                    timestamp=feed_message_ts,
                )

    def _get_message(
        self, user: t.Dict, category: str, inbound_message_url: str, with_url: bool
    ) -> str:
        message = f":thumbsup: {render_slack_id_to_mention(user['id'])} acknowledged the "
        if with_url:
            message += render_slack_url(url=inbound_message_url, text="inbound message")
        else:
            message += "inbound message"

        return f"{message} triaged to {self.config.categories[category].display_name}."


class InboundRequestRecategorizeHandler(BaseActionHandler, InboundRequestHandlerMixin):
    """
    This handler will be called if on-call wants to recategorize the request
    that they get notified about.
    """

    @property
    def action_id(self):
        return "recategorize_submit_action"

    async def handle(self, args):
        body = args.body

        notify_oncall_msg = body["container"]
        notify_oncall_msg_ts = notify_oncall_msg["message_ts"]
        notify_oncall_msg_channel = notify_oncall_msg["channel_id"]

        msg_metadata = body["message"].get("metadata", {}).get("event_payload", {})
        feed_message_ts = msg_metadata["feed_message_ts"]
        feed_message_channel = msg_metadata["feed_message_channel"]
        inbound_message_url = msg_metadata["inbound_message_url"]

        # Predicted category that turned out to be incorrect
        # and wanted to be recategorized.
        predicted_category = self.config.categories[msg_metadata.pop("predicted_category")]
        assert predicted_category

        user: t.Dict = body["user"]

        notify_oncall_msg_blocks = body["message"]["blocks"]
        selection_block = get_block_by_id(
            notify_oncall_msg_blocks, BlockId.recategorize_select_category
        )
        remaining_category_keys: t.List[str] = [
            o["value"] for o in selection_block["accessory"]["options"]
        ]

        selected_category: t.Optional[RequestCategory] = self.get_selected_category(body)
        selected_conversation: t.Optional[str] = self.get_selected_conversation(body)
        valid, notify_oncall_msg_blocks = await self._validate_selection(
            selected_category, selected_conversation, notify_oncall_msg_blocks
        )
        if valid:
            assert selected_category, "selected_category should be set if valid"
            message_kwargs = {
                "user": user,
                "predicted_category": predicted_category,
                "selected_category": selected_category,
                "selected_conversation": selected_conversation,
                "inbound_message_url": inbound_message_url,
            }

            await self._slack_client.update_message(
                blocks=[],
                channel=notify_oncall_msg_channel,
                ts=notify_oncall_msg_ts,
                # If the feed message is in the same channel as the notify on-call message, don't need to include
                # the URL since it's already in the original feed message.
                text=self._get_message(
                    **message_kwargs,
                    with_url=notify_oncall_msg_channel != feed_message_channel,
                ),
            )

            # Indicate that the previous predicted category is not accurate.
            await self._slack_client.add_reaction(
                channel=feed_message_channel,
                name="thumbsdown",
                timestamp=feed_message_ts,
            )

            # If the feed message is in a different channel than the notify on-call message,
            # post recategorization update to the feed channel.
            if notify_oncall_msg_channel != feed_message_channel:
                await self._slack_client.post_message(
                    blocks=[],
                    channel=feed_message_channel,
                    thread_ts=feed_message_ts,
                    text=self._get_message(**message_kwargs, with_url=False),
                )

            remaining_categories = [
                self.config.categories[category_key]
                for category_key in remaining_category_keys
                if category_key != selected_category.key
            ]

            # Route this to the next oncall.
            await self.notify_oncall(
                predicted_category=selected_category,
                selected_conversation=selected_conversation,
                remaining_categories=remaining_categories,
                **msg_metadata,
            )
        else:
            # Display warning.
            await self._slack_client.update_message(
                blocks=notify_oncall_msg_blocks,
                channel=notify_oncall_msg_channel,
                ts=notify_oncall_msg_ts,
                text="",
            )

    def _get_message(
        self,
        *,
        user: t.Dict,
        predicted_category: RequestCategory,
        selected_category: RequestCategory,
        selected_conversation: t.Optional[str],
        inbound_message_url: str,
        with_url: bool,
    ) -> str:
        rendered_selected_conversation = (
            render_slack_id_to_mention(selected_conversation) if selected_conversation else None
        )
        selected_category_display_name = selected_category.display_name.format(
            rendered_selected_conversation
        )

        message_text = f"<{inbound_message_url}|inbound message>" if with_url else "inbound message"
        return f":thumbsdown: {render_slack_id_to_mention(user['id'])} reassigned the {message_text} from {predicted_category.display_name} to: {selected_category_display_name}."

    async def _validate_selection(
        self,
        selected_category: t.Optional[RequestCategory],
        selected_conversation: t.Optional[str],
        blocks: t.List[RenderedSlackBlock],
    ) -> t.Tuple[bool, t.List[RenderedSlackBlock]]:
        if not selected_category:
            return False, self.render_block_if_not_exists(
                block_id=BlockId.empty_category_warning, blocks=blocks
            )
        elif selected_category.is_other() and not selected_conversation:
            return False, self.render_block_if_not_exists(
                block_id=BlockId.empty_conversation_warning, blocks=blocks
            )

        return True, blocks


class InboundRequestRecategorizeSelectHandler(BaseActionHandler, InboundRequestHandlerMixin):
    """
    This handler will be called if on-call selects a new category for a request they
    get notififed about.
    """

    @property
    def action_id(self):
        return "recategorize_select_category_action"

    async def handle(self, args):
        body = args.body

        notify_oncall_msg = body["container"]
        notify_oncall_msg_ts = notify_oncall_msg["message_ts"]
        notify_oncall_msg_channel = notify_oncall_msg["channel_id"]

        notify_oncall_msg_blocks = body["message"]["blocks"]
        notify_oncall_msg_blocks = remove_block_id_if_exists(
            notify_oncall_msg_blocks, BlockId.empty_category_warning
        )

        selected_category = self.get_selected_category(body)
        if selected_category.is_other():
            # Prompt on-call to select a conversation if Other category is selected.
            notify_oncall_msg_blocks = self.render_block_if_not_exists(
                block_id=BlockId.recategorize_select_conversation,
                blocks=notify_oncall_msg_blocks,
            )
        else:
            # Remove warning if on-call updates their selection from Other to non-Other.
            notify_oncall_msg_blocks = remove_block_id_if_exists(
                notify_oncall_msg_blocks, BlockId.recategorize_select_conversation
            )

        # Update message with warnings, if any.
        await self._slack_client.update_message(
            blocks=notify_oncall_msg_blocks,
            channel=notify_oncall_msg_channel,
            ts=notify_oncall_msg_ts,
        )


class InboundRequestRecategorizeSelectConversationHandler(BaseActionHandler):
    """
    This handler will be called if on-call selects a conversation to route the request to.
    """

    @property
    def action_id(self):
        return "recategorize_select_conversation_action"

    async def handle(self, args):
        pass
