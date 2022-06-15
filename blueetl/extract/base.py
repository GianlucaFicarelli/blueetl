import logging
from abc import ABC
from typing import Dict, List, Optional, Type, TypeVar

import pandas as pd

from blueetl.utils import ensure_dtypes

L = logging.getLogger(__name__)
ExtractorT = TypeVar("ExtractorT", bound="BaseExtractor")


class BaseExtractor(ABC):
    COLUMNS: List[str] = []
    _allow_missing_columns = False
    _allow_extra_columns = False
    _allow_empty_data = False

    def __init__(self, df: pd.DataFrame) -> None:
        self._validate(df)
        self._df = ensure_dtypes(df)

    @classmethod
    def _validate(cls, df: pd.DataFrame) -> None:
        cls._validate_data(df)
        cls._validate_columns(df)

    @classmethod
    def _validate_data(cls, df: pd.DataFrame) -> None:
        if not cls._allow_empty_data and len(df) == 0:
            raise RuntimeError(f"No data in {cls.__name__}")

    @classmethod
    def _validate_columns(cls, df: pd.DataFrame) -> None:
        # check the names of the columns
        actual = set(df.columns)
        expected = set(cls.COLUMNS)
        if not cls._allow_missing_columns and expected - actual:
            raise ValueError(f"Expected columns not present: {expected - actual}")
        if not cls._allow_extra_columns and actual - expected:
            raise ValueError(f"Additional columns not allowed: {actual - expected}")

    @property
    def df(self) -> pd.DataFrame:
        return self._df

    @classmethod
    def from_pandas(
        cls: Type[ExtractorT], df: pd.DataFrame, query: Optional[Dict] = None
    ) -> ExtractorT:
        if query:
            L.debug("Filtering dataframe by %s", query)
            df = df.etl.q(query)
        return cls(df)

    def to_pandas(self) -> pd.DataFrame:
        return self.df
