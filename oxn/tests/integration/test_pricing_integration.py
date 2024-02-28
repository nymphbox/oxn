import unittest
import docker
import psutil

from oxn.pricing import Accountant


class AccountantIntegrationTest(unittest.TestCase):
    client = docker.from_env()
    otelcol_container_name = "otel-col"

    def test_it_reads_stats(self):
        accountant = Accountant(
            client=self.client, container_names=["otel-col"], process=psutil.Process()
        )
        accountant.read_all_containers()
        accountant.read_oxn()
        self.assertTrue(accountant.data)
        accountant.read_all_containers()
        accountant.read_oxn()
        accountant.consolidate()
        self.assertTrue(accountant.consolidated_data)
