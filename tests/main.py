#!.virtualenv/bin/python
import unittest

from mesos.plugins.daemon.tests import Test_A_DaemonPlugin
from mesos.plugins.cluster.tests import Test_B_ClusterPlugin
from mesos.plugins.agent.tests import Test_C_AgentPlugin
from mesos.plugins.container.tests import Test_D_ContainerPlugin

if __name__ == '__main__':
    unittest.main(verbosity=2)
