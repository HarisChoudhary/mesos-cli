import os
import sys
import subprocess
import StringIO
import time
import unittest

import traceback

import main
from mesos.exceptions import CLIException
from mesos.plugins.daemon.main import Daemon
from mesos.util import hit_endpoint
from mesos.plugins.cluster.tests import Test_B_ClusterPlugin

from multiprocessing import Process, Manager

#Need to write test cases for container commands
class Test_D_ContainerPlugin(unittest.TestCase):

    # We use this teardown to stop the cluster daemon and kill the
    # mesos-execute instance that we have been using throughout the test
    @classmethod
    def tearDownClass(cls):
        daemon = Daemon(None)
        daemon.stop(None)
        Test_B_ClusterPlugin.exec_process.kill()

    # Returns stdout output of a given function
    def __get_output(self, run, argv, wait=None):
        stdout = sys.stdout
        sys.stdout = StringIO.StringIO()
        try:
            run(argv)
        except Exception as exception:
            # Need to make sure we fix stdout in case something goes wrong
            sys.stdout = stdout
            raise CLIException(str(exception))

        sys.stdout.seek(0)
        output = sys.stdout.read().strip()
        sys.stdout = stdout
        return output

    def __get_execute_output(self, argv, process_dict):
        container_plugin = main.Container(None)
        try:
            process_dict["output"]=container_plugin.execute(argv, True)
        except Exception as exception:
            raise CLIException("Error executing command in container: {error}"
                                                     .format(error=exception))
        return

    # Verify that this test is being run by a root user.
    def __verify_root(self):
        if os.geteuid() != 0:
            raise unittest.SkipTest("Must be be root for this test!")

    def test_ps(self):
        # Get container info from from agent to validate ps output
        try:
            container_info = hit_endpoint('127.0.0.1:5051','/containers')
        except Exception as exception:
            self.fail("Could not get /containers from agent node: {error}"
                                                .format(error=exception))

        container_plugin = main.Container(None)
        # Now we proced to check if the fields parsed are correct
        ps_argv = {"--addr" : "127.0.0.1:5051"}
        ps_response = ""
        try:
            ps_output = self.__get_output(container_plugin.ps,ps_argv)
        except Exception as exception:
            self.fail("Could not get ps output from agent node: {error}"
                                               .format(error=exception))

        # Make sure that the return response is a json list with 1 container
        self.assertEqual(type(container_info), list)
        self.assertEqual(len(container_info),1)
        # Make sure the ps output has only two lines: header and container info
        try:
            ps_output = ps_output.split('\n')
        except Exception as exception:
            self.fail("Could not split ps table: {error}"
                                    .format(error=exception))

        self.assertEqual(len(ps_output),2)
        try:
            ps_output = ps_output[1].split()
            self.assertEqual(ps_output[0], container_info[0]["container_id"])
            self.assertEqual(ps_output[1], container_info[0]["framework_id"])
            self.assertEqual(ps_output[2], container_info[0]["executor_id"])
        except Exception as exception:
            self.fail("Could not verify ps table info: {error}"
                                        .format(error=exception))


    def test_execute(self):
        self.__verify_root()
        # Get container id from from agent to execute command in
        try:
            container_info = hit_endpoint('127.0.0.1:5051','/containers')
            container_id = container_info[0]["container_id"]
        except Exception as exception:
            self.fail("Could not get container id from agent node: {error}"
                                                .format(error=exception))
        # Make sure the executor_id is present in the /containers endpoint 
        pid_exists = False
        if "executor_pid" in container_info[0]["status"]:
           pid_exists = True

        self.assertTrue(pid_exists)
        container_plugin = main.Container(None)
        # Check if we correctly enter container namespace
        execute_argv = {"--addr" : "127.0.0.1:5051",
                        "<container-id>" : container_id,
                        "<command>" : ["ps","-ax"]}

        manager = Manager()
        process_dict = manager.dict()
        process = Process(target=self.__get_execute_output,
                                    args=(execute_argv,process_dict,))
        try:
            process.start()
            process.join()
        except Exception as exception:
            self.fail("Error getting ps output: {error}"
                                .format(error=exception))

        ps_output = process_dict["output"].strip()
        self.assertEqual(len(ps_output.split('\n')), 5)

    # The test case for this is nearly identical to cluster ps
    def test_logs(self):
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

        # Get container id from from agent to execute command in
        try:
            container_info = hit_endpoint('127.0.0.1:5051','/containers')
            container_id = container_info[0]["container_id"]
        except Exception as exception:
            self.fail("Could not get container id from agent node: {error}"
                                                .format(error=exception))

        test_output = ""
        container_argv={"--addr" : "127.0.0.1:5051",
                        "<container-id>" : container_id,
                        "--no-stderr" : True,
                        "--no-stdout" : False}
        container_plugin = main.Container(None)
        try:
            test_output = self.__get_output(container_plugin.logs
                                                        ,container_argv)
        except Exception as exception:
            self.fail("Could not get logs of the container: {error}"
                                            .format(error=exception))
        self.assertEqual(test_output, real_output.strip())

    def test_top(self):
        self.__verify_root()

    def test_stats(self):
        pass

    def test_images(self):
        pass

