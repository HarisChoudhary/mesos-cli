import json
import sys
import urllib2
import config
import os
import subprocess
import ctypes
from socket import error as socket_error
from multiprocessing import Process, Manager

import mesos

from mesos.plugins import PluginBase
from mesos.util import Table

PLUGIN_CLASS = "Container"
PLUGIN_NAME = "container"

VERSION = "Mesos CLI Container Plugin 1.0"

SHORT_HELP = "Container specific commands for the Mesos CLI"


class Container(PluginBase):

    COMMANDS = {
        "ps" : {
            "arguments" : [],
            "flags" : {
                "--addr=Addr" :
                "IP and Port of Agent [Default: "+config.AGENT_IP+"]"
                },
            "short_help" : "List all running containers on this agent",
            "long_help"  :
"""
List all containers that are currently running on this local agent machine.
Also displays
"""
        },
        "execute" : {
            "arguments" : ["<container-ID>", "<command>..."],
            "flags" : {
                "--addr=Addr" :
                "IP and Port of Agent [Default: "+config.AGENT_IP+"]"
                },
            "short_help" : "Execute a command within the specified container",
            "long_help"  :
"""
Will run the provided command within the container specified by the ID.
Only supports the Mesos Containerizer.
"""
        },
        "logs" : {
            "arguments" : ["<container-ID>"],
            "flags" : {
                "--addr=Addr" :
                "IP and Port of Agent [Default: "+config.AGENT_IP+"]",
                "--noStdout" : "Do not print Stdout",
                "--noStderr" : "Do not print Stderr"
                },
            "short_help" : "Show logs",
            "long_help"  :
"""
Show stdout/stderr logs of a container
Note: To view logs the --work_dir flag in the agent must be the absolute path
"""
        },
        "top" : {
            "arguments" : ["<container-ID>"],
            "flags" : {
                "--addr=Addr" :
                "IP and Port of Agent [Default: "+config.AGENT_IP+"]"
                },
            "short_help" : "Show running processes of a container",
            "long_help"  :
"""
Show the processes running inside of a container.
"""
        },
        "stats" : {
            "arguments" : ["<container-ID>..."],
            "flags" : {
                "--addr=Addr" :
                "IP and Port of Agent [Default: "+config.AGENT_IP+"]"
                },
            "short_help" : "Show status for one or more Containers",
            "long_help"  :
"""
Show various statistics of running containers. Inputting multiple ID's
will output the container statistics for all those containers.
"""
        },
        "images" : {
            "arguments" : [],
            "flags" : {
                "--addr=Addr" :
                "IP and Port of Agent [Default: "+config.AGENT_IP+"]"
                },
            "short_help" : "Lists container images",
            "long_help"  :
"""
List images present in the Docker/Appc store on the agent
"""
        }
    }

    def __setup__(self, command, argv):
        pass

    def __autocomplete__(self, command, current_word, argv):
        return []

    # Checks for root access if needed and runs script as root accordingly
    def check_sudo(self):
        euid = os.geteuid()
        if euid != 0:
            # How we run this script again depends if its a executable or not
            if getattr(sys, 'frozen', False):
                args = ['sudo', sys.executable] + sys.argv[1:] + [os.environ]
            else:
                args = ['sudo', sys.executable] + sys.argv + [os.environ]

            os.execlpe('sudo', *args)

    # Enter a process namespace
    def nsenter(self, pid):
        libc = ctypes.CDLL('libc.so.6')
        namespaces = ['ipc','uts','net','pid','mnt']
        for namespace in namespaces:
            path = '/proc/%s/ns/%s' % (pid, namespace)
            try:
                fd = open(path)
            except IOError, e:
                print("Invalid pid", pid)
                sys.exit(1)

            if libc.setns(fd.fileno(), 0) != 0:
                print "Failed to mount %s namespace" % namespace
                sys.exit(1)

    # Helper function to parse container images from file
    def parse_images(self,text):
        result = ""
        previous = False
        text = text.split('\n')
        for line in text:
            if '@' in line and not previous:
                result += line.split('@')[0] + "\n"
                previous = True
            else:
                previous = False
        if result == "":
            return "No Images Found!"

        return result

    #Helper to hit the specified endpoint and return json results
    def hit_endpoint(self,addr,endpoint):
        try:
            http_response = ( urllib2.urlopen("http://"+addr+endpoint)
                                            .read().decode('utf-8') )
        except socket_error as e:
            print("Cannot establish connection with Agent")
            sys.exit(1)

        return json.loads(http_response)

    # Read file on a Master/Agent Node sandbox
    def read_file(self, addr, path):
        # Determine the current length of the file.
        try:
            result = self.hit_endpoint( addr,
                '/files/read?path='+path+'&offset=-1')
        except HTTPError as error:
            if error.code == 404:
                print ('No such file or directory')
                sys.exit(1)
            else:
                print ('Failed to determine length of file')
                sys.exit(1)

        length = result['offset']
        PAGE_LENGTH = 1024
        offset = 0
        while True:
            try:
                result = self.hit_endpoint( addr,
                    '/files/read?path='+path
                    +'&offset='+str(offset)
                    +'&length='+str(PAGE_LENGTH))
                offset += len(result['data'])
                yield result['data']
                if offset == length:
                    return
            except:
                print('Failed to read file from agent')
                sys.exit(1)

    # Helper function to retrieve PID of a container from /containers endpoint
    # Also Serves the purpose of checking containerizer type
    def get_pid(self,addr,container_id):
        container_info = self.hit_endpoint(addr,"/containers")
        prev_match = False
        pid = None
        for container in container_info:
            if ( container["container_id"].startswith(container_id)
                    and "executor_pid" in container["status"].keys() ):
                if prev_match:
                    print ("Container ID not unique enough")
                    sys.exit(1)
                else:
                    pid = str(container["status"]["executor_pid"])
                    prev_match = True

        if pid is None:
            print ("No container with specified ID found")
            sys.exit(1)

        return pid

    def ps(self,argv):
        container_info = self.hit_endpoint(argv["--addr"], "/containers")
        if len(container_info) == 0:
            print("There are no containers running on this Agent")
            return

        table = Table(["Container ID", "Framework", "Executor"])
        for elem in container_info:
            table.add_row([elem["container_id"], elem["framework_id"],
                                                 elem["executor_id"]])
        print(table.to_string())

    def execute(self,argv):
        self.check_sudo()
        container_pid = self.get_pid(argv["--addr"],argv["<container-ID>"])
        self.nsenter(container_pid)
        subprocess.call(argv["<command>"])

    def logs(self, argv):
        container_pid = self.get_pid(argv["--addr"],argv["<container-ID>"])
        state_info = self.hit_endpoint(argv["--addr"], "/state")
        work_dir = None
        prev_match = False
        for framework in state_info["frameworks"]:
            for executor in framework["executors"]:
                if executor["container"].startswith(argv["<container-ID>"]):
                    if prev_match:
                        print ("Container ID not unique enough")
                    else:
                        work_dir = executor["directory"]
                        prev_match = True

        if work_dir is None:
            print("No container with specified ID found")
            sys.exit(1)

        if not argv["--noStdout"]:
            stdout_file = os.path.join(work_dir,"stdout")
            for line in self.read_file(argv["--addr"], stdout_file):
                print (line)

        print ("=" * 20)

        if not argv["--noStderr"]:
            stderr_file = os.path.join(work_dir,"stderr")
            for line in self.read_file(argv["--addr"], stderr_file):
                print (line)

    def top(self, argv):
        argv["<command>"]=["ps","-ax"]
        self.execute(argv)

    def stats(self, argv):
        self.check_sudo()
        containers = argv["<container-ID>"]
        pids = []
        for container in containers:
            container_pid = self.get_pid(argv["--addr"],container)
            pids.append(container_pid)

        def get_status(proc_dic):
            self.nsenter(proc_dic['pid'])
            command = ["top","-b","-d1","-n1"]
            proc_dic['output'] = subprocess.check_output(command)

        manager = Manager()
        proc_dict = manager.dict()

        """
        We continuously ask containers for the system statistics and print
        the information for the user. A try/except is used because it
        gracefully exits the function when a user kills it via ctrl+c etc
        """
        try:
            while True:
                display = ""
                for pid in pids:
                    proc_dict['pid'] = pid
                    process = Process(target=get_status, args=(proc_dict,))
                    process.start()
                    process.join()
                    #Parse relevant information from the top output
                    stat_lines = proc_dict['output'].split('\n')
                    stat_lines.pop(0)
                    for line in stat_lines:
                        if line == '':
                            break
                        else:
                            display += line+"\n"
                    display += "\n\n"
                subprocess.call(['clear'])
                print(display)
                subprocess.call(['sleep','1'])
        except:
            return

    def images(self, argv):
        self.check_sudo()
        flags = self.hit_endpoint(argv["--addr"],"/flags")

        # Get docker store images
        docker_store = flags["flags"]["docker_store_dir"] + "/storedImages"
        if os.path.exists(docker_store):
            with open(docker_store) as f:
                output = f.read().decode('ISO-8859-1')
            print("Docker Image Store:")
            print(self.parse_images(output))
        else:
            print("No Images present in Docker Store!")

        # Get Appc store images
        appc_store = flags["flags"]["appc_store_dir"] + "/storedImages"
        if os.path.exists(appc_store):
            with open(appc_store) as f:
                output = f.read().decode('ISO-8859-1')
            print("Appc Image Store:")
            print(self.parse_images(output))
        else:
            print("No Images present in Appc Store!")


