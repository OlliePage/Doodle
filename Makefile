.PHONY: doodle check test stop

# The one command. Updates the checkout when that is safe, makes sure the
# environment and packages are there, says which drawing services have a key,
# clears an app left running on the port, then opens Doodle.
doodle:
	@python3 scripts/doodle_start.py

# The same checks with nothing launched.
check:
	@python3 scripts/doodle_start.py --check-only

test:
	@.venv/bin/python -m pytest

# For when Doodle is running in a terminal you have since closed. The listening
# filter is not optional: without it lsof also returns the browser tab that has
# the page open, and this stops the browser along with the app.
stop:
	@pids=$$(lsof -ti tcp:8501 -sTCP:LISTEN); \
	if [ -n "$$pids" ]; then kill $$pids && echo "Stopped $$pids."; \
	else echo "Nothing is running on port 8501."; fi
