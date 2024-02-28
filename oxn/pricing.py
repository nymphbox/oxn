"""
Module to price a synthetic dataset produced by an observability experiment

The price of a dataset is defined as the expended resources during an experiment
multiplied by the price of the resource per unit resource. As resources, we
use memory utilization and CPU utilization. We get these numbers from the docker daemon of the host machine,
more specifically from the docker stats sub-command.

"""
import pytz
import datetime
import logging
import dateutil.parser

from typing import List, Optional
from collections import defaultdict

import psutil
from docker import DockerClient
from docker.models.containers import Container

logger = logging.Logger(__name__)


class Accountant:
    def __init__(
        self, client: DockerClient, process: psutil.Process, container_names=None
    ):
        self.oxn_process: psutil.Process = process
        """Psutil class to gather stats for the oxn process"""
        self.data: dict = defaultdict(list)
        """Dict of lists to store data between reads"""
        self.consolidated_data: Optional[dict] = {}
        """The consolidated resource usage data after all reads"""
        self.client = client
        """A reference to a docker client"""
        self.container_names = container_names
        """A list of container names to read"""

    def containers(self) -> List[Container]:
        return self.client.containers.list()

    @staticmethod
    def total_cpu_usage(stats_dict) -> int:
        """Return the total cpu usage in seconds"""
        nanoseconds = stats_dict["cpu_stats"]["cpu_usage"]["total_usage"]
        return nanoseconds / 10**9

    @staticmethod
    def number_of_cpus(stats_dict) -> int:
        return stats_dict["cpu_stats"]["online_cpus"]

    @staticmethod
    def timestamp(stats_dict) -> datetime.datetime:
        """Return the read timestamp for stats_dict converted to a python datetime"""
        ts = stats_dict["read"]
        return dateutil.parser.parse(ts)

    def read_container_stats(
        self, container_name: str, container_id: str, container_stats: dict
    ):
        """
        Read stats for a single container.

        CPU Usage is in nanoseconds on Linux

        """
        values = {
            "container_id": container_id,
            "container_name": container_name,
            "total_cpu_usage": self.total_cpu_usage(container_stats),
            "number_of_cpus": self.number_of_cpus(container_stats),
            "timestamp": self.timestamp(container_stats),
        }
        self.data[container_name].append(values)

    def read_all_containers(self):
        """Read docker stats for all containers"""
        for container in self.containers():
            if container.name in self.container_names:
                self.read_container_stats(
                    container_name=container.name,
                    container_id=container.id,
                    container_stats=container.stats(stream=False),
                )

    def consolidate(self):
        """Calculate experiment resource expenditure from two reads of docker stats"""
        consolidated = {}
        for container_id, value_list in self.data.items():
            try:
                first_read, second_read = value_list
                # consolidate the two reads
                consolidated[container_id] = {
                    "container_name": first_read["container_name"],
                    "total_cpu_usage": second_read["total_cpu_usage"]
                    - first_read["total_cpu_usage"],
                    "number_of_cpus": first_read["number_of_cpus"],
                }
            except (ValueError, KeyError):
                logger.error("Could not read twice from docker stats")
        self.consolidated_data = consolidated

    def clear(self):
        """Clear the stats"""
        self.data = {}
        self.consolidated_data = defaultdict(list)

    def read_oxn(self):
        """Read resource expenditure data for the process running oxn"""
        with self.oxn_process.oneshot():
            total = 0
            time_in_seconds = self.oxn_process.cpu_times()
            total += time_in_seconds.user
            total += time_in_seconds.system
            total += time_in_seconds.children_user
            total += time_in_seconds.children_system
            values = {
                "timestamp": datetime.datetime.now(pytz.utc),
                "container_id": self.oxn_process.pid,
                "container_name": "oxn",
                "total_cpu_usage": total,
                "number_of_cpus": psutil.cpu_count(),
            }
            self.data["oxn"].append(values)
