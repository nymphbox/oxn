"""Unit and integration tests for the HDF based data store"""
import unittest

from oxn.store import Trie, get_dataframe, consolidate_runs


class StoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.trie = Trie(disk_name=None)
        self.entries = [
            "experiments/6ce2f6b0/a33e8e5b/otelcol_exporter_sent_spans",
            "experiments/6ce2f6b0/a31e8e5b/otelcol_exporter_some_other_metric",
            "experiments/6ce2f6b0/a35e8e5b/otelcol_exporter_sent_spans",
            "experiments/6ce2f6b0/f35e8e5b/otelcol_exporter_sent_spans",
        ]
        for entry in self.entries:
            self.trie.insert(entry)

    def test_it_searches_by_experiment(self):
        prefix = self.entries[0][:11]
        search = self.trie.query(item=prefix)
        self.assertTrue(search)
        self.assertTrue(len(search) == 4)

    def test_it_searches_by_run(self):
        prefix = "experiments/6ce2f6b0/"
        search = self.trie.query(item=prefix)
        self.assertTrue(search)

    def test_it_returns_empty_list_on_missing_key_trie(self):
        prefix = "not/in/store"
        search = self.trie.query(item=prefix)
        self.assertFalse(search)

    def test_it_returns_none_on_missing_key_store(self):
        key = "not/in/store"
        df = get_dataframe(key)
        self.assertFalse(df)

    def test_it_returns_none_on_missing_key_concat(self):
        key = "not/in/store"
        response_variable = "foobar"
        dfs = consolidate_runs(experiment_key=key, response_variable=response_variable)
        self.assertFalse(dfs)
