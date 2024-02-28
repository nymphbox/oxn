## Introduction
OXN - **O**bservability e**X**periment e**N**gine - 
is an extensible software framework to run observability experiments and compare observability design decisions.
OXN follows the design principles of cloud benchmarking and strives towards portable and repeatable experiments.
Experiments are defined as yaml-based configuration files, which allows them to be shared, versioned and repeated.
OXN automates every step of the experiment process in a straightforward manner, from SUE setup to data collection, processing and reporting. 


## Installation

##### Prerequisites
- Docker + Docker Compose
- Python >= v3.10
- Jupyter


###### Setup the OpenTelemetry demo application
1.  Change to the forked demo submodule folder

    ```cd opentelemetry-demo/```

2. Build needed containers. This will take a while a while

    ``` make build ```

    Alternativly, you can just build the container with fault injection, e.g., the recommender service. This may cause incompatability in the future. 

    ``` docker compose build recommendationservice ```

3. Run docker compose to start the demo

    ```docker compose up```

3. Verify the demo application is working by visiting

* ```http:localhost:8080/``` for the Webstore
* ```http:localhost:8080/jaeger/ui``` for Jaeger
* ```http:localhost:9090``` for Prometheus

##### Install oxn via pip

> Note: oxn requires Python >= 3.10

1. Install virtualenv

    ```pip install virtualenv```

2. Create a virtualenv (named venv here)

    ```virtualenv venv```

3. Source the venv 

    ```source venv/bin/activate```

4. Install oxn

    ```pip install . ```

> Note: oxn requires the pytables package, which in turn requires a set of dependencies.


##### Run an example observability experiment
1. Verify that oxn is correctly installed 

```
oxn --help
usage: oxn [-h] [--times TIMES] [--report REPORT] [--accounting] [--randomize] [--extend EXTEND] [--loglevel [{debug,info,warning,error,critical}]] [--logfile LOG_FILE] [--timeout TIMEOUT] spec

Observability experiments engine

positional arguments:
  spec                  Path to an oxn experiment specification to execute.

options:
  -h, --help            show this help message and exit
  --times TIMES         Run the experiment n times. Default is 1
  --report REPORT       Create an experiment report at the specified location. If the file exists, it will be overwritten. If it does not exist, it will be created.
  --accounting          Capture resource usage for oxn and the sue. Requires that the report option is set.Will increase the time it takes to run the experiment by about two seconds for each service in the sue.
  --randomize           Randomize the treatment execution order. Per default, treatments are executed in the order given in the experiment specification
  --extend EXTEND       Path to a treatment extension file. If specified, treatments in the file will be loaded into oxn.
  --loglevel [{debug,info,warning,error,critical}]
                        Set the log level. Choose between debug, info, warning, error, critical. Default is info
  --logfile LOG_FILE    Write logs to a file. If the file does not exist, it will be created.
  --timeout TIMEOUT     Timeout after which we stop trying to build the SUE. Default is 1m

```

2. Run an experiment and write the experiment report to disk 

```
oxn experiments/recommendation_pause_baseline.yml --report baseline_report.yml

```
