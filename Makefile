# Thin wrapper: every target runs scripts/tasks.py so that Windows users
# without make can run `python scripts/tasks.py <target>` instead.
PY ?= python
ARGS ?=

TARGETS := data-report convert nnunet-prep sitegroups train-smoke train-loso infer example-predictions \
           uncertainty eval site-risk app export-demo fixtures lint test test-ui test-all docs

.PHONY: $(TARGETS) help
help:
	@$(PY) scripts/tasks.py --list

$(TARGETS):
	$(PY) scripts/tasks.py $@ -- $(ARGS)
