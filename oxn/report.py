"""Handle the generation of experiment reports"""
import uuid
from typing import Tuple, Union

import locust.stats
import yaml

import pandas as pd
from scipy.stats import ttest_ind

from .runner import ExperimentRunner
from .models.treatment import Treatment
from .responses import TraceResponseVariable, MetricResponseVariable
from .store import construct_key
from .utils import humanize_utc_timestamp
from .errors import OxnException


class Reporter:
    def __init__(
        self,
        report_path: str,
    ):
        self.report_data = {"report": {"runs": {}}}
        self.report_path = report_path
        self.interactions = []

    @staticmethod
    def compute_welch_ttest(
        dataframe: pd.DataFrame, label: str, label_column: str, value_column: str
    ) -> Tuple[str, str, str]:
        """
        Perform a two-sided welsh t-test

        We test under the default H0: Treatment has no effect on response
        via class means.
        """
        try:
            control = dataframe.loc[dataframe[label_column] != label][value_column]
            experiment = dataframe.loc[dataframe[label_column] == label][value_column]
        except (KeyError, AttributeError) as e:
            raise OxnException(
                message="Dataframe passed to welch ttest has wrong format",
                explanation=e,
            )
        ttest_result = ttest_ind(
            control,
            experiment,
            equal_var=False,
            nan_policy="omit",
        )
        return str(ttest_result[0]), str(ttest_result[1]), "welch t-test"

    def gather_interaction(
        self,
        experiment: ExperimentRunner,
        treatment: Treatment,
        response: Union[TraceResponseVariable, MetricResponseVariable],
    ):
        """Gather interaction data between a treatment and a response for the experiment report"""
        value_column = (
            "duration"
            if isinstance(response, TraceResponseVariable)
            else response.metric_name
        )
        display_response_name = (
            response.name
            if isinstance(response, MetricResponseVariable)
            else f"{response.name}.duration"
        )
        store_key = construct_key(
            experiment_key=experiment.config_filename,
            run_key=experiment.short_id,
            response_key=response.name,
        )
        statistic, pvalue, test_name = self.compute_welch_ttest(
            dataframe=response.data,
            label="NoTreatment",
            label_column=treatment.name,
            value_column=value_column,
        )
        self._add_interaction_data(
            treatment_name=treatment.name,
            treatment_type=treatment.treatment_type,
            treatment_start=treatment.start,
            treatment_end=treatment.end,
            response_type=response.response_type,
            response_start=response.start,
            response_end=response.end,
            response_name=display_response_name,
            p_value=pvalue,
            test_statistic=statistic,
            test_performed=test_name,
            store_key=store_key,
        )

    def _add_interaction_data(
        self,
        treatment_name: str,
        treatment_start: int,
        treatment_type: str,
        treatment_end: int,
        response_name: str,
        response_type: str,
        response_start: int,
        response_end: int,
        p_value: str,
        test_statistic: str,
        test_performed: str,
        store_key: str,
    ) -> None:
        """Populate the interaction dict with interaction data"""
        humanized_treatment_start = self._humanize_timestamp(treatment_start)
        humanized_treatment_end = self._humanize_timestamp(treatment_end)
        humanized_response_start = self._humanize_timestamp(response_start)
        humanized_response_end = self._humanize_timestamp(response_end)
        self.interactions.append(
            {
                "treatment_name": treatment_name,
                "treatment_start": humanized_treatment_start,
                "treatment_end": humanized_treatment_end,
                "treatment_type": treatment_type,
                "response_name": response_name,
                "response_start": humanized_response_start,
                "response_end": humanized_response_end,
                "response_type": response_type,
                "p_value": p_value,
                "test_statistic": test_statistic,
                "test_performed": test_performed,
                "store_key": store_key,
            }
        )

    @staticmethod
    def _humanize_timestamp(timestamp: float) -> str:
        """Create human-readable datetime strings from integer timestamps"""
        return humanize_utc_timestamp(timestamp)

    def assemble_interaction_data(self, run_key) -> dict:
        """Assemble all interaction data for an experiment run"""
        self.report_data["report"]["runs"][run_key] = {}
        self.report_data["report"]["runs"][run_key]["interactions"] = {}
        for idx, interaction in enumerate(self.interactions):
            self.report_data["report"]["runs"][run_key]["interactions"][
                f"interaction_{idx}"
            ] = interaction
        return self.report_data

    def add_experiment_data(self, runner: ExperimentRunner) -> dict:
        """Add top level experiment data to the report"""
        try:
            self.report_data["report"][
                "experiment_start"
            ] = runner.humanize_start_timestamp
            self.report_data["report"]["experiment_end"] = runner.humanize_end_timestamp
            self.report_data["report"]["experiment_key"] = runner.short_hash
        except KeyError as key_error:
            raise OxnException(
                message="Can't write experiment data to report",
                explanation=str(key_error),
            )
        return self.report_data

    def add_loadgen_data(
        self,
        request_stats: locust.stats.RequestStats,
        runner: ExperimentRunner,
    ) -> dict:
        """Add load generation details to the report"""
        self.report_data["report"]["runs"][runner.short_id]["loadgen"] = {}
        self.report_data["report"]["runs"][runner.short_id]["loadgen"][
            "loadgen_start_time"
        ] = humanize_utc_timestamp(request_stats.start_time)
        self.report_data["report"]["runs"][runner.short_id]["loadgen"][
            "loadgen_end_time"
        ] = humanize_utc_timestamp(request_stats.last_request_timestamp)
        self.report_data["report"]["runs"][runner.short_id]["loadgen"][
            "loadgen_total_requests"
        ] = request_stats.num_requests
        self.report_data["report"]["runs"][runner.short_id]["loadgen"][
            "loadgen_total_failures"
        ] = request_stats.num_failures
        self.report_data["report"]["runs"][runner.short_id]["loadgen"][
            "task_details"
        ] = {}
        for entry in request_stats.entries.values():
            # get a random task identifier
            task_id = uuid.uuid4().hex[:16]
            self.report_data["report"]["runs"][runner.short_id]["loadgen"][
                "task_details"
            ][task_id] = {
                "url": entry.name,
                "verb": entry.method,
                "requests": entry.num_requests,
                "failures": entry.num_failures,
                "fail_ratio": entry.fail_ratio,
                "sum_response_time": entry.total_response_time,
                "min_response_time": entry.min_response_time,
                "max_response_time": entry.max_response_time,
                "avg_response_time": entry.avg_response_time,
                "median_response_time": entry.median_response_time,
            }
        return self.report_data

    def add_accountant_data(self, runner: ExperimentRunner):
        """Add data from an accountant"""
        self.report_data["report"]["runs"][runner.short_id]["accounting"] = {}
        accountant_data = runner.accountant.consolidated_data
        for container_id, container_data in accountant_data.items():
            container_name = container_data["container_name"]
            self.report_data["report"]["runs"][runner.short_id]["accounting"][
                container_name
            ] = {
                "cpu_seconds": container_data["total_cpu_usage"],
                "number_of_cpus": container_data["number_of_cpus"],
            }

    def dump_report_data(self):
        with open(self.report_path, "w+") as fp:
            contents = yaml.dump(self.report_data, sort_keys=False)
            fp.write(contents)
