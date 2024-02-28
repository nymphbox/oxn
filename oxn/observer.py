"""Module to handle data capture during experiment execution"""
import logging
from typing import Optional
from operator import attrgetter


from .responses import MetricResponseVariable, TraceResponseVariable
from .models.response import ResponseVariable
from .utils import time_string_to_seconds

logger = logging.getLogger(__name__)


class Observer:
    """
    The observer class is responsible for constructing response variables from
    an experiment description and then observing the variables during or after an experiment.
    """

    def __init__(
        self,
        config: Optional[dict],
        experiment_start: Optional[float] = None,
        experiment_end: Optional[float] = None,
    ):
        self.config = config
        """The experiment specification"""
        self.experiment_start = experiment_start
        """The experiment start timestamp """
        self.experiment_end = experiment_end
        """The experiment end timestamp"""
        self._response_variables: dict = {}
        """The response variables constructed from the specification and experiment start / end timestamps"""

    def _initialize_metric_variable(self, response_name, response_description) -> None:
        response_variable = MetricResponseVariable(
            name=response_name,
            description=response_description,
            experiment_start=self.experiment_start,
            experiment_end=self.experiment_end,
        )
        self._response_variables[response_variable.name] = response_variable

    def _initialize_trace_variable(self, response_name, response_description) -> None:
        """Initialize a trace variable from a response description"""
        response_variable = TraceResponseVariable(
            name=response_name,
            description=response_description,
            experiment_start=self.experiment_start,
            experiment_end=self.experiment_end,
        )
        self._response_variables[response_variable.name] = response_variable

    def initialize_variables(self) -> None:
        """
        Process the response variable section from the specification config

        Note that we cannot initialize this straightaway when reading the experiment specification,
        as the observational windows depend on experiment start and end times.
        """
        responses = self.config["experiment"]["responses"]
        for response in responses:
            for response_name, response_params in response.items():
                response_type = response_params["type"]
                if response_type == "trace":
                    self._initialize_trace_variable(
                        response_name=response_name,
                        response_description=response_params,
                    )
                if response_type == "metric":
                    self._initialize_metric_variable(
                        response_name=response_name,
                        response_description=response_params,
                    )

    def variables(self) -> dict[str, ResponseVariable]:
        return self._response_variables

    def time_to_wait_right(self) -> float:
        """Determine the time to wait before observing the variables"""
        max_right_window = max(self.variables().values(), key=attrgetter("end"))
        diff = max_right_window.end - self.experiment_end
        return diff

    def time_to_wait_left(self):
        """
        Determine the time to wait on the left side of an experiment start
        """
        responses = self.config["experiment"]["responses"]
        max_left_window = 0
        for response in responses:
            for response_name, response_params in response.items():
                in_seconds = time_string_to_seconds(response_params["left_window"])
                if in_seconds > max_left_window:
                    max_left_window = in_seconds
        return max_left_window

    def get_metric_variables(self) -> list[MetricResponseVariable]:
        """Return the metric variables of this observer"""
        return [
            v
            for _, v in self.variables().items()
            if isinstance(v, MetricResponseVariable)
        ]

    def get_trace_variables(self) -> list[TraceResponseVariable]:
        """Return the trace variables of this observer"""
        return [
            v
            for _, v in self.variables().items()
            if isinstance(v, TraceResponseVariable)
        ]

    def observe(self) -> None:
        for variable in self.variables().values():
            try:
                variable.observe()
            except Exception as e:
                logger.info(f"failed to capture {variable.name}, proceeding. {e}")
