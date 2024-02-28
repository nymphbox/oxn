"""Module to handle orchestration of a system under experiment"""
import logging
import os
import time
from pathlib import Path
from typing import Optional, List

import docker.errors
import python_on_whales
from python_on_whales import DockerClient
from python_on_whales import DockerException
from docker.errors import NotFound
from .errors import OrchestrationException

logger = logging.getLogger(__name__)


class DockerComposeOrchestrator:
    """
    Container orchestration for building the system under experiment

    Wrapper class around docker via python-on-whales and docker-py
    to provide container orchestration features. We use python-on-whales
    for scripting around docker compose and docker-py for everything else.

    """

    def __init__(self, experiment_config=None):
        self.compose_client: Optional[DockerClient] = None
        self.docker_client = None
        self.experiment_config: dict = experiment_config
        self.docker_compose_path: str = ""
        self.docker_compose_yml: dict = {}
        self.docker_service_names = set()
        self.sue_service_names = set()
        self.service_container_map = {}  # map service names to container names
        self.container_service_map = {}  # map container names to service names
        self.exclude = None
        self.include = None
        self.messages = []
        if self.experiment_config:
            self._read_orchestration_section()
            self._initialize_compose_client()
            self._initialize_docker_client()
            self._validate_sue()
        self._read_service_names()
        self._build_sue_service_names()

    def _validate_sue(self):
        """Validate the sue section of an experiment spec"""
        sue_section = self.experiment_config["experiment"]["sue"]
        # check that the compose file exists
        compose_path = sue_section["compose"]
        compose_file = Path(compose_path)
        if not compose_file.is_file():
            self.messages.append("Specified compose file does not exist")
        # if it exists, check that it's a valid docker-compose file
        try:
            compose_config = self.compose_client.compose.config(return_json=False)
            # check that the provided service names in include exist
            included = sue_section.get("include", [])
            excluded = sue_section.get("exclude", [])
            if included:
                for service_name in included:
                    if service_name not in compose_config.services.keys():
                        self.messages.append(
                            f"Included service {service_name} does not exist in the compose file"
                        )
            if excluded:
                for service_name in excluded:
                    if service_name not in compose_config.services.keys():
                        self.messages.append(
                            f"Excluded service {service_name} does not exist in the compose file"
                        )
        except DockerException:
            self.messages.append("Specified compose file has invalid format")
        if self.messages:
            explanation = "\n".join(self.messages)
            raise OrchestrationException(
                message="Error while validating the sue composition",
                explanation=explanation,
            )

    def _read_orchestration_section(self):
        docker_compose_path = self.experiment_config["experiment"]["sue"]["compose"]
        excluded_services = (
            self.experiment_config["experiment"]["sue"].get("exclude") or []
        )
        included_services = (
            self.experiment_config["experiment"]["sue"].get("include") or []
        )
        self.exclude = excluded_services
        self.include = included_services
        self.docker_compose_path = docker_compose_path

    def _read_service_names(self):
        config = self.compose_client.compose.config(return_json=False)
        for service_name, service_configuration in config.services.items():
            self.docker_service_names.add(service_name)
            self.service_container_map[
                service_name
            ] = service_configuration.container_name
            self.container_service_map[
                service_configuration.container_name
            ] = service_name

    def _build_sue_service_names(self):
        """Build the SUE service composition from the provided configuration"""
        if self.include and self.exclude:
            services = set(self.docker_service_names).intersection(set(self.include))
            services = services.difference(set(self.exclude))
        elif self.exclude:
            services = list(
                set(self.docker_service_names).difference(set(self.exclude))
            )
        elif self.include:
            services = list(
                set(self.docker_service_names).intersection(set(self.include))
            )
        else:
            services = list(self.docker_service_names)
        self.sue_service_names = services

    def _initialize_compose_client(self):
        try:
            self.compose_client = DockerClient(compose_files=[self.docker_compose_path])
        except python_on_whales.ClientNotFoundError as compose_exception:
            raise OrchestrationException(
                message="Error while building the sue",
                explanation=str(compose_exception),
            )

    def _initialize_docker_client(self):
        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
        except docker.errors.APIError as docker_api_error:
            raise OrchestrationException(
                message="Error while building the sue",
                explanation=docker_api_error.explanation,
            )
        except docker.errors.DockerException as docker_exception:
            raise OrchestrationException(
                message="Cannot connect to docker daemon",
                explanation=docker_exception,
            )

    def _locate_otelcol_extras(self):
        otelcol_file_name = "otelcol-config-extras.yml"
        path = ""
        compose_dirname = os.path.dirname(self.docker_compose_path)
        for root, dirs, files in os.walk(compose_dirname):
            if otelcol_file_name in files:
                path = os.path.join(root, otelcol_file_name)
        return path

    def _read_original_otelcol_extras(self):
        """Read the contents of the original otelcol extras file"""
        self.sue_otelcol_config_path = self._locate_otelcol_extras()
        with open(self.sue_otelcol_config_path, "r") as fp:
            self.sue_otelcol_config_file = fp.read()

    def translate_compose_names(self, compose_names: List[str]):
        """Translate a list of service names from the compose file to a list of container names"""
        container_names = [
            self.service_container_map.get(compose_name)
            for compose_name in compose_names
        ]
        return container_names

    def translate_container_names(self, container_names: List[str]):
        """Translate a list of container names to service names"""
        service_names = [
            self.container_service_map.get(container_name)
            for container_name in container_names
        ]
        return service_names

    @property
    def running_services(self) -> List[str]:
        """Return a list of running services created by the orc"""
        containers = self.compose_client.compose.ps()
        return [self.container_service_map[container.name] for container in containers]

    def orchestrate(self):
        self.compose_client.compose.up(
            detach=True, services=self.sue_service_names, quiet=True
        )

    def ready(self, expected_services=None, timeout=120) -> bool:
        """
        Block until all services are ready
        """
        all_ready = []
        if not expected_services:
            expected_services = self.docker_service_names
        for service_name in expected_services:
            container_name = self.service_container_map[service_name]
            try:
                container = self.docker_client.containers.get(
                    container_id=container_name
                )
                elapsed = 0
                while not container.status == "running" and elapsed < timeout:
                    time.sleep(1)
                    elapsed += 1
                    container = container.reload()
                logger.debug(f"Container {container_name} is running.")
                all_ready.append(True)
            except NotFound as e:
                raise OrchestrationException(message="Error while building the sue", explanation=e)
        # TODO: container "running" state does not mean the service is responsive yet
        # TODO: throw exception if container object is not accessible
        return all(all_ready)

    def teardown(self):
        """Stop the containers specified in compose file"""
        if "OXN_WAIT" in os.environ:
            time.sleep(int(os.environ["OXN_WAIT"]))
        self.compose_client.compose.down(remove_orphans=True, quiet=True)
        self.docker_client.close()
