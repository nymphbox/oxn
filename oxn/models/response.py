import uuid
import abc

import pandas as pd


class ResponseVariable(abc.ABC):
    def __init__(
        self,
        experiment_start: float,
        experiment_end: float,
    ):
        self.id = uuid.uuid4().hex
        """Unique identifier"""
        self.experiment_start = experiment_start
        """UTC Timestamp of experiment start"""
        self.experiment_end = experiment_end
        """UTC Timestamp of experiment end"""
        self.name = None
        """Name of the response variable as defined in experiment specification"""
        self.start = None
        """Start of the observation period"""
        self.end = None
        """End of the observation period"""
        self.data = None
        """Observed data stored as a dataframe"""

    @property
    @abc.abstractmethod
    def short_id(self) -> str:
        pass

    @property
    def response_type(self) -> str:
        return self.__class__.__name__

    @abc.abstractmethod
    def label(
        self,
        treatment_start: float,
        treatment_end: float,
        label_column: str,
        label: str,
    ) -> None:
        pass

    @abc.abstractmethod
    def observe(self) -> pd.DataFrame:
        pass
