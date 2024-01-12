CWD := $(shell pwd)
REPO_ROOT := $(shell git rev-parse --show-toplevel)
ESCAPED_REPO_ROOT := $(shell echo $(REPO_ROOT) | sed 's/\//\\\//g')

init-env-file:
	cp ./sdlc_slackbot/.env.template ./sdlc_slackbot/.env

init-pyproject:
	cat $(CWD)/pyproject.template.toml | \
	sed "s/\$$REPO_ROOT/$(ESCAPED_REPO_ROOT)/g" > $(CWD)/pyproject.toml 
