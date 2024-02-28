import logging
import schema
import yaml

from .runner import ExperimentRunner
from .orchestration import DockerComposeOrchestrator
from .report import Reporter
from .store import write_dataframe
from .loadgen import LoadGenerator
from .utils import utc_timestamp
from .validation import syntactic_schema
from .context import Context
from .errors import OxnException, OrchestrationException

logger = logging.getLogger(__name__)


class Engine:
    """
    Observability experiments engine

    This class encapsulates all behavior needed to execute observability experiments.
    """

    def __init__(self, configuration_path=None, report_path=None, treatment_file=None):
        self.config = configuration_path
        """The path to the configuration file for this engine"""
        self.spec = None
        """The loaded experiment specification"""
        self.report_path = report_path
        """The path to write the experiment report to"""
        self.reporter = Reporter(report_path=report_path)
        """A reference to a reporter instance"""
        self.context = Context(treatment_file_path=treatment_file)
        """A reference to a treatment context"""
        self.additional_treatments = self.context.load_treatment_file()
        """Additional treatments defined by the user"""
        self.orchestrator = None
        """A reference to an orchestrator instance"""
        self.generator = None
        """A reference to a load generator instance"""
        self.runner = None
        """A reference to a runner instance"""
        self.loadgen_running = False
        """Status of the load generator"""
        self.sue_running = False
        """Status of the sue"""

    def read_experiment_specification(self):
        """Read the experiment specification file and confirm that its valid yaml"""
        with open(self.config, "r") as fp:
            contents = fp.read()
            try:
                self.spec = yaml.safe_load(contents)
            except yaml.YAMLError as e:
                raise OxnException(
                    message="Provided experiment spec is not valid YAML",
                    explanation=str(e),
                )

    def validate_syntax(self):
        """Validate the specification syntactically"""
        try:
            syntactic_schema.validate(data=self.spec)
        except schema.SchemaError as e:
            raise OxnException(
                message="Can't validate experiment spec", explanation=str(e)
            )

    def run(
        self,
        runs=None,
        orchestration_timeout=None,
        randomize=False,
        accounting=False,
    ):
        """Run an experiment n times"""

        logger.info(f"Running experiment {self.config} for {runs} times")
        for idx in range(runs):
            logger.info(f"Experiment run {idx + 1} of {runs}")
            self.orchestrator = DockerComposeOrchestrator(
                experiment_config=self.spec,
            )
            self.generator = LoadGenerator(config=self.spec)
            names = (
                self.orchestrator.translate_compose_names(
                    self.orchestrator.sue_service_names
                )
                if accounting
                else []
            )
            self.runner = ExperimentRunner(
                config=self.spec,
                config_filename=self.config,
                additional_treatments=self.additional_treatments,
                random_treatment_order=randomize,
                accountant_names=names,
            )
            self.runner.execute_compile_time_treatments()
            self.orchestrator.orchestrate()
            if not self.orchestrator.ready(timeout=orchestration_timeout):
                self.runner.clean_compile_time_treatments()
                self.orchestrator.teardown()
                raise OrchestrationException(
                    message="Error while building the sue",
                    explanation=f"Could not build the sue within {orchestration_timeout}",
                )
            self.sue_running = True
            logger.info("Started sue")
            for treatment in self.runner.treatments.values():
                if not treatment.preconditions():
                    raise OxnException(
                        message=f"Error while checking preconditions for treatment {treatment.name}",
                        explanation="\n".join(treatment.messages),
                    )
            self.generator.start()
            logger.info("Started load generation")
            self.loadgen_running = True
            experiment_start = utc_timestamp()
            self.runner.experiment_start = experiment_start
            self.runner.observer.experiment_start = experiment_start
            self.runner.execute_runtime_treatments()
            self.runner.clean_compile_time_treatments()
            self.runner.experiment_end = utc_timestamp()
            self.runner.observer.experiment_end = self.runner.experiment_end
            self.runner.observe_response_variables()
            self.generator.stop()
            self.loadgen_running = False
            logger.info("Stopped load generation")
            for _, response in self.runner.observer.variables().items():
                write_dataframe(
                    dataframe=response.data,
                    experiment_key=self.runner.config_filename,
                    run_key=self.runner.short_id,
                    response_key=response.name,
                )
                logger.debug(
                    f"Experiment {self.runner.config_filename}: DataFrame: {len(response.data)} rows"
                )
                logger.info(f"Wrote {response.name} to store")
                if self.report_path:
                    for _, treatment in self.runner.treatments.items():
                        self.reporter.gather_interaction(
                            experiment=self.runner,
                            treatment=treatment,
                            response=response,
                        )
                        logger.debug(
                            f"Gathered interaction data for {treatment} and {response}"
                        )
                    self.reporter.assemble_interaction_data(
                        run_key=self.runner.short_id
                    )
                    logger.debug("Assembled all interaction data")
                    self.reporter.add_loadgen_data(
                        runner=self.runner, request_stats=self.generator.env.stats
                    )
                    logger.debug("Added load generation data")
                    if accounting:
                        self.reporter.add_accountant_data(runner=self.runner)
                        logger.debug("Added accounting data")
            self.orchestrator.teardown()
            logger.info("Stopped sue")
            self.sue_running = False
            logger.info(f"Experiment run {idx + 1} of {runs} completed")
        if self.report_path:
            self.reporter.dump_report_data()
            logger.debug("Wrote report data to file")
