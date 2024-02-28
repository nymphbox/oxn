"""Wrapper around the Prometheus HTTP API"""
import logging
import requests
from requests.adapters import Retry, HTTPAdapter

from .errors import PrometheusException

logger = logging.getLogger(__name__)


# NOTE: prometheus wire timestamps are in milliseconds since unix epoch utc-aware


class Prometheus:
    def __init__(self):
        self.session = requests.Session()
        retries = Retry(
            total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
        )
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.base_url = "http://localhost:9090/api/v1/"
        self.endpoints = {
            "range_query": "query_range",
            "instant_query": "query",
            "targets": "targets",
            "labels": "labels",
            "metrics": "label/__name__/values",
            "label_values": "label/%s/values",
            "metric_metadata": "metadata",
            "target_metadata": "targets/metadata",
            "config": "status/config",
            "flags": "status/flags",
        }

    @staticmethod
    def build_query(metric_name, label_dict=None):
        """Build a query in the Prometheus Query Language format"""
        label_string = ""
        query_template = '%s="%s",'
        if label_dict:
            for k, v in label_dict.items():
                interpolated = query_template % (k, v)
                label_string += interpolated
            qry = metric_name + "{%s}" % label_string
        else:
            qry = metric_name
        return qry

    def target_metadata(
        self, match_target: str = None, metric: str = None, limit: int = None
    ):
        """Return metadata about metric with additional target information"""

        params = {
            "match_target": match_target,
            "metric": metric,
            "limit": limit,
        }
        url = self.base_url + self.endpoints.get("target_metadata")
        try:
            response = self.session.get(url=url, params=params)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.HTTPError) as requests_exception:
            raise PrometheusException(
                message=f"Error while talking to Prometheus at {url}",
                explanation=f"{requests_exception}",
            )

    def targets(self):
        """Return an overview of the current state of Prometheus target discovery"""
        url = self.base_url + self.endpoints.get("targets")
        try:
            response = self.session.get(url=url)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.HTTPError) as requests_exception:
            raise PrometheusException(
                message=f"Error while talking to Prometheus at {url}",
                explanation=f"{requests_exception}",
            )

    def labels(self, start=None, end=None, match=None):
        """Return label names"""
        params = {
            "start": start,
            "end": end,
            "match": match,
        }
        url = self.base_url + self.endpoints.get("labels")
        try:
            response = self.session.get(
                self.base_url + self.endpoints.get("labels"), params=params
            )
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.HTTPError) as requests_exception:
            raise PrometheusException(
                message=f"Error while talking to Prometheus at {url}",
                explanation=f"{requests_exception}",
            )

    def metrics(self):
        url = self.base_url + self.endpoints.get("metrics")
        try:
            response = self.session.get(url=url)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.HTTPError) as requests_exception:
            raise PrometheusException(
                message=f"Error while talking to Prometheus at {url}",
                explanation=f"{requests_exception}",
            )

    def label_values(self, label=None, start=None, end=None, match=None):
        endpoint = self.endpoints.get("label_values") % label
        url = self.base_url + endpoint

        params = {
            "start": start,
            "end": end,
            "match": match,
        }
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.HTTPError) as requests_exception:
            raise PrometheusException(
                message=f"Error while talking to Prometheus at {url}",
                explanation=f"{requests_exception}",
            )

    def metric_metadata(self, metric=None, limit=None):
        url = self.base_url + self.endpoints.get("metric_metadata")
        params = {
            "metric": metric,
            "limit": limit,
        }
        try:
            response = self.session.get(url=url, params=params)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.HTTPError) as requests_exception:
            raise PrometheusException(
                message=f"Error while talking to Prometheus at {url}",
                explanation=f"{requests_exception}",
            )

    def config(self):
        url = self.base_url + self.endpoints.get("config")
        try:
            response = self.session.get(url=url)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.HTTPError) as requests_exception:
            raise PrometheusException(
                message=f"Error while talking to Prometheus at {url}",
                explanation=f"{requests_exception}",
            )

    def flags(self):
        url = self.base_url + self.endpoints.get("flags")
        try:
            response = self.session.get(url=url)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.HTTPError) as requests_exception:
            raise PrometheusException(
                message=f"Error while talking to Prometheus at {url}",
                explanation=f"{requests_exception}",
            )

    def instant_query(self, query, time=None, timeout=None):
        """Evaluate a Prometheus query instantly"""
        url = self.base_url + self.endpoints.get("instant_query")
        params = {
            "query": query,
            "time": time,
            "timeout": timeout,
        }
        try:
            response = self.session.get(url=url, params=params)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.HTTPError) as requests_exception:
            raise PrometheusException(
                message=f"Error while talking to Prometheus at {url}",
                explanation=f"{requests_exception}",
            )

    def range_query(self, query, start, end, step=None, timeout=None):
        """Evaluate a Prometheus query over a time range"""
        url = self.base_url + self.endpoints.get("range_query")
        params = {
            "query": query,
            "start": start,
            "end": end,
            "step": step,
            "timeout": timeout,
        }
        try:
            response = self.session.get(url=url, params=params)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.HTTPError) as requests_exception:
            raise PrometheusException(
                message=f"Error while talking to Prometheus at {url}",
                explanation=f"{requests_exception}",
            )
