import argparse
import os

from .utils import time_string_to_seconds


def validate_file(file):
    if not os.path.exists(file):
        raise argparse.ArgumentTypeError(
            f"Experiment specification {file} does not exist"
        )
    return file


parser = argparse.ArgumentParser(
    prog="oxn",
    description="Observability experiments engine",
)

parser.add_argument(
    "spec",
    action="store",
    type=validate_file,
    help="Path to an oxn experiment specification to execute.",
)
parser.add_argument(
    "--times", default=1, type=int, help="Run the experiment n times. Default is 1"
)
parser.add_argument(
    "--report",
    dest="report",
    type=str,
    help="Create an experiment report at the specified location. If the file exists, it will be overwritten. If it "
    "does not exist, it will be created.",
)
parser.add_argument(
    "--accounting",
    action="store_true",
    help="Capture resource usage for oxn and the sue. Requires that the report option is set."
    "Will increase the time it takes to run the experiment by about "
    "two seconds for each service in the sue.",
)
parser.add_argument(
    "--randomize",
    action="store_true",
    help="Randomize the treatment execution order. Per default, treatments are executed in the order given in the "
    "experiment specification",
)
parser.add_argument(
    "--extend",
    dest="extend",
    type=validate_file,
    help="Path to a treatment extension file. If specified, treatments in the file will be loaded into oxn.",
)

parser.add_argument(
    "--loglevel",
    dest="log_level",
    choices=["debug", "info", "warning", "error", "critical"],
    nargs="?",
    default="info",
    help="Set the log level. Choose between debug, info, warning, error, critical. Default is info",
)
parser.add_argument(
    "--logfile",
    dest="log_file",
    type=str,
    help="Write logs to a file. If the file does not exist, it will be created.",
)

parser.add_argument(
    "--timeout",
    default="1m",
    help="Timeout after which we stop trying to build the SUE. Default is 1m",
    type=time_string_to_seconds
)


def parse_oxn_args(args):
    args = parser.parse_args(args)
    if args.accounting and not args.report:
        parser.error("The --accounting option requires the --report option to be set")
    return args
