import time
import unittest

import requests
from requests import Session
from unittest.mock import patch

from oxn.errors import PrometheusException
from oxn.prometheus import Prometheus

import warnings
warnings.simplefilter("ignore", ResourceWarning)


class PrometheusTests(unittest.TestCase):

    def setUp(self) -> None:
        self.api = Prometheus()

    def tearDown(self) -> None:
        self.api.session.close()

    @patch.object(Session, "get")
    def test_all_metrics_endpoint(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": "mocked_data"}
        response = self.api.metrics()
        self.assertTrue(response == {"data": "mocked_data"})

    @patch.object(Session, "get")
    def test_metadata_endpoint(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": "mocked_data"}
        some_metric_metadata = self.api.metric_metadata(metric="")
        self.assertTrue(some_metric_metadata == {"data": "mocked_data"})

    @patch.object(Session, "get")
    def test_it_fetches_target_metadata(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": "mocked_data"}
        metadata = self.api.target_metadata(match_target="some_target", metric="")
        self.assertTrue(metadata == {"data": "mocked_data"})

    @patch.object(Session, "get")
    def test_it_fetches_labels(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": "mocked_data"}
        labels = self.api.labels()
        self.assertTrue(labels == {"data": "mocked_data"})

    @patch.object(Session, "get")
    def test_it_fetches_exported_job(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": "mocked_data"}
        exporter = self.api.label_values(label="server")
        self.assertTrue(exporter == {"data": "mocked_data"})

    @patch.object(Session, "get")
    def test_it_throws_on_http_error_code(self, mock_get):
        mock_get.side_effect = requests.HTTPError
        with self.assertRaises(PrometheusException):
            self.api.labels()

    @patch.object(Session, "get")
    def test_it_performs_range_queries(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": "mock_data"}
        now = time.time()
        a_minute_ago = now - 1 * 60
        metric_name = "otelcol_exporter_sent_spans"
        query = self.api.build_query(metric_name=metric_name)
        result = self.api.range_query(
            query=query, start=a_minute_ago, end=now, step="5s"
        )
        self.assertTrue(result == {"data": "mock_data"})
