import typing as t

RenderedSlackBlock = t.NewType("RenderedSlackBlock", t.Dict[str, t.Any])


def block_id_exists(blocks: t.List[RenderedSlackBlock], block_id: str) -> bool:
    return any([block.get("block_id") == block_id for block in blocks])


def remove_block_id_if_exists(blocks: t.List[RenderedSlackBlock], block_id: str) -> t.List:
    return [block for block in blocks if block.get("block_id") != block_id]


def get_block_by_id(blocks: t.Dict, block_id: str) -> t.Dict:
    for block in blocks:
        if block.get("block_id") == block_id:
            return block
    return {}


def extract_text_from_event(event) -> str:
    """Extracts text from either plaintext and block message."""

    # Extract text from plaintext message.
    text = event.get("text")
    if text:
        return text

    # Extract text from message blocks.
    texts = []
    attachments = event.get("attachments", [])
    for attachment in attachments:
        attachment_message_blocks = attachment.get("message_blocks", [])
        for amb in attachment_message_blocks:
            message_blocks = amb.get("message", {}).get("blocks", [])
            for mb in message_blocks:
                mb_elements = mb.get("elements", [])
                for mbe in mb_elements:
                    mbe_elements = mbe.get("elements", [])
                    for mbee in mbe_elements:
                        if mbee.get("type") == "text":
                            texts.append(mbee["text"])

    return " ".join(texts).strip()


def render_slack_id_to_mention(id: str):
    """Render a usergroup or user ID to a mention."""

    if not id:
        return ""
    elif id.startswith("U"):
        return f"<@{id}>"
    elif id.startswith("S"):
        return f"<!subteam|{id}>"
    elif id.startswith("C"):
        return f"<#{id}>"
    else:
        raise ValueError(f"Unsupported/invalid ID type: {id}")


def render_slack_url(*, url: str, text: str) -> str:
    """Render a URL to a clickable link."""
    return f"<{url}|{text}>"
