INSTALLER = tools/agentutils-install
RUN = uv run --directory $(INSTALLER)

.PHONY: install uninstall install-skills uninstall-skills status help

install:            ## Install all CLI tools globally
	$(RUN) agentutils install

uninstall:          ## Uninstall all CLI tools
	$(RUN) agentutils uninstall

install-skills:     ## Install Claude Code skills to ~/.claude/skills/
	$(RUN) agentutils install-skills

uninstall-skills:   ## Remove Claude Code skills
	$(RUN) agentutils uninstall-skills

status:             ## Show installation status
	$(RUN) agentutils status

install-all: install install-skills  ## Install tools + skills

uninstall-all: uninstall uninstall-skills  ## Uninstall tools + skills

help:               ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
