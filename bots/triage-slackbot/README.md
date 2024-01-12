<p align="center">
  <img width="150" alt="triage-slackbot-logo" src="https://github.com/openai/openai-security-bots/assets/10287796/fab77b12-1640-452c-86df-30b8bdd6cd35">
  <h1 align="center">Triage Slackbot</h1>
</p>

Triage Slackbot triages inbound requests in a Slack channel to different sub-teams within your organization.

## Prerequisites

You will need:
1. A Slack application (aka your triage bot) with Socket Mode enabled
2. OpenAI API key

Generate an App-level token for your Slack app, by going to:
```
Your Slack App > Basic Information > App-Level Tokens > Generate Token and Scopes
```
Create a new token with `connections:write` scope. This is your `SOCKET_APP_TOKEN` token.

Once you have them, from the current directory, run:
```
$ make init-env-file
```
and fill in the right values.

Your Slack App needs the following scopes:

- channels:history
- chat:write
- groups:history
- reactions:read
- reactions:write

## Setup

From the current directory, run:
```
make init-pyproject
```

From the repo root, run:
```
make clean-venv
source venv/bin/activate
make build-bot BOT=triage-slackbot
```

## Run bot with example configuration

The example configuration is `config.toml`. Replace the configuration values as needed.

⚠️ *Make sure that the bot is added to the channels it needs to read from and post to.* ⚠️

From the repo root, run:

```
make run-bot BOT=triage-slackbot
```

## Demo

This demo is run with the provided `config.toml`. In this demo:

```
inbound_request_channel_id = ID of #inbound-security-requests channel
feed_channel_id = ID of #inbound-security-requests-feed channel

[[ categories ]]
key = "appsec"
...
oncall_slack_id = ID of #appsec-requests channel

[[ categories ]]
key = "privacy"
...
oncall_slack_id = ID of @tiffany user
```

The following triage scenarios are supported: 

First, the bot categorizes the inbound requests accurately, and on-call acknowledges this prediction.

https://github.com/openai/openai-security-bots/assets/10287796/2bb8b301-41b6-450f-a578-482e89a75050

Secondly, the bot categorizes the request into a category that it can autorespond to, e.g. Physical Security, 
and there is no manual action from on-call required.

https://github.com/openai/openai-security-bots/assets/10287796/e77bacf0-e16d-4ed3-9567-6f3caaab02ad

Finally, on-call can re-route an inbound request to another category's on-call if the initial predicted 
category is not accurate. Additionally, if `other_category_enabled` is set to true, on-call can select any
channels it can route the user to:

https://github.com/openai/openai-security-bots/assets/10287796/04247a29-f904-42bc-82d8-12b7f2b7e170

The bot will reply to the thread with this:

<img width="671" alt="autorespond" src="https://github.com/openai/openai-security-bots/assets/10287796/ba01186f-41c4-4cd6-9982-2edb9429b2c4">
