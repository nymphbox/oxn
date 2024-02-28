import unittest
import yaml

from oxn.orchestration import DockerComposeOrchestrator
from oxn.tests.unit.spec_mocks import experiment_spec_mock


class OrchestrationTest(unittest.TestCase):
    spec = experiment_spec_mock
    loaded_spec = yaml.safe_load(spec)

    def setUp(self) -> None:
        self.orc = DockerComposeOrchestrator(experiment_config=self.loaded_spec)

    def tearDown(self) -> None:
        self.orc.docker_client.close()

    def test_it_reads_the_env_section(self):
        self.assertTrue(self.orc.docker_compose_path)

    def test_it_reads_service_names(self):
        self.assertTrue(self.orc.docker_service_names)

    def test_it_includes_services(self):
        self.assertTrue(self.orc.include)

    def test_it_excludes_services(self):
        self.assertTrue(self.orc.exclude)

    def test_it_has_correct_include_exclude_logic(self):
        excluded_set = self.orc.exclude
        included_set = self.orc.include

        for service in excluded_set:
            self.assertFalse(service in self.orc.sue_service_names)

        for service in included_set:
            self.assertTrue(service in self.orc.sue_service_names)

    def test_it_initializes_the_client(self):
        self.assertTrue(self.orc.compose_client)

    def test_it_validates_sue(self):
        self.assertFalse(self.orc.messages)
