import openai


def get_form_input(values, *fields):
    ret = {}
    for f in fields:
        container = values[f][f + "_input"]
        value = container.get("value")
        if value:
            ret[f] = container["value"]
        else:
            for key, item in container.items():
                if key.startswith("selected_") and item:
                    ret[f] = item
                    break
    return ret


def plain_text(text):
    return dict(type="plain_text", text=text)


def field(type, placeholder, **kwargs):
    return dict(type=type, placeholder=plain_text(placeholder), **kwargs)


def input_block(block_id, label, element):
    if "action_id" not in element:
        element["action_id"] = block_id + "_input"

    return dict(
        type="input",
        block_id=block_id,
        label=plain_text(label),
        element=element,
    )


def submit_block(action_id):
    return dict(
        type="actions",
        elements=[
            dict(
                type="button",
                text=plain_text("Submit"),
                action_id=action_id,
                style="primary",
            )
        ],
    )


def ask_gpt(prompt, context):
    response = openai.ChatCompletion.create(
        model="gpt-4-32k",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": context},
        ],
    )

    return response.choices[0].message["content"]
