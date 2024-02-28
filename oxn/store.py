"""
Simple HDF5-based storage
"""
import pickle
import warnings

import pandas as pd
from typing import List
from .settings import STORAGE_NAME, TRIE_NAME

# silence warning that we cant use hex strings as key names
# we don't want table accessing by dot notation
# due to fixed format in hdf
from tables import NaturalNameWarning

warnings.filterwarnings("ignore", category=NaturalNameWarning)


class Node:
    """A node in the trie structure"""

    def __init__(self, character):
        self.character = character
        """Character stored at this node"""
        self.end = False
        """Indicates if this is a leaf node"""
        self.children = {}
        """Children of this node"""


class Trie:
    """A trie to facilitate efficient prefix based lookups for the underlying hdf5 store"""

    def __init__(self, disk_name=TRIE_NAME):
        self.root = Node("")
        """The root node of the trie"""
        self.keys = []
        """List to accumulate results in"""
        self.disk_name = disk_name
        """If set, serialize and deserialize the trie from disk at the specified name. Leave blank for testing"""
        if self.disk_name:
            self.deserialize()

    def insert(self, store_entry: str):
        """Insert a storage key into the Trie"""
        node = self.root

        for character in store_entry:
            if character in node.children:
                node = node.children[character]
            else:
                new_node = Node(character)
                node.children[character] = new_node
                node = new_node
        node.end = True
        if self.disk_name:
            self.serialize()

    def depth_first_search(self, node, prefix):
        """Recursive DFS implementation"""
        if node.end:
            self.keys.append(prefix + node.character)
        for child in node.children.values():
            self.depth_first_search(child, prefix + node.character)

    def query(self, item):
        """
        Query the trie for an item.

        Querying the trie with "" will return all items in the trie in LIFO order.

        """
        self.keys = []
        node = self.root

        for character in item:
            if character in node.children:
                node = node.children[character]
            else:
                return []
        self.depth_first_search(node, item[:-1])

        return sorted(self.keys, reverse=True)

    def serialize(self):
        """Write the trie to disk"""
        if self.disk_name:
            with open(self.disk_name, "wb") as fp:
                pickle.dump(self.root, fp)

    def deserialize(self):
        """Deserialize the trie from disk"""

        # trie might have not been serialized yet
        if self.disk_name:
            try:
                with open(self.disk_name, "rb") as fp:
                    self.root = pickle.load(fp)
            except FileNotFoundError:
                return


def construct_key(experiment_key, run_key, response_key):
    """Construct a storage key from the experiment name, run id and response name"""
    return experiment_key + "/" + run_key + "/" + response_key


def write_dataframe(dataframe, experiment_key, run_key, response_key) -> None:
    """Write a dataframe to the store"""
    with pd.HDFStore(STORAGE_NAME) as store:
        key = construct_key(experiment_key, run_key, response_key)
        store.put(key=key, value=dataframe)
        trie = Trie()
        trie.insert(key)


def get_dataframe(key):
    """Retrieve a dataframe from the store"""
    trie = Trie()
    results = trie.query(key)
    if results:
        with pd.HDFStore(STORAGE_NAME) as store:
            return store.get(key=key)


def annotate(key, **kwargs):
    """Annotate a stored response variable with metadata"""
    with pd.HDFStore(STORAGE_NAME) as store:
        store.get_storer(key).attrs.metadata = kwargs


def remove_dataframe(key) -> None:
    """Remove a dataframe from the store"""
    with pd.HDFStore(STORAGE_NAME) as store:
        store.remove(key=key)


def consolidate_runs(experiment_key, response_variable) -> pd.DataFrame:
    """
    Return a consolidated dataframe from the store

    A consolidated dataframe contains all data for a given response and a given experiment key
    """
    trie = Trie()
    results = trie.query(experiment_key)
    results = [key for key in results if response_variable in key]
    dataframes = [get_dataframe(result) for result in results]
    if dataframes:
        return pd.concat(dataframes)


def list_keys_for_experiment(experiment_key) -> List[str]:
    """Return all keys from the store that match a given experiment key"""
    trie = Trie()
    results = trie.query(item=experiment_key)
    return results


def list_keys_for_run(experiment_key, experiment_run) -> List[str]:
    """Return all keys from the store that match a given experiment and run key"""
    trie = Trie()
    results = trie.query(experiment_key + experiment_run)
    return results


def list_all_dataframes():
    """List all dataframes in the store"""
    with pd.HDFStore(STORAGE_NAME) as store:
        return store.keys(include="pandas")
