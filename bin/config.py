import os
import sys

# The top level directory of this project
PROJECT_DIR = os.path.join(os.path.dirname(__file__), os.pardir)

# Build the list of paths to search for plugins. Some of these
# paths point to builtin plugins. Others are pulled from the
# 'MESOS_CLI_PLUGIN_PATH' environment variable.
MESOS_CLI_PLUGINS = [
    os.path.join(PROJECT_DIR, "lib/mesos/plugins", "example"),
    os.path.join(PROJECT_DIR, "lib/mesos/plugins", "container"),
    os.path.join(PROJECT_DIR, "lib/mesos/plugins", "cluster"),
    os.path.join(PROJECT_DIR, "lib/mesos/plugins", "agent"),
    os.path.join(PROJECT_DIR, "lib/mesos/plugins", "daemon")
]
if os.environ.get('MESOS_CLI_PLUGINS'):
    MESOS_CLI_PLUGINS += \
    filter(None, os.environ.get('MESOS_CLI_PLUGINS').split(":"))

# Set default IP's for Master/Agents.
MASTER_IP = "127.0.0.1:5050";
AGENT_IP = "127.0.0.1:5051";
# A dictionary from IP's to SSH keys to assist with remote commands
SSH_KEYS = {}

if os.environ.get('MESOS_CLI') is not None:
    configData = None
    try:
        with open(os.environ['MESOS_CLI']) as data_file:
            configData = json.load(data_file)
            if "MASTER_IP" in configData:
                MASTER_IP = configData["MASTER_IP"]

            if "AGENT`_IP" in configData:
                AGENT_IP = configData["AGENT_IP"]

            if "SSH_KEYS" in configData:
                SSH_KEYS = configData["SSH_KEYS"]
    except:
        pass

