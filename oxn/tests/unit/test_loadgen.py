import unittest
import yaml

from locust.shape import LoadTestShape
from locust.user import User

from oxn.loadgen import LoadGenerator
from oxn.tests.unit.spec_mocks import experiment_spec_mock


class LoadGenerationTest(unittest.TestCase):
    spec = yaml.safe_load(experiment_spec_mock)

    def setUp(self) -> None:
        self.generator = LoadGenerator(config=self.spec)

    def test_it_initializes(self):
        self.assertTrue(self.generator.env)

    def test_it_returns_custom_load_shapes(self):
        load_test_shape = self.generator._shape_factory()
        self.assertTrue(load_test_shape, isinstance(load_test_shape, LoadTestShape))

    def test_it_returns_fast_http_user(self):
        fast_user_class = self.generator._locust_factory_random()
        self.assertTrue(issubclass(fast_user_class, User))

    def test_it_has_locust_tasks(self):
        self.assertTrue(self.generator.locust_tasks)

    def test_it_has_stages(self):
        self.assertTrue(self.generator.stages)

    def test_it_has_a_run_time(self):
        self.assertTrue(self.generator.run_time)
