"""Wrapper around the internal Jaeger tracing API"""
from typing import Optional, Union

import requests
from requests.adapters import HTTPAdapter, Retry
import logging

from .errors import JaegerException

LOGGER = logging.getLogger(__name__)


# NOTE: jaeger timestamps wire format is microseconds since epoch in utc cf.
# https://github.com/jaegertracing/jaeger/pull/712


class Jaeger:
    """
    Wrapper around the undocumented Jaeger HTTP API.
    """

    def __init__(self):
        self.session = requests.Session()
        retries = Retry(
            total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
        )
        """Retry policy. Force retries on server errors"""
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        """Mount the retry adapter"""
        self.base_url = "http://localhost:8080/jaeger/ui/api/"
        """Jaeger base url"""
        self.endpoints = {
            "traces": "traces",
            "services": "services",
            "operations": "services/%s/operations",
            "dependencies": "dependencies",
            "trace": "traces/%s",
        }
        """Jaeger API endpoints"""

    def get_services(self) -> Union[list, None]:
        """Returns a list of all services"""
        endpoint = self.endpoints.get("services")
        url = self.base_url + endpoint
        try:
            response = self.session.get(
                url=url,
            )
            response.raise_for_status()
            response_json = response.json()
            try:
                return list(response_json["data"])
            except KeyError as error:
                LOGGER.error("Received invalid response from Jaeger")
                raise JaegerException from error
        except requests.exceptions.HTTPError as error:
            LOGGER.error(error)
            raise JaegerException from error
        except requests.exceptions.ConnectionError as error:
            LOGGER.error(f"Could not connect to jaeger at {url}")
            raise JaegerException from error

    def search_traces(
        self,
        start=None,
        end=None,
        limit=None,
        lookback=None,
        max_duration=None,
        min_duration=None,
        service_name="adservice",
    ) -> Optional[dict]:
        """Search Jaeger traces"""
        endpoint = self.base_url + self.endpoints.get("traces")
        params = {
            "start": start,
            "end": end,
            "lookback": lookback,
            "maxDuration": max_duration,
            "minDuration": min_duration,
            "service": service_name,
            "limit": limit,
        }
        try:
            response = self.session.get(url=endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            raise JaegerException(
                message=f"Error while talking to Jaeger at {endpoint}",
                explanation=error,
            )

    def get_service_operations(self, service="adservice") -> [dict, None]:
        """Get all service operations for a given service from Jaeger"""
        endpoint = self.base_url + self.endpoints.get("operations")
        endpoint = endpoint % service
        try:
            response = self.session.get(endpoint)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            raise JaegerException(
                message=f"Error while talking to Jaeger at {endpoint}",
                explanation=error,
            )

    def get_dependencies(self, end_timestamp=None, lookback=604800000) -> [dict, None]:
        """Get a dependency graph from Jaeger"""
        endpoint = self.base_url + self.endpoints.get("dependencies")
        params = {"endTs": end_timestamp, "lookback": lookback}
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            raise JaegerException(
                message=f"Error while talking to Jaeger at {endpoint}",
                explanation=error,
            )

    def get_trace_by_id(self, trace_id) -> [dict, None]:
        """Get a single Jaeger trace by a trace id"""
        endpoint = self.base_url + self.endpoints.get("trace") % trace_id
        try:
            response = self.session.get(endpoint)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            raise JaegerException(
                message=f"Error while talking to Jaeger at {endpoint}",
                explanation=error,
            )
