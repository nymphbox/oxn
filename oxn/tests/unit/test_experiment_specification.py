import unittest

import schema
import yaml


from oxn.validation import syntactic_schema

from oxn.tests.unit.spec_mocks import experiment_spec_mock


class SpecificationTest(unittest.TestCase):
    example_spec = experiment_spec_mock

    def test_syntax_ok(self):
        loaded_spec = yaml.safe_load(self.example_spec)
        self.assertTrue(syntactic_schema.validate(loaded_spec))

    def test_syntax_bad_no_responses(self):
        loaded_spec = yaml.safe_load(self.example_spec)
        modified_spec = loaded_spec.copy()
        modified_spec["experiment"].pop("responses")

        with self.assertRaises(schema.SchemaError):
            syntactic_schema.validate(modified_spec)

    def test_syntax_bad_incorrect_type_randomize(self):
        loaded_spec = yaml.safe_load(self.example_spec)
        modified_spec = loaded_spec.copy()
        modified_spec["experiment"]["randomize"] = 42
        with self.assertRaises(schema.SchemaError):
            syntactic_schema.validate(modified_spec)

    def test_syntax_bad_incorrect_type_loadgen_run_time(self):
        loaded_spec = yaml.safe_load(self.example_spec)
        modified_spec = loaded_spec.copy()
        modified_spec["experiment"]["loadgen"]["run_time"] = 42.0
        with self.assertRaises(schema.SchemaError):
            syntactic_schema.validate(modified_spec)
