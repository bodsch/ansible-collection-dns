#
export COLLECTION_ROLE      ?=
export COLLECTION_SCENARIO  ?= default
export TOX_ANSIBLE          ?= ansible_9.5
# --------------------------------------------------------

TEMP_REPO_URL := http://git.boone-schulz.de/ansible/ansible-hooks.git
TEMP_REPO_PATH := collections/hooks
TARGET_DIR := hooks
CACHE_DIR := ${HOME}/.cache/ansible/ansible-hooks   # persistent im Projekt

# --------------------------------------------------------

# Alle Targets, die schlicht ein Skript in hooks/ aufrufen
HOOKS := install uninstall doc prepare converge destroy verify test lint gh-clean
TARGET_DIR := hooks

.SILENT: pre post
.PHONY: $(HOOKS)

.DEFAULT_GOAL := converge

# $@ expandiert zu dem Namen des gerade angeforderten Targets
$(HOOKS): | hooks-ready
	@hooks/$@

hooks-ready:
	@if [ ! -d "hooks" ] || [ -z "$$(ls -A 'hooks' 2>/dev/null)" ]; then \
		$(MAKE) --no-print-directory fetch-hooks >/dev/null 2>&1; \
	fi

fetch-hooks:
	@if [ -d "$(CACHE_DIR)/.git" ]; then \
		printf '%s\n' '>> updating cache: $(CACHE_DIR)'; \
		git -C "$(CACHE_DIR)" fetch --depth=1 --prune origin; \
		git -C "$(CACHE_DIR)" reset --hard origin/HEAD; \
		# falls Sparse-Pfad geändert wurde, erneut setzen:
		git -C "$(CACHE_DIR)" sparse-checkout set "$(TEMP_REPO_PATH)"; \
	else \
		printf '%s\n' '>> initial clone: $(CACHE_DIR)'; \
		mkdir -p "$(dir $(CACHE_DIR))"; \
		GIT_TERMINAL_PROMPT=0 git clone --depth 1 --filter=blob:none --sparse "$(TEMP_REPO_URL)" "$(CACHE_DIR)"; \
		git -C "$(CACHE_DIR)" sparse-checkout set "$(TEMP_REPO_PATH)"; \
	fi
	@mkdir -p "$(TARGET_DIR)"
	@rsync -a --delete "$(CACHE_DIR)/$(TEMP_REPO_PATH)/" "$(TARGET_DIR)/"
