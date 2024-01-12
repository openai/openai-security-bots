


SDLC Slackbot decides if a project merits a security review.

## Prerequisites

You will need:
1. A Slack application (aka your sdlc bot) with Socket Mode enabled
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

## Setup

From the current directory, run:
```
make init-pyproject
```

From the repo root, run:
```
make clean-venv
source venv/bin/activate
make build-bot BOT=sdlc-slackbot
```

## Run bot with example configuration

The example configuration is `config.toml`. Replace the configuration values as needed.
You need to at least replace the `openai_organization_id` and `notification_channel_id`.

For optional Google Docs integration you'll need a 'credentials.json' file:
- Go to the Google Cloud Console.
- Select your project.
- Navigate to "APIs & Services" > "Credentials".
- Under "OAuth 2.0 Client IDs", find your client ID and download the JSON file.
- Save it in the `sdlc-slackbot/sdlc_slackbot` directory as `credentials.json`.



⚠️ *Make sure that the bot is added to the channels it needs to read from and post to.* ⚠️

From the repo root, run:

```
make run-bot BOT=sdlc-slackbot
```

