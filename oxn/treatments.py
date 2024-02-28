"""Treatment implementations"""
import logging
import os.path
import tempfile
import time
import re
from typing import Optional

import docker
import yaml
import requests
from docker.errors import NotFound as ContainerNotFound
from docker.errors import APIError as DockerAPIError

from python_on_whales import DockerClient

from oxn.utils import (
    time_string_to_seconds,
    validate_time_string,
    time_string_format_regex,
    add_env_variable, remove_env_variable, to_milliseconds,
)
from oxn.models.treatment import Treatment

logger = logging.getLogger(__name__)


class EmptyTreatment(Treatment):
    """
    Empty treatment to represent a simple observation of response variables
    """

    def clean(self) -> None:
        pass

    def _transform_params(self) -> None:
        relative_time_string = self.config.get("duration")
        relative_time_seconds = time_string_to_seconds(relative_time_string)
        self.config["duration_seconds"] = relative_time_seconds

    def _validate_params(self) -> bool:
        bools = []
        for key, value in self.params().items():
            if key in {"duration", } and key not in self.config:
                self.messages.append(f"Parameter {key} has to be supplied")
                bools.append(False)
            if key in self.config and not isinstance(self.config[key], value):
                self.messages.append(f"Parameter {key} has to be of type {str(value)}")
        for key, value in self.config.items():
            if key == "duration":
                if not validate_time_string(value):
                    self.messages.append(
                        f"Parameter {key} has to match {time_string_format_regex}"
                    )
                    bools.append(False)
        return all(bools)

    def inject(self) -> None:
        sleep_duration_seconds = self.config.get("duration_seconds")
        time.sleep(sleep_duration_seconds)

    def params(self) -> dict:
        return {
            "duration": str,
        }

    def preconditions(self) -> bool:
        return True

    @property
    def action(self):
        return "empty"

    def is_runtime(self):
        return True


class ByteMonkeyTreatment(Treatment):
    """Compile-time treatment that injects faults into a java service"""

    def __init__(self, config, name):
        super().__init__(config, name)
        self.docker_client = docker.from_env()
        self.original_entrypoint = ""
        self.dockerfile_content = ""
        self.temporary_jar_path = ""

    @property
    def action(self):
        return "bytemonkey"

    def preconditions(self) -> bool:
        return True

    def build_entrypoint(self) -> str:
        """Build a modified entrypoint from provided bytemonkey configuration"""
        mode = self.config.get("mode")
        rate = self.config.get("rate")
        template_string = f"-javaagent:byte-monkey.jar=mode:{mode},rate:{rate},"
        return template_string

    def read_dockerfile(self):
        dockerfile_path = self.config.get("dockerfile")
        with open(dockerfile_path, "r") as fp:
            self.dockerfile_content = fp.read()

    def download_jar(self, url="https://github.com/mrwilson/byte-monkey/releases/download/1.0.0/byte-monkey.jar"):
        response = requests.get(url)
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix="jar", delete=False) as temporary_jar:
            self.temporary_jar_path = temporary_jar.path
            with open(self.temporary_jar_path, "wb") as fp:
                fp.write(response.content)

    def modify_dockerfile(self):
        """Modify the dockerfile to add the bytemonkey dependency and modify the entrypoint"""
        dockerfile_lines = self.dockerfile_content.splitlines()
        for idx, line in enumerate(dockerfile_lines):
            if line.startswith("ENTRYPOINT"):
                self.original_entrypoint = ""
                dockerfile_lines.insert(idx, f"COPY {self.temporary_jar_path} ./")
                dockerfile_lines[idx] = f"{self.original_entrypoint} {self.build_entrypoint()}"
        return "\n".join(dockerfile_lines)

    def restore_entrypoint(self):
        dockerfile_lines = self.dockerfile_content.splitlines()
        for idx, line in enumerate(dockerfile_lines):
            if line.startswith("ENTRYPOINT"):
                dockerfile_lines[idx] = self.original_entrypoint
        return "\n".join(dockerfile_lines)

    def write_dockerfile(self, new_content: str):
        dockerfile_path = self.config.get("dockerfile")
        with open(dockerfile_path, "w") as fp:
            fp.write(new_content)

    def inject(self) -> None:
        """Update the Dockerfile to modify the java entrypoint and re-build the image"""
        self.read_dockerfile()
        self.write_dockerfile(new_content=self.build_entrypoint())

    def clean(self) -> None:
        """Restore the original docker entrypoint"""
        self.write_dockerfile(new_content=self.dockerfile_content)

    def params(self) -> dict:
        return {
            "mode": str,
            "rate": float,
            "dockerfile": str,
            "service_name": str,
        }

    def _validate_params(self) -> bool:
        pass

    def _transform_params(self) -> None:
        pass


class CorruptPacketTreatment(Treatment):
    def action(self):
        return "corrupt"

    def preconditions(self) -> bool:
        """Check if the service has tc installed"""
        service = self.config.get("service_name")
        command = [
            "tc",
            "-Version"
        ]
        client = docker.from_env()
        try:
            container = client.containers.get(container_id=service)
            status_code, _ = container.exec_run(cmd=command)
            logger.info(
                f"Probed container {service} for tc with result {status_code}"
            )
            if not status_code == 0:
                self.messages.append(
                    f"Container {service} does not have tc installed which is required for {self}. Please install "
                    "package iptables2 in the container"
                )
            return status_code == 0

        except ContainerNotFound:
            logger.error(f"Can't find container {service}")
            return False
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")
            return False

    def inject(self) -> None:
        service = self.config.get("service_name")
        interface = self.config.get("interface")
        duration = self.config.get("duration_seconds")
        percentage = self.config.get("corrupt_percentage")
        # optional param with default arg
        correlation = self.config.get("corrupt_correlation") or "0%"

        command = [
            "tc",
            "qdic",
            "add",
            "dev",
            interface,
            "root",
            "netem",
            "corrupt",
            percentage,
            correlation,
        ]

        client = docker.from_env()
        try:
            container = client.containers.get(container_id=service)
            container.exec_run(cmd=command)
            logger.info(
                f"Injected packet corruption into container {service}. Waiting for {duration}s."
            )
            time.sleep(duration)
        except ContainerNotFound:
            logger.error(f"Can't find container {service}")
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")

    def clean(self) -> None:
        interface = self.config.get("interface") or "eth0"
        service = self.config.get("service_name")
        command = ["tc", "qdisc", "del", "dev", interface, "root", "netem"]
        client = docker.from_env()
        try:
            container = client.containers.get(container_id=service)
            container.exec_run(cmd=command)
            logger.info(f"Cleaned delay treatment from container {service}")
        except (ContainerNotFound, DockerAPIError) as e:
            logger.error(
                f"Cannot clean delay treatment from container {service}: {e.explanation}"
            )
            logger.error(f"Container state for {service} might be polluted now")

    def params(self) -> dict:
        return {
            "service_name": str,
            "interface": str,
            "duration": str,
            "corrupt_percentage": str,
            "corrupt_correlation": Optional[str],
        }

    def _validate_params(self) -> bool:
        bools = []
        for key, value in self.params().items():
            # required params
            if (
                    key in {"service_name", "duration", "interface", "corrupt_percentage"}
                    and key not in self.config
            ):
                self.messages.append(f"Parameter {key} has to be supplied")
                bools.append(False)
            # supplied params have correct type
            if key in self.config and not isinstance(self.config[key], value):
                self.messages.append(f"Parameter {key} has to be of type {str(value)}")
        for key, value in self.config.items():
            if key == "duration":
                if not validate_time_string(value):
                    self.messages.append(
                        f"Parameter {key} has to match {time_string_format_regex}"
                    )
                    bools.append(False)
            if key in {"corrupt_percentage", "corrupt_correlation"}:
                format_regex = r"^[1-9][0-9]?\%$|^100\%$"
                if not bool(re.match(format_regex, value)):
                    self.messages.append(f"Parameter {key} has to match {format_regex}")
                    bools.append(False)
        return all(bools)

    def _transform_params(self) -> None:
        relative_time_string = self.config.get("duration")
        relative_time_seconds = time_string_to_seconds(relative_time_string)
        self.config["duration_seconds"] = relative_time_seconds

    def is_runtime(self) -> bool:
        return True


class MetricsExportIntervalTreatment(Treatment):
    """
    Modify the OTEL_METRICS_EXPORT interval for a given container
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_yaml = None
        # TODO: reuse the existing docker compose client
        self.compose_client = DockerClient(
            compose_files=[self.config.get("compose_file")]
        )
        self.docker_client = docker.from_env()

    def action(self):
        return "otel_metrics_interval"

    def preconditions(self) -> bool:
        # TODO: check proper preconditions
        return True

    def inject(self) -> None:
        service = self.config.get("service_name")
        compose_file = self.config.get("compose_file")
        interval_ms = self.config.get("interval_ms")

        add_env_variable(
            compose_file_path=compose_file,
            service_name=service,
            variable_name="OTEL_METRIC_EXPORT_INTERVAL",
            variable_value=str(int(interval_ms)),
        )

    def clean(self) -> None:
        original_compose_file = self.config["original_yaml"]
        compose_file_path = self.config.get("compose_file")
        with open(compose_file_path, "w+") as file:
            file.write(yaml.safe_dump(original_compose_file, default_flow_style=False))

    def params(self) -> dict:
        return {
            "compose_file": str,
            "service_name": str,
            "interval": str,
        }

    def _validate_params(self) -> bool:
        for key, value in self.params().items():
            if key not in self.config:
                self.messages.append(f"Parameter {key} has to be supplied")
            if not isinstance(self.config[key], value):
                self.messages.append(f"Parameter {key} has to be of type {str(value)}")
        for key in self.config.items():
            if key == "percentage" and not 0 <= self.config[key] <= 100:
                self.messages.append(
                    f"Value for key {key} has to be in the range [0, 100] for {self.treatment_type}"
                )
            if key == "interval" and not validate_time_string(self.config[key]):
                self.messages.append(
                    f"Value for parameter {key} has to match {time_string_format_regex} for {self.treatment_type}"
                )
        return not self.messages

    def _transform_params(self) -> None:
        """Convert the provided time string into milliseconds"""
        interval_s = time_string_to_seconds(self.config["interval"])
        interval_ms = to_milliseconds(interval_s)
        self.config["interval_ms"] = interval_ms

        compose_file_path = self.config.get("compose_file")
        with open(compose_file_path, "r") as file:
            self.config["original_yaml"] = yaml.safe_load(file.read())

    def is_runtime(self) -> bool:
        return False


class ProbabilisticSamplingTreatment(Treatment):
    """
    Add a probabilistic sampling policy to the opentelemetry collector
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = docker.from_env()

    @property
    def action(self):
        return "probl"

    def is_runtime(self) -> bool:
        return False

    def preconditions(self) -> bool:
        # TODO: write tests to check if file exists
        return True

    def inject(self) -> None:
        path = self.config.get("otelcol_extras")
        # support only the base attributes for now
        sampling_percentage = self.config.get("percentage")
        seed = self.config.get("seed")
        updated_extras = {
            "processors": {
                "probabilistic_sampler": {
                    "hash_seed": seed,
                    "sampling_percentage": sampling_percentage
                }
            },
            "service": {
                "pipelines": {
                    "traces": {
                        "processors": ["probabilistic_sampler"],
                    }
                }
            },
        }
        with open(path, "w+") as file:
            existing_config = yaml.safe_load(file.read())
            if not existing_config:
                existing_config = {}
            existing_config.update(updated_extras)
            yaml.dump(existing_config, file, default_flow_style=False)

    def clean(self) -> None:
        original_extras = self.config.get("otelcol_extras_yaml")
        path = self.config.get("otelcol_extras")
        with open(path, "w+") as file:
            file.write(yaml.dump(original_extras, default_flow_style=False))

    def params(self) -> dict:
        return {
            "otelcol_extras": str,
            "percentage": int,
            "seed": int,
        }

    def _validate_params(self) -> bool:
        for key, value in self.params().items():
            if key == "otelcol_extras" and key not in self.config:
                self.messages.append(f"Key {key} is required for {self.treatment_type}")
            if key == "percentage" and key not in self.config:
                self.messages.append(f"Key {key} is required for {self.treatment_type}")
            if key == "seed" and key not in self.config:
                self.messages.append(f"Key {key} is required for {self.treatment_type}")
            if key in self.config and not isinstance(self.config[key], value):
                self.messages.append(f"Key {key} has to be of type {value} for {self.treatment_type}")
        for key in self.config.items():
            if key == "percentage" and not 0 <= self.config[key] <= 100:
                self.messages.append(
                    f"Value for key {key} has to be in the range [0, 100] for {self.treatment_type}"
                )
        return not self.messages

    def _transform_params(self) -> None:
        path = self.config.get("otelcol_extras")
        with open(path, "r") as file:
            contents = yaml.safe_load(file.read())
            if not contents:
                contents = {}
            self.config["otelcol_extras_yaml"] = contents


class TailSamplingTreatment(Treatment):
    """
    Add a tracing tail sampling policy to the OpenTelemetry collector
    As of 2023-03-24, the otelcol is not able to do a hot reload,
    which means we need to restart the container via docker after
    changing the config.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = docker.from_env()

    @property
    def action(self):
        return "tail"

    def is_runtime(self) -> bool:
        return True

    def preconditions(self) -> bool:
        """
        Check that the collector exists and is running

        Not implemented yet
        """
        return True

    def inject(self) -> None:
        """Write the policy to the otelcol-extras file"""
        path = self.config.get("otelcol_extras")
        # get existing configuration
        # inject the policy
        policy_type = self.config.get("type")
        policy_name = self.config.get("policy_name")
        policy_params = self.config.get("policy_params")
        updated_extras = {
            "processors": {
                "tail_sampling": {
                    "policies": [
                        {
                            "name": policy_name,
                            "type": policy_type,
                            policy_type: policy_params,
                        }
                    ]
                }
            },
            "service": {
                "pipelines": {
                    "traces": {
                        "processors": ["tail_sampling"],
                    }
                }
            },
        }
        with open(path, "w+") as file:
            file.write(yaml.dump(updated_extras, default_flow_style=False))

        # restart the collector and block until it has restarted
        container = self.client.containers.get("otel-col")
        container.stop()
        container.wait()
        container.start()

        duration = self.config.get("duration", "0m")
        if duration:
            seconds = time_string_to_seconds(duration)
            time.sleep(seconds)

    def clean(self) -> None:
        original_extras = self.config.get("otelcol_extras_yaml")
        path = self.config.get("otelcol_extras")
        with open(path, "w+") as file:
            file.write(yaml.dump(original_extras, default_flow_style=False))

    def params(self) -> dict:
        return {
            "otelcol_extras": str,
            "policy_name": str,
            "decision_wait": str,
            "num_traces": int,
            "expected_new_traces": int,
            "type": str,
            "policy_params": dict,
        }

    def _validate_params(self) -> bool:
        # TODO: implement the method
        return True

    def _transform_params(self) -> None:
        path = self.config.get("otelcol_extras")
        with open(path, "r") as file:
            contents = yaml.safe_load(file.read())
            if not contents:
                contents = {}
            self.config["otelcol_extras_yaml"] = contents


class PauseTreatment(Treatment):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = docker.from_env()

    def is_runtime(self) -> bool:
        return True

    @property
    def action(self):
        return "pause"

    def params(self) -> dict:
        return {
            "service_name": str,
            "duration": str,
        }

    def _validate_params(self) -> bool:
        for key, value in self.params().items():
            # required key
            if key == "service_name" and key not in self.config:
                self.messages.append(f"Key {key} is required for {self.treatment_type}")
            # required key
            if key == "duration" and key not in self.config:
                self.messages.append(f"Key {key} is required for {self.treatment_type}")
            # key has correct type
            if key in self.config and not isinstance(self.config[key], value):
                self.messages.append(
                    f"Key {key} has to be of type {value} for {self.treatment_type}"
                )
        for key in self.config.items():
            # if an interval is supplied, a timeout needs to be supplied as well
            if key == "duration" and not validate_time_string(self.config[key]):
                self.messages.append(
                    f"Value for key {key} has to match {time_string_format_regex} for {self.treatment_type}"
                )
        return not self.messages

    def _transform_params(self) -> None:
        if "duration" in self.config:
            relative_time_string = self.config.get("duration")
            relative_time_seconds = time_string_to_seconds(relative_time_string)
            self.config |= {"duration_seconds": relative_time_seconds}

    def preconditions(self) -> bool:
        """Check if the docker daemon is running and the container is running"""
        service = self.config.get("service_name")
        try:
            container = self.client.containers.get(container_id=service)
            container_state = container.status
            logger.info(
                f"Probed container {service} for state running with result {container_state}"
            )
            if not container_state == "running":
                self.messages.append(
                    f"Container {service} is not running which is required for {self.treatment_type}."
                )
            return container_state == "running"
        except ContainerNotFound:
            self.messages.append(
                f"Can't find container {service} for {self.treatment_type}"
            )
            return False
        except DockerAPIError as e:
            self.messages.append(
                f"Can't talk to Docker API: {e.explanation} in {self.treatment_type}"
            )
            return False

    def inject(self):
        duration_seconds = self.config.get("duration_seconds")
        service = self.config.get("service_name")

        try:
            container = self.client.containers.get(container_id=service)
            container.pause()
        except ContainerNotFound:
            logger.error(f"Can't find container {service}")
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")
        logger.info(
            f"Injected pause into container {service}. Waiting for {duration_seconds}s"
        )
        time.sleep(duration_seconds)

    def clean(self):
        service = self.config.get("service_name")
        try:
            container = self.client.containers.get(container_id=service)
            container.unpause()
            logger.debug(f"Cleaned pause from container {service}.")
            self.client.close()
        except (ContainerNotFound, DockerAPIError) as e:
            logger.error(
                f"Cannot clean pause treatment from container {service}: {e.explanation}"
            )
            logger.error(f"Container state for {service} might be polluted now")


class NetworkDelayTreatment(Treatment):
    """Inject network delay into a service"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = docker.from_env()

    action = "delay"

    def is_runtime(self) -> bool:
        return True

    def _validate_params(self) -> bool:
        for key, val in self.params().items():
            # required params
            if (
                    key in {"service_name", "duration", "interface", "delay_time"}
                    and key not in self.config
            ):
                self.messages.append(
                    f"Parameter {key} has to be supplied for {self.treatment_type}"
                )
            # supplied params have correct type
            if key in self.config and not isinstance(self.config[key], val):
                self.messages.append(
                    f"Parameter {key} has to be of type {val.__class__.__name__} for {self.treatment_type}"
                )
        for key, value in self.config.items():
            if key in {"duration", "delay_time", "delay_jitter"}:
                if not validate_time_string(value):
                    self.messages.append(
                        f"Value for parameter {key} has to match {time_string_format_regex} for {self.treatment_type}"
                    )
            if key == "delay_correlation":
                format_regex = r"\d+\%"
                if not bool(re.match(format_regex, value)):
                    self.messages.append(
                        f"Value for parameter {key} has to match {format_regex} for {self.treatment_type}"
                    )
            if key == "distribution":
                distribution_set = {"uniform", "pareto", "normal", "paretonormal"}
                if key not in distribution_set:
                    self.messages.append(
                        f"Value for parameter {key} has to be one of {distribution_set} for {self.treatment_type}"
                    )
        return not self.messages

    def _transform_params(self) -> None:
        # correctly formatted params can be passed to tc directly as it can handle values + units
        # we need only transform the duration into seconds for the time.sleep call
        relative_time_string = self.config.get("duration")
        relative_time_seconds = time_string_to_seconds(relative_time_string)
        self.config["duration_seconds"] = relative_time_seconds

    def params(self) -> dict:
        return {
            "service_name": str,
            "interface": str,
            "duration": str,
            "delay_time": str,
            "delay_jitter": Optional[str],
            "delay_correlation": Optional[str],
            "delay_distribution": Optional[str],
        }

    def preconditions(self) -> bool:
        """Check if the service has tc installed"""
        service = self.config.get("service_name")
        command = ["tc", "-Version"]
        try:
            container = self.client.containers.get(container_id=service)
            status_code, _ = container.exec_run(cmd=command)
            logger.info(f"Probed container {service} for tc with result {status_code}")
            if not status_code == 0:
                self.messages.append(
                    f"Container {service} does not have tc installed which is required for {self.treatment_type}. Please install "
                    "package iptables2 in the container"
                )
            return status_code == 0

        except ContainerNotFound:
            self.messages.append(f"Can't find container {service}")
            return False
        except DockerAPIError as e:
            self.messages.append(f"Can't talk to the Docker API: {e.explanation}")
            return False

    def inject(self) -> None:
        # required params
        service = self.config.get("service_name")
        interface = self.config.get("interface")
        delay_time = self.config.get("delay_time")
        duration = self.config.get("duration_seconds")
        # optional params: use default values so we dont need to construct multiple commands
        jitter = self.config.get("delay_jitter", "0ms")
        correlation = self.config.get("delay_correlation", "0%")
        command = [
            "tc",
            "qdisc",
            "add",
            "dev",
            interface,
            "root",
            "netem",
            "delay",
            delay_time,
            jitter,
            correlation,
        ]
        try:
            container = self.client.containers.get(container_id=service)
            container.exec_run(cmd=command)
            logger.info(
                f"Injected delay into container {service}. Waiting for {duration}s."
            )
            time.sleep(duration)
        except ContainerNotFound:
            logger.error(f"Can't find container {service}")
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")

    def clean(self) -> None:
        interface = self.config.get("interface") or "eth0"
        service = self.config.get("service_name")
        command = ["tc", "qdisc", "del", "dev", interface, "root", "netem"]
        try:
            container = self.client.containers.get(container_id=service)
            container.exec_run(cmd=command)
            logger.info(f"Cleaned delay treatment from container {service}")
            self.client.close()
        except (ContainerNotFound, DockerAPIError) as e:
            logger.error(
                f"Cannot clean delay treatment from container {service}: {e.explanation}"
            )
            logger.error(f"Container state for {service} might be polluted now")


class PacketLossTreatment(Treatment):
    """Inject packet loss into a service"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = docker.from_env()

    action = "loss"

    def is_runtime(self) -> bool:
        return True

    def params(self) -> dict:
        return {
            "service_name": str,
            "duration": str,
            "interface": str,
            "loss_percentage": str,
        }

    def _validate_params(self) -> bool:
        for key, value in self.params().items():
            if key not in self.config:
                self.messages.append(
                    f"Parameter {key} has to be supplied for {self.treatment_type}"
                )
            if not isinstance(self.config[key], value):
                self.messages.append(
                    f"Parameter {key} has to be of type {value.__class__.__name__} for {self.treatment_type}"
                )
        for key in self.config:
            if key == "duration":
                if not validate_time_string(self.config[key]):
                    self.messages.append(
                        f"Value for parameter {key} has to match {time_string_format_regex} for {self.treatment_type}"
                    )
            if key == "loss_percentage":
                format_regex = r"^[1-9][0-9]?\%$|^100\%$"
                if not bool(re.match(format_regex, self.config[key])):
                    self.messages.append(
                        f"Value for parameter {key} has to match {format_regex} for {self.treatment_type}"
                    )
        return not self.messages

    def _transform_params(self) -> None:
        if "duration" in self.config:
            relative_time_string = self.config.get("duration")
            relative_time_seconds = time_string_to_seconds(relative_time_string)
            self.config |= {"duration_string": str(relative_time_seconds)}
            self.config |= {"duration_integer": relative_time_seconds}

    def preconditions(self) -> bool:
        """Check if the service has tc installed"""
        service = self.config.get("service_name")
        command = ["tc", "-Version"]
        try:
            container = self.client.containers.get(container_id=service)
            status_code, _ = container.exec_run(cmd=command)
            logger.info(f"Probed container {service} for tc with result {status_code}")
            if not status_code == 0:
                self.messages.append(
                    f"Container {service} does not have tc installed which is required for {self}. Please install "
                    "package iptables2 in the container"
                )
            return status_code == 0
        except ContainerNotFound:
            logger.error(f"Can't find container {service}")
            return False
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")
            return False

    def inject(self):
        duration_seconds = self.config.get("duration_integer")
        service = self.config.get("service_name")
        percentage = self.config.get("loss_percentage")
        interface = self.config.get("interface")
        command = [
            "tc",
            "qdisc",
            "add",
            "dev",
            interface,
            "root",
            "netem",
            "loss",
            "random",
            percentage,
        ]
        try:
            container = self.client.containers.get(container_id=service)
            status_code, _ = container.exec_run(cmd=command)
            logger.debug(
                f"Injected packet loss into container {service} with status code {status_code}. Waiting for {duration_seconds}s"
            )
            time.sleep(duration_seconds)
        except ContainerNotFound:
            logger.error(f"Can't find container {service}")
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")

    def clean(self):
        interface = self.config.get("interface") or "eth0"
        service = self.config.get("service_name")
        command = [
            "tc",
            "qdisc",
            "del",
            "dev",
            interface,
            "root",
            "netem",
        ]
        try:
            container = self.client.containers.get(container_id=service)
            container.exec_run(cmd=command)
            logger.info(f"Cleaned packet loss treatment in container {service}.")
            self.client.close()
        except (DockerAPIError, ContainerNotFound) as e:
            logger.error(
                f"Cannot clean packet loss treatment from container {service}: {e.explanation}"
            )
            logger.error(f"Container state for {service} might be polluted now")


class KillTreatment(Treatment):
    """
    Kill a Docker container.
    """

    action = "kill"

    def preconditions(self) -> bool:
        """Check if the docker daemon is running and the container is running"""
        service = self.config.get("service_name")
        client = docker.from_env()
        try:
            container = client.containers.get(container_id=service)
            container_state = container.status
            logger.debug(
                f"Probed container {service} for state running with result {container_state}"
            )
            if not container_state == "running":
                self.messages.append(
                    f"Container {service} is not running which is required for {self.treatment_type}."
                )
            return container_state == "running"
        except ContainerNotFound:
            logger.error(f"Can't find container {service}")
            return False
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")
            return False

    def inject(self) -> None:
        service_name = self.config.get("service_name")
        duration_seconds = self.config.get("duration_seconds")
        client = docker.from_env()
        try:
            container = client.containers.get(container_id=service_name)
            container.kill()
            logger.debug(
                f"Killed container {service_name}. Sleeping for {duration_seconds}"
            )
            time.sleep(duration_seconds)
        except ContainerNotFound:
            logger.error(f"Can't find container {service_name}")
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")

    def clean(self) -> None:
        service_name = self.config.get("service_name")
        client = docker.from_env()
        try:
            container = client.containers.get(container_id=service_name)
            container.restart()
            logger.debug(f"Restarted container {service_name}")
        except ContainerNotFound:
            logger.error(f"Can't find container {service_name}")
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")

    def params(self) -> dict:
        return {
            "service_name": str,
            "duration": str,
        }

    def _validate_params(self) -> bool:
        for key, value in self.params().items():
            if key == "service_name" and key not in self.config:
                self.messages.append(
                    f"Parameter {key} has to be supplied for {self.treatment_type}"
                )
            if key == "service_name" and not isinstance(self.config[key], value):
                self.messages.append(
                    f"Parameter {key} has to be of type {value} for {self.treatment_type}"
                )
        for key, value in self.config.items():
            if key == "duration" and not validate_time_string(value):
                self.messages.append(
                    f"Parameter {key} has to match {time_string_format_regex} for {self.treatment_type}"
                )
        return not self.messages

    def _transform_params(self):
        relative_time_string = self.config.get("duration", "0s")
        relative_time_seconds = time_string_to_seconds(relative_time_string)
        self.config |= {"duration_seconds": relative_time_seconds}

    def is_runtime(self) -> bool:
        return True


class PacketReorderTreatment(Treatment):
    """
    Reorder packets. This can be used to simulate different cache locality effects.
    This is an example of a non-destructive treatment incompatible with the chaos engineering approach.
    Rather, this could be used to improve upon the system.
    Confer https://www.usenix.org/conference/nsdi22/presentation/ghasemirahni
    """

    # TODO: implement packet reordering


class SlotTreatment(Treatment):
    """Defer the delivery of accumulated packets to within a slot.
    Each slot is configurable with a minimum delay, number of bytes delivered per slot and
    number of delivered packets per slot.

    This treatment can be used to simulate bursty traffic, i.e. network congestion effects.
    """

    # TODO: implement slot treatment


class PrometheusIntervalTreatment(Treatment):
    """
    Treatment to change the global scrape interval of a Prometheus instance.

    Prometheus is able to reload its configuration at runtime on a post request to  /-/reload
    (cf. https://prometheus.io/docs/prometheus/latest/configuration/configuration/),
    therefore we only need as a parameter the path to the prometheus configuration file
    and the new scrape interval. The treatment memorizes the old scrape_interval for the cleanup method and
    writes the new scrape interval to the config.


    """

    def preconditions(self) -> bool:
        """Check that the config exists at the specified location and that Prometheus is running"""
        return True

    def inject(self) -> None:
        prometheus_yaml = self.config.get("prometheus_yaml")
        prometheus_yaml["global"]["scrape_interval"] = self.config.get("interval")
        prometheus_path = self.config.get("prometheus_config")
        with open(prometheus_path, "w+") as fp:
            yaml.dump(prometheus_yaml, fp, default_flow_style=False)
        # tell prometheus to reload the config
        # TODO: infer the url from docker compose file or have it be user provided
        requests.post("http://localhost:9090/-/reload")

    def clean(self) -> None:
        prometheus_yaml = self.config.get("prometheus_yaml")
        prometheus_yaml["global"]["scrape_interval"] = self.config.get(
            "original_interval"
        )
        prometheus_path = self.config.get("prometheus_config")
        with open(prometheus_path, "w+") as fp:
            yaml.dump(prometheus_yaml, fp, default_flow_style=False)
        # tell prometheus to reload the config
        requests.post("http://localhost:9090/-/reload")

    def params(self) -> dict:
        return {
            "prometheus_config": str,
            "interval": str,
        }

    def _validate_params(self) -> bool:
        for key, val in self.params().items():
            if key in {"prometheus_config", "interval"} and key not in self.config:
                self.messages.append(
                    f"Parameter {key} has to be supplied for {self.treatment_type}"
                )
            if key in self.config and not isinstance(self.config[key], val):
                self.messages.append(
                    f"Parameter {key} has to be of type {val} for {self.treatment_type}"
                )
        for key, value in self.config.items():
            prometheus_regex = (
                r"((([0-9]+)y)?(([0-9]+)w)?(([0-9]+)d)?(([0-9]+)h)?(([0-9]+)m)?((["
                r"0-9]+)s)?(([0-9]+)ms)?|0)"
            )
            if key == "interval" and not bool(re.match(prometheus_regex, value)):
                self.messages.append(
                    f"Parameter {key} has to match {prometheus_regex} for {self.treatment_type}"
                )
            if key == "prometheus_config":
                if not os.path.isfile(value):
                    self.messages.append(f"Prometheus config at {value} does not exist")
        return not self.messages

    def _transform_params(self) -> None:
        """
        Memorize the original prometheus setting and provide a loaded version of the prometheus yaml config
        """
        # since _transform_params always get called after validation, we know the file exists
        path = self.config.get("prometheus_config")
        with open(path, "r") as fp:
            self.config["prometheus_yaml"] = yaml.safe_load(fp.read())
            self.config["original_interval"] = self.config["prometheus_yaml"]["global"][
                "scrape_interval"
            ]

    @property
    def action(self):
        return "sampling"

    def is_runtime(self) -> bool:
        return False


class StressTreatment(Treatment):
    """
    Stress system resources of a service via stress-ng.
    """

    action = "stress"

    def preconditions(self) -> bool:
        """Check if the service has stress-ng installed"""
        service = self.config.get("service_name")
        command = ["stress-ng", "--version"]
        client = docker.from_env()
        try:
            container = client.containers.get(container_id=service)
            status_code, _ = container.exec_run(cmd=command)
            logger.debug(
                f"Probed container {service} for stress-ng installation with result {status_code}"
            )
            if not status_code == 0:
                self.messages.append(
                    f"Container {service} does not have stress-ng installed which is required for {self.treatment_type}."
                )
            return status_code == 0

        except ContainerNotFound:
            logger.error(f"Can't find container {service}")
            return False
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")
            return False

    def _build_stressor_list(self):
        return list(sum(self.stressors.items(), ()))

    def _build_command(self):
        stressor_list = self._build_stressor_list()
        return (
                ["stress-ng"] + stressor_list + ["--timeout", self.config.get("duration")]
        )

    def inject(self) -> None:
        service_name = self.config.get("service_name")

        command = self._build_command()
        client = docker.from_env()

        try:
            container = client.containers.get(container_id=service_name)
            status_code, _ = container.exec_run(cmd=command)
            logger.debug(
                f"Injected stress into container {service_name}. stress-ng terminated with status code {status_code}."
            )
        except ContainerNotFound:
            logger.error(f"Can't find container {service_name}")
        except DockerAPIError as e:
            logger.error(f"Docker API returned an error: {e.explanation}")

    def clean(self) -> None:
        # stress-ng cleans up after itself
        pass

    def params(self) -> dict:
        return {
            "service_name": str,
            "stressors": dict,
            "duration": str,
        }

    def _validate_params(self) -> bool:
        for key, val in self.params().items():
            if (
                    key in {"service_name", "duration", "stressors"}
                    and key not in self.config
            ):
                self.messages.append(
                    f"Parameter {key} has to be supplied for {self.treatment_type}"
                )
            if key in self.config and not isinstance(self.config[key], val):
                self.messages.append(
                    f"Parameter {key} has to be of type {val.__class__.__name__} for {self.treatment_type}"
                )
        for key, value in self.config.items():
            if key == "duration" and not validate_time_string(value):
                self.messages.append(
                    f"Parameter {key} has to match {time_string_format_regex} for {self.treatment_type}"
                )
            if key == "stressors" and not value:
                self.messages.append(
                    f"Parameter {key} has to have at least one stressor for {self.treatment_type}"
                )
        return not self.messages

    def _transform_params(self) -> None:
        if "duration" in self.config:
            relative_time_string = self.config.get("duration")
            relative_time_seconds = time_string_to_seconds(relative_time_string)
            self.config |= {"duration_integer": relative_time_seconds}
        if "stressors" in self.config:
            # transform the stressors by prefixing with -- and place them into a new dict for clarity
            self.stressors = {}
            for stressor_name, stressor_count in self.config["stressors"].items():
                prefixed_stressor = f"--{stressor_name}"
                self.stressors[prefixed_stressor] = str(stressor_count)

    def is_runtime(self) -> bool:
        return False
