import os
import sys
import socket
import StringIO
import time
import unittest
import urllib2
import socket
from multiprocessing import Process
from contextlib import closing

import main
import mesos.config as config

from mesos.util import hit_endpoint
from mesos.exceptions import CLIException

class Test_A_DaemonPlugin(unittest.TestCase):

    # We have one test case here for all the commands and not a seperate one
    # per command. This is because each command builds off of the previous.
    def test_daemon(self):
        daemon = main.Daemon(None)
        # Starts a daemon process for testing.
        try:
            daemon_process = Process(target=daemon.start,
                                     args=(None,))
            daemon_process.start()
        except Exception as exception:
            self.fail("Could not start daemon for testing: {error}"
                                          .format(error=exception))
        # Spawn a master and agent node process in daemon.
        spawn_msg = {"--master" : True, "--agent" : True,
                    "--master_flags" : None, "--agent_flags" : None}
        if os.geteuid() == 0:
            spawn_msg["--agent_flags"] = ("--master=127.0.0.1:5050 "
                                          "--work_dir=/tmp/sudo_agent_daemon")

        try:
            daemon.spawn(spawn_msg)
        except Exception as exception:
            self.fail("Could not spawn master/agent on daemon: {error}"
                                              .format(error=exception))

        # Give some time for master/agent to setup
        time.sleep(2)
        # Assert if master is running and healthy
        try:
            httpResponseCode = ( urllib2.urlopen("http://127.0.0.1:5050/health")
                                                               .getcode() )
        except Exception as exception:
            self.fail("Could not contact master node: {error}"
                                    .format(error=exception))

        self.assertEqual(httpResponseCode, 200)
        try:
            agents = hit_endpoint('127.0.0.1:5050','/slaves')
        except Exception as exception:
            self.fail("Could not get list of agents from master: {error}"
                                                .format(error=exception))

        # Check we have one agent and that it is active.
        self.assertEqual(len(agents['slaves']), 1)
        self.assertTrue(agents['slaves'][0]['active'])
        # Need some time here for cluster to service previous requests
        time.sleep(2)
        # Kill off master and agent
        kill_msg = {"--master" : True, "--agent" : True}
        try:
            daemon.kill(kill_msg)
        except Exception as exception:
            self.fail("Could not kill master/agent on daemon: {error}"
                                              .format(error=exception))

        with self.assertRaises(CLIException) as exception:
            hit_endpoint("127.0.0.1:5050","/state")
        # Check to make sure exception was because we couldnt open url
        self.assertTrue('Could not open' in str(exception.exception))
        # Stop the daemon and confirm the port was released
        try:
            daemon.stop(config.DAEMON_PORT)
        except Exception as exception:
            self.fail("Could not stop daemon: {error}".format(error=exception))
        '''
        # Check if the socket was released when daemon was stopped
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            result = sock.connect_ex(('127.0.0.1',config.DAEMON_PORT))
            self.assertEqual(result,0)
        '''
