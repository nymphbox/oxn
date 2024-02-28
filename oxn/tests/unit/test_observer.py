import unittest
import yaml

from oxn.observer import Observer
from oxn.utils import utc_timestamp
from oxn.tests.unit.spec_mocks import experiment_spec_mock


class ObserverTest(unittest.TestCase):
    loaded = yaml.safe_load(experiment_spec_mock)

    def setUp(self) -> None:
        self.now = utc_timestamp()
        self.five_min_ago = self.now - 5 * 60
        self.observer = Observer(
            config=self.loaded,
            experiment_start=self.five_min_ago,
            experiment_end=self.now,
        )
        self.observer.initialize_variables()

    def test_it_builds_response_variables(self):
        self.assertTrue(self.observer.variables())

    def test_it_returns_metric_rvars(self):
        variables = self.observer.get_metric_variables()
        self.assertTrue(variables)

    def test_it_returns_trace_rvars(self):
        variables = self.observer.get_trace_variables()
        self.assertTrue(variables)

    def test_it_calculates_max_ttw(self):
        ttw = self.observer.time_to_wait_right()
        self.assertTrue(ttw == 2 * 60)

    def test_it_calculates_max_left_window(self):
        max_left_window = self.observer.time_to_wait_left()
        self.assertTrue(max_left_window == float(5 * 60))

    def test_response_var_has_type(self):
        some_variable = self.observer.get_trace_variables()[0]
        self.assertTrue(some_variable.response_type)

    def test_response_var_has_short_id(self):
        some_variable = self.observer.get_trace_variables()[0]
        self.assertTrue(some_variable.short_id)
