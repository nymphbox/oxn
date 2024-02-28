import logging
from typing import List

import gevent
import locust
from locust import LoadTestShape
from locust import events
from locust.env import Environment

import oxn.utils as utils

logger = logging.getLogger(__name__)


class LoadGenerator:
    """Load generation for experiments

    Wrapper class around locust to provide customizable load generation for the SUE.

    From the customizations in the load generation subsection of the environment section
    of an experiment specification we then build a custom LoadTestShape locust class
    and execute the load generation.
    """

    def __init__(self, config=None):
        self.config = config
        """The experiment spec"""
        self.locust_tasks: List[LocustTask] = []
        """A list of locust tasks defined in the spec"""
        self.stages: List[dict] = []
        """A list of stages defined in the spec"""
        self.run_time: int = 0
        """The total desired run time of the load generation"""
        self.env = None
        """Locust environment"""
        self._read_config()
        """Read the experiment spec and populate stages and tasks"""

    def _read_config(self):
        """Read the load generation section of an experiment specification"""
        loadgen_section = self.config["experiment"]["loadgen"]
        self.stages = loadgen_section.get("stages", None)
        self.run_time = utils.time_string_to_seconds(loadgen_section["run_time"])
        self.locust_tasks = [
            LocustTask(**task_dict) for task_dict in loadgen_section["tasks"]
        ]

        sequential = loadgen_section.get("sequential", False)
        if not sequential:
            self.locust_class = self._locust_factory_random()
        else:
            self.locust_class = self._locust_factory_sequential()
        if self.stages:
            self.shape_instance = self._shape_factory()
        else:
            self.shape_instance = None
        self.env = Environment(
            user_classes=[self.locust_class],
            shape_class=self.shape_instance,
            events=events,
        )

    def _task_sequence_factory(self):
        """Create a sequential task set to force ordered execution of tasks"""

        class TaskSequence(locust.SequentialTaskSet):
            tasks = [task_factory(task=task) for task in self.locust_tasks]

        return TaskSequence

    def _shape_factory(self):
        """Build a custom LoadTestShape from a list of stages"""

        class CustomLoadTestShape(LoadTestShape):
            def __init__(self, stages):
                super().__init__()
                self.stages = stages

            def tick(self):
                run_time = self.get_run_time()
                logger.debug(f"Current run time in CustomLoadShape: {run_time}")
                logger.debug(f"Current user count: {self.get_current_user_count()}")
                for stage in self.stages:
                    if run_time < stage["duration"]:
                        return stage["users"], stage["spawn_rate"]

        return CustomLoadTestShape(stages=self.stages)

    def _locust_factory_random(self):
        """Build a Locust class from a list of tasks"""
        simple_tasks = {task_factory(task): task.weight for task in self.locust_tasks}

        class CustomLocust(locust.FastHttpUser):
            # tasks = simple_tasks
            tasks = simple_tasks
            host = "http://localhost:8080"

        return CustomLocust

    def _locust_factory_sequential(self):
        """Create a fast http user with a sequential task set"""

        class CustomLocust(locust.FastHttpUser):
            # tasks = simple_tasks
            tasks = [self._task_sequence_factory()]
            host = "http://localhost:8080"

        return CustomLocust

    def start(self):
        """Start the load generation"""
        runner = self.env.create_local_runner()
        if self.shape_instance:
            runner.start_shape()
        else:
            runner.start(user_count=1, spawn_rate=1)
        gevent.spawn_later(self.run_time, lambda: runner.quit())

    def stop(self):
        """Join the greenlet created by locust env (= wait until it has finished)"""
        runner = self.env.runner
        runner.greenlet.join()

    def kill(self):
        """Kill all greenlets spawned by locust"""
        runner = self.env.runner
        runner.greenlet.kill(block=True)


class LocustTask:
    """Class to hold locust task information"""

    def __init__(self, name="", endpoint="", verb="", weight=1, params=None):
        self.name = name
        """Optional name for the task"""
        self.endpoint = endpoint
        """HTTP endpoint to hit"""
        self.verb = verb
        """HTTP verb to use"""
        self.weight = weight
        """Weight parameter that indicates how likely the task is to excecute versus other tasks"""
        self.params = params
        """Optional JSON parameters to send with the request"""

    def __str__(self):
        return f"LocustTask(name={self.name}, verb={self.verb}, url={self.endpoint})"

    def __repr__(self):
        return self.__str__()


def task_get_factory(endpoint, params):
    """Factory for a task that represents a GET request"""

    def _locust_task(locust):
        locust.client.get(endpoint, json=params)

    return _locust_task


def task_post_factory(endpoint, params):
    """Factory for a task that represents a POST request with params"""

    def _locust_task(locust):
        locust.client.post(endpoint, json=params)

    return _locust_task


@events.request.add_listener
def _on_request(
        request_type,
        name,
        response_time,
        response_length,
        response,
        context,
        exception,
        start_time,
        url,
        **kwargs,
):
    """Event hook to log requests made by Locust"""
    logger.debug(
        f"{request_type} {name} {response.status_code} {response_time} {context}"
    )
    if exception:
        logger.debug(f"{request_type} {exception}")


def task_factory(task: LocustTask):
    """Factory to create simple locust tasks from a loadgen section in experiment spec"""
    verb = task.verb
    if verb == "get":
        return task_get_factory(endpoint=task.endpoint, params=task.params)
    if verb == "post":
        return task_post_factory(endpoint=task.endpoint, params=task.params)
