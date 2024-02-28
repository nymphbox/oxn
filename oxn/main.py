import logging
import sys

from .engine import Engine
from .errors import (
    OrchestrationException,
    PrometheusException,
    JaegerException,
    OxnException,
)
from .log import initialize_logging
from .argparser import parse_oxn_args

logger = logging.getLogger(__name__)


def main():
    args = parse_oxn_args(sys.argv[1:])
    initialize_logging(loglevel=args.log_level, logfile=args.log_file)
    engine = Engine(
        configuration_path=args.spec,
        report_path=args.report,
        treatment_file=args.extend,
    )
    try:
        engine.read_experiment_specification()
    except OxnException as e:
        logger.error(f"OxnException: {e}")
        sys.exit(1)

    try:
        engine.validate_syntax()
    except OxnException as e:
        logger.error(f"OxnException: {e}")
        sys.exit(1)
    try:
        engine.run(
            runs=args.times,
            orchestration_timeout=args.timeout,
            randomize=args.randomize,
            accounting=args.accounting,
        )
    except OrchestrationException as orc_exception:
        logger.error(f"OrchestrationException: {orc_exception}")
    except PrometheusException as prom_exception:
        logger.error(f"PrometheusException: {prom_exception}")
    except JaegerException as jaeger_expcetion:
        logger.error(f"JaegerException: {jaeger_expcetion}")
    except OxnException as oxn_exception:
        logger.error(f"OxnException: {oxn_exception}")
    except KeyboardInterrupt:
        logger.info("Trying to shut down gracefully. Press ctrl-c to force")
    finally:
        if engine.loadgen_running:
            engine.generator.kill()
            logger.info("Shut down load generation")
        if engine.sue_running:
            # TODO: call cleanup methods here
            engine.orchestrator.teardown()
            logger.info("Shut down sue")
