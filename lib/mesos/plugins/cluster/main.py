import json
import sys
import urllib2
import config
import os
import subprocess
import itertools
from socket import error as socket_error

import mesos

from mesos.plugins import PluginBase
from mesos.util import Table

PLUGIN_CLASS = "Cluster"
PLUGIN_NAME = "cluster"

VERSION = "Mesos CLI Cluster Plugin 1.0"

SHORT_HELP = "Cluster specific commands for the Mesos CLI"


class Cluster(PluginBase):

    COMMANDS = {
        "execute" : {
            "external" : True,
            "short_help" : "Execute a task on the cluster.",
            "long_help"  :
"""
Execute a task on the Mesos Cluster. A wrapper script over mesos-execute.
Arguments and Flag information same as mesos-execute.
"""
        },
        "ps" : {
            "arguments" : [],
            "flags" : {
                "--addr=Addr" :
                "IP and Port of Mesos Master [Default: "+config.MASTER_IP+"]"
                },
            "short_help" : "Display info for agents",
            "long_help"  :
"""
Displays framework and task related statistics regarding the mesos cluster.
Equivalent to mesos-ps.
"""
        },
        "cat" : {
            "arguments" : ["<framework-ID>", "<task-ID>", "<file>"],
            "flags" : {
                "--addr=Addr" :
                "IP and Port of Mesos Master [Default: "+config.MASTER_IP+"]"
                },
            "short_help" : "Display file within task sandbox",
            "long_help"  :
"""
Displays contents of a file within a task sandbox.
Equivalent to mesos-cat
"""
        }
    }


    def __setup__(self, command, argv):
        pass

    def __autocomplete__(self, command, current_word, argv):
        return []

    #Helper to hit the specified endpoint and return json results
    def hit_endpoint(self,addr,endpoint):
        try:
            http_response = ( urllib2.urlopen("http://"+addr+endpoint)
                                             .read().decode('utf-8') )
        except socket_error as e:
            print("Cannot establish connection with Agent/Master")
            sys.exit(1)

        return json.loads(http_response)

    def execute(self,argv):
        subprocess.call(["mesos-execute"] + argv["<args>"])

    # Helper for formatting the CPU column for a task.
    def cpus(self, task, statistics):
        if statistics is None:
            return ""

        framework_id = task['framework_id']
        executor_id = task['executor_id']
        # An executorless task has an empty executor ID in the master but
        # uses the same executor ID as task ID in the slave.
        if executor_id == '':
            executor_id = task['id']

        cpus_limit = None
        for entry in statistics:
            if (entry['framework_id'] == framework_id and
                entry['executor_id'] == executor_id):
                cpus_limit = entry['statistics'].get('cpus_limit', None)
                break

        if cpus_limit is not None:
            return str(cpus_limit)

        return ""

    # Helper for formatting the MEM column for a task.
    def mem(self, task, statistics):
        if statistics is None:
            return ""

        framework_id = task['framework_id']
        executor_id = task['executor_id']
        # An executorless task has an empty executor ID in the master but
        # uses the same executor ID as task ID in the slave.
        if executor_id == '':
            executor_id = task['id']

        mem_rss_bytes = None
        mem_limit_bytes = None
        for entry in statistics:
            if (entry['framework_id'] == framework_id and
                entry['executor_id'] == executor_id):
                mem_rss_bytes = entry['statistics'].get('mem_rss_bytes', None)
                mem_limit_bytes = entry['statistics'].get('mem_limit_bytes'
                        , None)
                break

        if mem_rss_bytes is not None and mem_limit_bytes is not None:
            MB = 1024.0 * 1024.0
            return ( '{usage}/{limit}'
                    .format(usage = data_size(mem_rss_bytes, "%.1f"),
                            limit = data_size(mem_limit_bytes, "%.1f")) )

        return ""

    def data_size(self, bytes, format):
        # Ensure bytes is treated as floating point for the math below.
        bytes = float(bytes)
        if bytes < 1024:
            return (format % bytes) + ' B'
        elif bytes < (1024 * 1024):
            return (format % (bytes / 1024)) + ' KB'
        elif bytes < (1024 * 1024 * 1024):
            return (format % (bytes / (1024 * 1024))) + ' MB'
        else:
            return (format % (bytes / (1024 * 1024 * 1024))) + ' GB'

    # Helper for formatting the TIME column for a task.
    def time(self, task, statistics):
        if statistics is None:
            return

        framework_id = task['framework_id']
        executor_id = task['executor_id']
        # An executorless task has an empty executor ID in the master but
        # uses the same executor ID as task ID in the slave.
        if executor_id == '':
            executor_id = task['id']

        cpus_time_secs = None
        cpus_system_time_secs = None
        cpus_user_time_secs = None
        for entry in statistics:
            if ( (entry['framework_id'] == framework_id and
                entry['executor_id'] == executor_id) ):
                cpus_system_time_secs = ( entry['statistics']
                        .get('cpus_system_time_secs', None) )
                cpus_user_time_secs = ( entry['statistics']
                        .get('cpus_user_time_secs', None) )
                break

        if ( cpus_system_time_secs is not None
                and cpus_user_time_secs is not None ):
            return (datetime.datetime
                    .utcfromtimestamp(cpus_system_time_secs
                            + cpus_user_time_secs)
                    .strftime('%H:%M:%S.%f'))

        return ""

    def ps(self,argv):
        state = self.hit_endpoint(argv["--addr"], "/state")
        # Collect all the active frameworks and tasks by agent ID.
        active = {}
        for framework in state['frameworks']:
            for task in framework['tasks']:
                if task['slave_id'] not in active.keys():
                    active[task['slave_id']] = []
                active[task['slave_id']].append((framework, task))

        table = Table(['USER','FRAMEWORK','TASK','AGENT','MEM','TIME',
                        'CPU (allocated)'])

        # Grab all the agents with active tasks.
        agents = []
        for agent in state['slaves']:
            if agent['id'] in active:
                agents.append(agent)
        # Go through each agents and create the table
        # We use helper functions defined above for format help
        for agent in agents:
            statistics = self.hit_endpoint(agent["pid"].split("@")[1],
                                            "/monitor/statistics")
            if statistics is None:
                print("Could not get statistics from agent at : "
                        + agent["pid"].split("@")[1])

            for framework, task in active[agent['id']]:
                row = [framework['user'], framework['name'], task['name'],
                        agent['hostname'],
                    self.mem(task,statistics), self.time(task, statistics),
                    self.cpus(task, statistics)]
                table.add_row(row)

        print (table.to_string())

    def read(self, agent, task, file):
        framework_id = task['framework_id']
        executor_id = task['executor_id']
        # An executorless task has an empty executor ID in the master but
        # uses the same executor ID as task ID in the slave.
        if executor_id == '':
            executor_id = task['id']

        # Get 'state' json  to determine the executor directory.
        state = self.hit_endpoint(agent['pid'].split('@')[1],"/state")
        directory = None
        for framework in itertools.chain(state['frameworks'],
                                         state['completed_frameworks']):
            if framework['id'] == framework_id:
                for executor in itertools.chain(framework['executors'],
                                            framework['completed_executors']):
                    if executor['id'] == executor_id:
                        directory = executor['directory']
                        break

        if directory is None:
            print ('File not found')

        path = os.path.join(directory, file)
        # Determine the current length of the file.
        try:
            result = self.hit_endpoint(
                agent['pid'].split('@')[1],
                '/files/read?path='+path+'&offset=-1')
        except HTTPError as error:
            if error.code == 404:
                print ('No such file or directory')
            else:
                print ('Failed to determine length of file')

        length = result['offset']
        # Start streaming "pages" up to length.
        PAGE_LENGTH = 1024
        offset = 0
        while True:
            try:
                result = self.hit_endpoint(
                    agent['pid'].split('@')[1],
                    '/files/read?path='+path
                    +'&offset='+str(offset)
                    +'&length='+str(PAGE_LENGTH))
                offset += len(result['data'])
                yield result['data']
                if offset == length:
                    return
            except:
                print('Failed to read file from agent')


    def cat(self,argv):
        # Get the master's state.
        state = self.hit_endpoint(argv["--addr"], "/state")
        if state is None:
            print ("Could not connect to Master")
            return

        # Build a dict from agent ID to agents.
        agents = {}
        for agent in state['slaves']:
            agents[agent['id']] = agent

        def cat(agent, task):
            for data in self.read(agent, task, argv["<file>"]):
                sys.stdout.write(data)

        for framework in itertools.chain(state['frameworks'],
                                         state['completed_frameworks']):
            if framework['id'] == argv["<framework-ID>"]:
                for task in itertools.chain(framework['tasks'],
                                            framework['completed_tasks']):
                    if (task['id'] == argv["<task-ID>"]):
                        cat(agents[task['slave_id']], task)
                        sys.exit(0)

        print('No task found!')







