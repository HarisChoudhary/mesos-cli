import os
import sys

# The top level directory of this project
PROJECT_DIR = os.path.join(os.path.dirname(__file__), os.pardir)

# Build the list of paths to search for plugins. Some of these
# paths point to builtin plugins. Others are pulled from the
# 'MESOS_CLI_PLUGIN_PATH' environment variable.
MESOS_CLI_PLUGINS = [
    os.path.join(PROJECT_DIR, "lib/mesos/plugins", "example")
]
if os.environ.get('MESOS_CLI_PLUGINS'):
	MESOS_CLI_PLUGINS += \
        filter(None, os.environ.get('MESOS_CLI_PLUGINS').split(":"))
