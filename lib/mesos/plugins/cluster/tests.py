import os
import sys
import subprocess
import StringIO
import time
import unittest

import main
from mesos.plugins.daemon.main import Daemon
from mesos.util import hit_endpoint

from multiprocessing import Process

class Test_B_ClusterPlugin(unittest.TestCase):
    # Some variables we need to be passed between test cases
    exec_info = None
    exec_process = None
    agent_state = None

    # We use this setup to initialize a previously tested Mesos Daemon.
    # Please note that this daemon will be used for this test and all
    # tests afterwards. If the user runs the test as root, we need a
    # different set of agent flags and execute test flags 
    # to meanigfully test some root only commands.
    @classmethod
    def setUpClass(cls):
        # We sleep here to let the os free up previous daemon test's 
        # port usage
        time.sleep(2)
        daemon = Daemon(None)
        # Starts a daemon process for testing.
        daemon_process = Process(target=daemon.start,
                                 args=(None,))
        daemon_process.start()
        # Spawn a master and agent node process in daemon. None flags will
        # cause them to run with a default set of flags
        spawn_msg = {"--master" : True, "--agent" : True,
                    "--master_flags" : None, "--agent_flags" : None}
        if os.geteuid() == 0:
            spawn_msg["--agent_flags"] = ("--master=127.0.0.1:5050 "
                                          "--work_dir=/tmp/sudo_agent_daemon "
              "--isolation=docker/runtime,filesystem/linux,namespaces/pid "
                                          "--image_providers=docker")

        daemon.spawn(spawn_msg)
        # Give some time for master/agent to setup
        time.sleep(2)

    # Returns stdout output of a given function
    def __get_output(self, run, argv):
        stdout = sys.stdout
        sys.stdout = StringIO.StringIO()
        try:
            run(argv)
        except Exception as exception:
            # Need to make sure we fix stdout in case something goes wrong
            sys.stdout = stdout
            raise Exception(str(exception))

        sys.stdout.seek(0)
        output = sys.stdout.read().strip()
        sys.stdout = stdout
        return output

    # We need this test to run first because all subsequent tests depend on it
    def test_a_execute(self):

        flags = ["--master=127.0.0.1:5050","--name=cluster-test",
                           "--command='/bin/bash'"]

        Test_B_ClusterPlugin.exec_process = \
                        subprocess.Popen(("exec mesos-execute {flags}"
                                           " > /dev/null 2>&1 ")
                                        .format(flags=' '.join(flags)),
                                        shell=True)

        # Let execute register and submit task on cluster
        time.sleep(10)
        # We'll hit the agent /containers endpoint to acheive several purposes:
        # 1) To find out whether mesos-execute worked and launched a container
        # 2) To store information that cluster ps can verify against
        try:
            exec_info = hit_endpoint('127.0.0.1:5051','/containers')
        except Exception as exception:
            self.fail("Could not get /containers from agent: {error}"
                                    .format(error=exception))
        self.assertEqual(len(exec_info), 1)
        Test_B_ClusterPlugin.exec_info = exec_info


    def test_cat(self):
        cluster = main.Cluster(None)
        # We need the agent id from its /state id as its usefull for assertion
        try:
            agent_state = hit_endpoint('127.0.0.1:5051','/state')
        except Exception as exception:
            self.fail("Could not get agent state info: {error}"
                                    .format(error=exception))

        # We read the stout file from the fs and compare with cat output
        exec_info = Test_B_ClusterPlugin.exec_info
        root_dir = 'agent_daemon'
        if os.geteuid() == 0:
            root_dir = 'sudo_agent_daemon'
        path_stdout = ('/tmp/{_dir}/slaves/{agent_id}/frameworks'
                        '/{frame_id}/executors/{exec_id}/runs/{cont_id}/stdout'
                        .format(_dir=root_dir,
                                agent_id=agent_state["id"],
                                frame_id=exec_info[0]["framework_id"],
                                exec_id=exec_info[0]["executor_id"],
                                cont_id=exec_info[0]["container_id"]))
        real_output = ""
        try:
            with open(path_stdout, 'r') as f:
                real_output = f.read()
        except Exception as exception:
            self.fail("Could not open stdout file: {error}"
                                  .format(error=exception))

        test_output = ""
        cluster_argv={"--addr" : "127.0.0.1:5050",
                      "<framework-ID>" : exec_info[0]["framework_id"],
                      "<task-ID>" : exec_info[0]["executor_id"],
                      "<file>" : "stdout"}

        try:
            test_output = self.__get_output(cluster.cat,cluster_argv)
        except Exception as exception:
            self.fail("Could not cat file with cluster cat: {error}"
                                            .format(error=exception))

        self.assertEqual(test_output, real_output.strip())

    def test_ps(self):
        cluster = main.Cluster(None)
        # We need the /state endpoint as its usefull for assertion
        try:
            agent_state = hit_endpoint('127.0.0.1:5051','/state')
        except Exception as exception:
            self.fail("Could not get agent state info: {error}"
                                    .format(error=exception))

        test_output = ""
        cluster_argv={"--addr" : "127.0.0.1:5050" }
        try:
            test_output = self.__get_output(cluster.ps,cluster_argv)
        except Exception as exception:
            self.fail("Could not perform cluster ps: {error}"
                                        .format(error=exception))
        # Table should have only two entries
        ps_table = test_output.split('\n')
        self.assertEqual(len(ps_table), 2)
        # Now we check if entries are correct
        entries = ps_table[1].split()

