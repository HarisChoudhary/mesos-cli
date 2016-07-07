import mesos

from mesos.plugins import PluginBase
from daemon import MesosDaemon
from multiprocessing.connection import Client

PLUGIN_CLASS = "Daemon"
PLUGIN_NAME = "daemon"

VERSION = "Mesos CLI Daemon Plugin 1.0"

SHORT_HELP = "Daemon specific commands for the Mesos CLI"

DAEMON_PORT = 5023


class Daemon(PluginBase):

    COMMANDS = {
        "create" : {
            "arguments" : [],
            "flags" : {
                },
            "short_help" : "Spawn a mesos cluster daemon",
            "long_help"  :
"""
Creates a mesos cluster daemon for testing purposes.
Cluster consists of 1 Master and 1 Agent.
"""
        },
        "destroy" : {
            "arguments" : [],
            "flags" : {
                },
            "short_help" : "Brings down a mesos cluster daemon",
            "long_help"  :
"""
Brings down a mesos cluster daemon previously spawned with the 'create' command
"""
        },
        "spawn" : {
            "arguments" : [],
            "flags" : {
                "--master" : "Spawn a master node process on the daemon",
                "--agent" : "Spawn a agent node process on the daemon"
                },
            "short_help" : "Spawn a mesos master/agent process",
            "long_help"  :
"""
Spawns a mesos master/agent process depending on flags used
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
    
    def create(self,argv):
        daemon = MesosDaemon(DAEMON_PORT)
        daemon.start()
        return

    def destroy(self,argv):
        daemon = MesosDaemon(DAEMON_PORT)
        daemon.stop()
        return

    def spawn(self,argv):
        msg = {"command" : []}
        if argv["--master"]:
            msg["command"].append('run_master')

        if argv["--agent"]:
            msg["command"].append('run_agent')

        if len(msg["command"]) != 0:
            address = ('localhost', DAEMON_PORT)
            conn = Client(address)
            conn.send(msg)
            conn.close()

    def kill(self,argv):
        msg = {"command" : []}
        if argv["--master"]:
            msg["command"].append('kill_master')

        if argv["--agent"]:
            msg["command"].append('kill_agent')

        if len(msg["command"]) != 0:
            address = ('localhost', DAEMON_PORT)
            conn = Client(address)
            conn.send(msg)
            conn.close()
