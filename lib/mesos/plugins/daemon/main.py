from multiprocessing.connection import Client

import config

from mesos.exceptions import CLIException
from mesos.plugins import PluginBase
from daemon import MesosDaemon

PLUGIN_CLASS = "Daemon"
PLUGIN_NAME = "daemon"

VERSION = "Mesos CLI Daemon Plugin 1.0"

SHORT_HELP = "Daemon specific commands for the Mesos CLI"



class Daemon(PluginBase):

    COMMANDS = {
        "start" : {
            "arguments" : [],
            "flags" : {},
            "short_help" : "Start a mesos cluster daemon",
            "long_help"  :
                """
                Creates a mesos cluster daemon for testing purposes.
                Cluster is initially empty but Agents/Masters can be launched
                with the 'spawn' command.
                """
        },
        "stop" : {
            "arguments" : [],
            "flags" : {},
            "short_help" : "Stop a mesos cluster daemon",
            "long_help"  :
                """
                Stops a mesos cluster daemon previously spawned with the
                'start' command
                """
        },
        "spawn" : {
            "arguments" : [],
            "flags" : {
                "--master" : "Spawn a master node process on the daemon",
                "--master_flags=flags" : "Flags for the master node",
                "--agent" : "Spawn a agent node process on the daemon",
                "--agent_flags=flags" : "Flags for the agent node",
                },
            "short_help" : "Spawn a mesos master/agent process",
            "long_help"  :
                """
                Spawns a mesos master/agent process depending on flags used.
                Default flags for Master is:
                work_dir=/tmp/master_daemon, ip=127.0.0.1

                Default flags for Agent is:
                work_dir=/tmp/agent_daemon, master=127.0.0.1:5050

                Note: Requires "mesos-master" and "mesos-agent" to be in your
                Path variable.
                """
        },
        "kill" : {
            "arguments" : [],
            "flags" : {
                "--master" : "kill a master node process on the daemon",
                "--agent" : "kill a agent node process on the daemon"
                },
            "short_help" : "kill a mesos master/agent process",
            "long_help"  :
                """
                kill a mesos master/agent process depending on flags used
                """
        }
    }


    def __setup__(self, command, argv):
        pass

    def __autocomplete__(self, command, current_word, argv):
        return []

    def start(self,argv):
        daemon = MesosDaemon(config.DAEMON_PORT)
        try:
            daemon.start()
        except Exception as exception:
            raise CLIException("Could not start mesos daemon on port {port}:"
                                " {error}".format(port=config.DAEMON_PORT,
                                                  error=exception))
        return

    def stop(self,argv):
        daemon = MesosDaemon(config.DAEMON_PORT)
        try:
            daemon.stop()
        except Exception as exception:
            raise CLIException("Could not stop mesos daemon on port {port}:"
                                " {error}".format(port=config.DAEMON_PORT,
                                                  error=exception))
        return

    def __contact_daemon(self,msg):
        try:
            address = ('localhost', config.DAEMON_PORT)
            conn = Client(address)
            conn.send(msg)
            conn.close()
        except Exception as exception:
            raise CLIException("Error connecting to Daemon {error}"
                                .format(error=exception))

    def spawn(self,argv):
        msg = {"command" : []}
        if argv["--master"]:
            msg["command"].append('run_master')
            if argv["--master_flags"] is None:
                msg["master_flags"] = ("--work_dir=/tmp/master_daemon "
                                "--ip=127.0.0.1")
            else:
                msg["master_flags"] = argv["--master_flags"]

        if argv["--agent"]:
            msg["command"].append('run_agent')
            if argv["--agent_flags"] is None:
                msg["agent_flags"] = ("--work_dir=/tmp/agent_daemon "
                                "--master=127.0.0.1:5050")
            else:
                msg["agent_flags"] = argv["--agent_flags"]

        if len(msg["command"]) != 0:
            try:
                self.__contact_daemon(msg)
            except Exception as exception:
                raise CLIException("Could not spawn nodes: {error}"
                                        .format(error=exception))

    def kill(self,argv):
        msg = {"command" : []}
        if argv["--master"]:
            msg["command"].append('kill_master')

        if argv["--agent"]:
            msg["command"].append('kill_agent')

        if len(msg["command"]) != 0:
            try:
                self.__contact_daemon(msg)
            except Exception as exception:
                raise CLIException("Could not kill nodes: {error}"
                                        .format(error=exception))
