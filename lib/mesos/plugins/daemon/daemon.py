import sys, os, time, atexit, signal
import subprocess
from signal import SIGTERM 
from multiprocessing import Process, Manager, Value
from multiprocessing.connection import Listener, Client

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
        except OSError, e: 
            print ("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

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
        except OSError, e: 
            print ("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1) 

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
            print ("Mesos Daemon already seems to be running...")
        
        # Start the daemon
        self.daemonize()
        # Once we're done handling all process related things,
        # Run the actual daemon work
        self.run()

    def stop(self):
        try:
            conn = Client(('localhost',self.port))
        except Exception as e:
            print ("No Mesos Daemon seems to be running")

        kill_msg = {"command":["kill"]}
        conn.send(kill_msg)
        conn.close()

    def restart(self):
        self.stop()
        self.start()

    def run_agent(self):
        my_env = os.environ.copy()
        my_env["LIBPROCESS_NUM_WORKER_THREADS"] = '1'
        agent_process = subprocess.Popen( ("exec mesos-agent "
                                            "--work_dir=/tmp/agent_daemon "
                                            "--master=127.0.0.1:5050")
                                            ,shell=True, env=my_env)
        self.Agents.append(agent_process)

    def kill_agent(self):
        if len(self.Agents) != 0:
            agent_process = self.Agents.pop()
            agent_process.kill()
            agent_process.wait()

    def run_master(self):
        if self.Master is not None:
            return
        my_env = os.environ.copy()
        my_env["LIBPROCESS_NUM_WORKER_THREADS"] = '1'
        master_process = subprocess.Popen( ("exec mesos-master "
                                            "--work_dir=/tmp/master_daemon "
                                            "--ip=127.0.0.1")
                                            ,shell=True, env=my_env)
        self.Master = master_process

    def kill_master(self):
        if self.Master is not None:
            self.Master.kill()
            self.Master.wait()
            self.Master = None

    def get_functions(self):
        functions = {}
        functions['run_agent'] = self.run_agent
        functions['run_master'] = self.run_master
        functions['kill_master'] = self.kill_master
        functions['kill_agent'] = self.kill_agent
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
                    invoke()
                elif command == 'kill':
                    alive = False
                    conn.close()
                    break
        self.cleanup()
        self.listener.close()

