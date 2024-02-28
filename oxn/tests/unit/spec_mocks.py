"""Library of mocks used by the tests"""

experiment_spec_mock = """
    experiment:
      responses:
        - my_metric_response_no_params:
            metric_name: prometheus_metric
            type: metric
            step: 5
            left_window: 2m
            right_window: 0m
        - otelcol_spans:
            metric_name: otelcol_exporter_sent_spans
            type: metric
            labels: {exporter: logging}
            step: 1
            left_window: 2m
            right_window: 2m
        - my_trace_response:
            type: trace
            service_name: adservice
            left_window: 5m
            right_window: 2m
      treatments:
         - pause_treatment:
            action: pause
            params:
                duration: 30s
                service_name: frontend
      sue:
        compose: /Users/witch/opentelemetry-demo/docker-compose.yml
        exclude: [loadgenerator]
        include: [otelcol]
      loadgen:
        run_time: 20s 
        stages:
            - {"duration": 5, "users": 1, "spawn_rate": 1}
            - {"duration": 15, "users": 10, "spawn_rate": 2}
        tasks:
            - {name: some_task_name, "endpoint": "/api/cart", "verb": "get", weight: 2, params: {}}
            - {name: some_other_task, "endpoint": "/", "verb": "get", weight: 5, params: {}}
    """
metric_rvar_description_mock = {
    "some_prometheus_metric": {
        "type": "metric",
        "metric_name": "otelcol_exporter_sent_spans",
        "step": "1",
        "labels": {
            "exporter": "logging",
        },
        "left_window": "2m",
        "right_window": "0m",
    }
}
screening_experiment_mock = """
experiment:
  responses:
    - recommendation_service_traces:
        type: trace
        service_name: recommendationservice
        left_window: 30s
        right_window: 30s
        limit: 1000
  sue:
    compose: /Users/witch/opentelemetry-demo/docker-compose.yml
    exclude: [loadgenerator]
  loadgen:
    run_time: 30s
    tasks:
    - { endpoint: /, verb: get, weight: 1, params: { } }
    - { endpoint: /api/products/0PUK6V6EV0, verb: get, weight: 1, params: { } }
    - { endpoint: /api/recommendations, verb: get, weight: 1, params: {"productIds": ["1YMWWN1N4O"]}}
    - { endpoint: /api/cart, verb: get, weight: 1, params: {}}
    - { endpoint: /api/data, verb: get, weight: 1, params: {"contextKeys": ["telescopes"]}}
"""
