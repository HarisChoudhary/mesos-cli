import sys
import StringIO
import unittest

import main

from mesos.util import hit_endpoint

class Test_C_AgentPlugin(unittest.TestCase):

    
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

    def test_ping(self):
        agent_plugin = main.Agent(None)
        ping_argv = {"--addr" : "127.0.0.1:5051"}
        output = ""
        try:
            output = self.__get_output(agent_plugin.ping, ping_argv)
        except Exception as exception:
            self.fail("Could not ping agent node: {error}"
                                    .format(error=exception))

        self.assertEqual("Agent Healthy!", output)

    def test_state(self):
        # We get the entire agent state info to check out parsing againt
        try:
            agent_state = hit_endpoint('127.0.0.1:5051','/state')
        except Exception as exception:
            self.fail("Could not get state from agent node: {error}"
                                    .format(error=exception))

        agent_plugin = main.Agent(None)
        # Now we proced to check if the fields parsed are correct
        agent_argv = {"--addr" : "127.0.0.1:5051",
                      "<field>" : ["master_hostname"]}
        test_response = ""
        try:
            test_response = self.__get_output(agent_plugin.state,agent_argv)
        except Exception as exception:
            self.fail("Could not get master_hostname from agent node: {error}"
                                    .format(error=exception))

        self.assertEqual(test_response[1:-1],agent_state["master_hostname"])
        agent_argv["<field>"] = ["flags.port"]
        try:
            test_response = self.__get_output(agent_plugin.state,agent_argv)
        except Exception as exception:
            self.fail("Could not get flags.port from agent node: {error}"
                                    .format(error=exception))

            self.assertEqual(test_response[1:-1],agent_state["flags"]["port"])

