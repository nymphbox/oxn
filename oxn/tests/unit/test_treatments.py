import unittest
from io import StringIO
from unittest import mock
from unittest.mock import patch


from oxn.treatments import (
    PrometheusIntervalTreatment,
    TailSamplingTreatment,
    StressTreatment,
)
from oxn.errors import OxnException


class PrometheusScrapeTest(unittest.TestCase):
    valid_config = {
        "prometheus_config": "mock-prometheus-config.yaml",
        "interval": "1s",
    }

    invalid_config = {
        "prometheus_config": "not-an-existing.file.yaml",
        "interval": "abc",
    }
    mock_prometheus_config = """
    global:
      evaluation_interval: 30s
      scrape_interval: 30s
    scrape_configs:
    - job_name: otel
      static_configs:
      - targets:
        - otelcol:9464
    - job_name: otel-collector
      static_configs:
      - targets:
        - otelcol:8888
    - job_name: docker
      static_configs:
      - targets:
        - docker.for.mac.localhost:9323
    """

    @patch("requests.post")
    @patch("os.path.isfile")
    @patch("builtins.open")
    def test_it_accepts_valid_config(self, mock_open, mock_isfile, mock_post):
        mock_isfile.return_value = True
        mock_open.return_value = StringIO(self.mock_prometheus_config)
        treatment = PrometheusIntervalTreatment(
            config=self.valid_config, name="prometheus_treatment"
        )
        self.assertTrue(treatment)
        self.assertTrue(isinstance(treatment, PrometheusIntervalTreatment))
        self.assertTrue(treatment.config.get("prometheus_yaml"))
        self.assertTrue(treatment.config.get("original_interval"))

    @patch("requests.post")
    def test_it_throws_on_invalid_config(self, mock_post):
        with self.assertRaises(OxnException) as context:
            PrometheusIntervalTreatment(
                config=self.invalid_config, name="prometheus_treatment"
            )
        self.assertTrue(context.exception.explanation)

    @patch("requests.post")
    @patch("os.path.isfile")
    @patch("builtins.open")
    def test_it_has_deferred_clean(self, mock_open, mock_isfile, mock_post):
        mock_isfile.return_value = True
        mock_open.return_value = StringIO(self.mock_prometheus_config)
        treatment = PrometheusIntervalTreatment(
            config=self.valid_config,
            name="prometheus_treatment",
        )
        self.assertTrue(treatment.clean.defer_cleanup)


class TailSamplingTreatmentTest(unittest.TestCase):
    valid_config = {
        "otelcol_extras": "mock-otelcol-extras.yaml",
        "policy_name": "my_policy_name",
        "decision_wait": "1s",
        "num_traces": 50000,
        "expected_new_traces": 5,
        "type": "probabilistic",
        "policy_params": {
            "percentage": 50,
        },
    }

    @mock.patch("builtins.open")
    def test_it_accepts_valid_config(self, mock_open):
        mock_open.return_value = StringIO("foo")
        treatment = TailSamplingTreatment(
            config=self.valid_config, name="test_tail_sampling"
        )

        self.assertTrue(treatment)
        self.assertTrue(isinstance(treatment, TailSamplingTreatment))
        self.assertTrue(treatment.config.get("otelcol_extras_yaml"))

    @mock.patch("builtins.open")
    def test_it_has_deferred_clean(self, mock_open):
        mock_open.return_value = StringIO("bar")
        treatment = TailSamplingTreatment(
            config=self.valid_config, name="test_tail_sampling"
        )
        self.assertTrue(treatment.clean.defer_cleanup)


class StressTreatmentTest(unittest.TestCase):
    valid_config = {
        "service_name": "recommendation-service",
        "duration": "30s",
        "stressors": {
            "cpu": 4,
            "dev": 2,
            "dir": 1,
            "epoll": 10,
        },
    }

    def test_it_reads_config(self):
        t = StressTreatment(name="example_stress_treatment", config=self.valid_config)
        self.assertTrue(t)

    def test_it_produces_correct_stressor_format(self):
        t = StressTreatment(name="example_stress_treatment", config=self.valid_config)
        self.assertTrue([key.startswith("--") for key in t.stressors.keys()])

    def test_it_builds_correct_command(self):
        t = StressTreatment(name="example_stress_treatment", config=self.valid_config)
        expected = [
            "stress-ng",
            "--cpu",
            "4",
            "--dev",
            "2",
            "--dir",
            "1",
            "--epoll",
            "10",
            "--timeout",
            "30s",
        ]
        self.assertTrue(t._build_command() == expected)
