SHELL := /bin/bash

clean-venv: rm-venv
	python3 -m venv venv 


rm-venv:
	if [ -d "venv" ]; then rm -rf venv; fi

maybe-clear-shared:
ifeq ($(SKIP_CLEAR_SHARED), true)
else
	pip cache remove openai_slackbot
endif

build-shared:
	pip install -e ./shared/openai-slackbot


build-bot: maybe-clear-shared build-shared
	cd bots/$(BOT) && $(MAKE) init-pyproject && pip install -e .


run-bot:
	python bots/$(BOT)/$(subst -,_,$(BOT))/bot.py


clear:
	find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf


build-all: 
	$(MAKE) build-bot BOT=triage-slackbot SKIP_CLEAR_SHARED=true


test-all: 
	pytest shared/openai-slackbot && \
	pytest bots/triage-slackbot && \
	pytest bots/incident-response-slackbot