import unittest
import yaml

from oxn.tests.unit.spec_mocks import experiment_spec_mock
from oxn.validation import SemanticValidator


class ValidationTests(unittest.TestCase):
    """
    Test semantic validation of experiment specifications
    """

    spec = yaml.safe_load(experiment_spec_mock)

    def setUp(self) -> None:
        self.validator = SemanticValidator(experiment_spec=self.spec)

    def tearDown(self) -> None:
        self.validator.prometheus.session.close()
        self.validator.jaeger.session.close()

    def test_it_fetches_prometheus_metric_names(self):
        self.assertTrue(self.validator.metric_names)

    def test_it_fetches_prometheus_label_names(self):
        self.assertTrue(self.validator.label_names)

    def test_it_fetches_prometheus_label_values(self):
        self.assertTrue(self.validator.label_values)

    def test_it_does_not_validate_wrong_name(self):
        mock = {
            "foobar": {
                "metric_name": "baz",
                "type": "metric",
                "step": "1",
                "left_window": "2m",
                "right_window": "0m",
            }
        }
        self.validator.validate_response(response=mock)
        self.assertTrue(self.validator.messages)

    def test_it_does_not_validate_wrong_labels(self):
        mock = {
            "otelcol_exporter_sent_span": {
                "type": "metric",
                "metric_name": "foobar",
                "step": "1",
                "labels": {"foo": "bar"},
                "left_window": "2m",
                "right_window": "0m",
            }
        }
        self.assertFalse(
            self.validator.validate_metric_response_description(response=mock)
        )

    def test_it_fetches_service_names(self):
        self.validator._populate_service_names()
        self.assertTrue(self.validator)

    def test_it_validates_existing_service_name(self):
        mock = {
            "frontend_traces": {
                "type": "trace",
                "service_name": "frontend",
                "left_window": "2m",
                "right_window": "0m",
            }
        }
        self.validator.validate_response(response=mock)
        self.assertFalse(self.validator.messages)

    def test_it_does_not_validate_nonexisting_service_name(self):
        mock = {
            "foobar": {
                "type": "trace",
                "service_name": "barbaz",
                "left_window": "2m",
                "right_window": "0m",
            }
        }
        self.validator.validate_trace_response_description(response=mock)
        self.assertTrue(self.validator.messages)
