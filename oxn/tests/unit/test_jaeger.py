import unittest
import warnings
from unittest.mock import patch

from requests import Session

from oxn.errors import JaegerException
from oxn.jaeger import Jaeger

warnings.simplefilter("ignore", ResourceWarning)


class JaegerTests(unittest.TestCase):

    def setUp(self) -> None:
        self.api = Jaeger()

    def tearDown(self) -> None:
        self.api.session.close()

    @patch.object(Session, "get")
    def test_services_endpoint(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": {"service_a"}}
        response = self.api.get_services()
        self.assertTrue(response == ["service_a"])

    @patch.object(Session, "get")
    def test_traces_endpoint(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": "mocked_data"}
        some_metric_metadata = self.api.search_traces()
        self.assertTrue(some_metric_metadata == {"data": "mocked_data"})

    @patch.object(Session, "get")
    def test_service_ops_endpoint(self, mock_get):
        mocked_data = {"data": "mocked_data"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mocked_data

        service_operations = self.api.get_service_operations()
        self.assertTrue(service_operations == mocked_data)

    @patch.object(Session, "get")
    def test_dependency_endpoint(self, mock_get):
        mocked_data = {"data": "mocked_data"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mocked_data

        service_operations = self.api.get_dependencies()
        self.assertTrue(service_operations == mocked_data)

    @patch.object(Session, "get")
    def test_trace_by_id_endpoint(self, mock_get):
        mocked_data = {"data": "mocked_data"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mocked_data

        service_operations = self.api.get_trace_by_id(trace_id="random_id")
        self.assertTrue(service_operations == mocked_data)

    def test_it_throws_on_error(self):
        with self.assertRaises(JaegerException) as context:
            self.api.get_trace_by_id(trace_id="some_trace_id")
            endpoint = self.api.endpoints.get("trace")
            self.assertTrue(
                context.exception == f"Error while talking to Jaeger at {endpoint}"
            )
