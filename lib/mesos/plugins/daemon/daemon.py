import os
import sys
import subprocess
import time

from multiprocessing.connection import Listener, Client
from signal import SIGTERM

from mesos.exceptions import CLIException

class MesosDaemon:
    def __init__(self, port, stdin='/dev/null', stdout='/dev/null'
                                              , stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.port = port
        self.Master = None
        self.Agents = []

    def daemonize(self):
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
               sys.exit(0)
        except Exception as exception:
            raise CLIException ("Fork #1 failed: {error}"
                                .format(error=exception))

        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)
        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent
                sys.exit(0)
        except Exception as exception:
            raise CLIException ("Fork #2 failed: {error}"
                                .format(error=exception))

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

    def start(self):
        # Check for port to see if the daemon already runs
        try:
            self.listener = Listener(('localhost',self.port))
        except Exception as e:
            raise CLIException ("Mesos Daemon already seems to be running...")

        # Start the daemon
        self.daemonize()
        # Once we're done handling all process related things,
        # Run the actual daemon work
        self.run()

    def stop(self):
        try:
            conn = Client(('localhost',self.port))
        except Exception as e:
            raise CLIException ("No Mesos Daemon seems to be running")

        kill_msg = {"command":["kill"]}
        conn.send(kill_msg)
        conn.close()

    def restart(self):
        self.stop()
        self.start()

    def run_agent(self, msg):
        my_env = os.environ.copy()
        my_env["LIBPROCESS_NUM_WORKER_THREADS"] = '1'
        agent_process = subprocess.Popen( "exec mesos-agent "
                                            + msg["agent_flags"],
                                            shell=True, env=my_env)
        self.Agents.append(agent_process)

    def kill_agent(self):
        if len(self.Agents) != 0:
            agent_process = self.Agents.pop()
            agent_process.kill()
            agent_process.wait()

    def run_master(self, msg):
        if self.Master is not None:
            return
        my_env = os.environ.copy()
        my_env["LIBPROCESS_NUM_WORKER_THREADS"] = '1'
        master_process = subprocess.Popen( "exec mesos-master "
                                            + msg["master_flags"],
                                            shell=True, env=my_env)
        self.Master = master_process

    def kill_master(self):
        if self.Master is not None:
            self.Master.kill()
            self.Master.wait()
            self.Master = None

    def get_functions(self):
        functions = {}
        functions['run_agent'] = (self.run_agent, True)
        functions['run_master'] = (self.run_master, True)
        functions['kill_master'] = (self.kill_master, False)
        functions['kill_agent'] = (self.kill_agent, False)
        return functions

    def cleanup(self):
        self.kill_master()
        num_agents = len(self.Agents)
        for i in range(0,num_agents):
            self.kill_agent()

    def run(self):
        functions = self.get_functions()
        alive = True
        while alive:
            conn = self.listener.accept()
            msg = conn.recv()
            for command in msg['command']:
                if command in functions:
                    invoke = functions[command]
                    if invoke[1]:
                        invoke[0](msg)
                    else:
                        invoke[0]()
                elif command == 'ping':
                    conn.send('pong')
                elif command == 'kill':
                    alive = False
                    break
            conn.close()
        self.cleanup()
        self.listener.close()
