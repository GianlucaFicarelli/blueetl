"""Pandas accessors."""
import collections
import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

L = logging.getLogger(__name__)

# Naming conventions
#  level: number, or name of the level in the MultiIndex
#  condition: name of the level (e.g. seed), similar to level, but it cannot be numeric
#  labels: possible values for a specific level of the index


class ETLBaseAccessor:
    """Accessor with methods common to Series and DataFrame."""

    def __init__(self, pandas_obj):
        """Initialize the accessor."""
        self._validate(pandas_obj)
        self._obj = pandas_obj

    @staticmethod
    def _validate(obj):
        """Validate the wrapped object."""
        # assert all(obj.index.names), "All the index levels must have a name"
        # assert len(set(obj.index.names)) == obj.index.nlevels, "The level names must be unique"

    def conditions(self):
        """Names for each of the index levels."""
        return self._obj.index.names

    def complementary_conditions(self, conditions):
        """Return the difference between the object conditions and the specified conditions.

        Args:
            conditions: single condition or list of conditions used to calculate the difference.
        """
        if not isinstance(conditions, (tuple, list)):
            conditions = [conditions]
        # TODO: raise a KeyError if any condition is not found in self.conditions?
        return self._obj.index.names.difference(conditions)

    def labels(self):
        """Unique labels for each level."""
        return [self.labels_of(condition) for condition in self.conditions()]

    def labels_of(self, condition):
        """Unique labels for a specific level in the index.

        Args:
            condition (str): condition name.
        """
        return self._obj.index.unique(condition)

    def remove_condition(self, condition):
        """Remove one or more conditions.

        Args:
            condition: single condition or list of conditions to remove.
        """
        return self._obj.droplevel(condition, axis=0)

    def keep_condition(self, condition):
        """Remove the conditions not specified.

        Args:
            condition: single condition or list of conditions to keep.
        """
        return self._obj.droplevel(self.complementary_conditions(condition), axis=0)

    def add_condition(self, condition, value, inner=False):
        """Add a new condition in the outermost or innermost level with the given value.

        Args:
            condition: condition to be added.
            value: value of the condition.
            inner (bool): if True, add the condition in the innermost position.
        """
        result = pd.concat([self._obj], axis="index", keys=[value], names=[condition])
        if inner:
            result = result.reorder_levels(list(range(1, result.index.nlevels)) + [0])
        return result

    def select(self, drop_level=True, **kwargs):
        """Filter the series or dataframe based on some conditions on the index.

        Args:
            drop_level (bool): True to drop the conditions from the returned object.
            kwargs: conditions used to filter, specified as name=value.
        """
        if not kwargs:
            return self._obj
        labels, values = zip(*kwargs.items())
        return self._obj.xs(level=labels, key=values, drop_level=drop_level, axis=0)

    filter = select  # deprecated, to be removed

    def select_one(self, drop_level=True, **kwargs):
        return self.select(drop_level=drop_level, **kwargs).iat[0]

    def groupby_excluding(self, conditions, *args, **kwargs):
        """Group by all the conditions except for the ones specified.

        Args:
            conditions: single condition or list of conditions to be excluded from the groupby
        """
        complementary_conditions = self.complementary_conditions(conditions)
        return self._obj.groupby(complementary_conditions, *args, **kwargs)

    def pool(self, conditions, func):
        """Remove one or more conditions grouping by the remaining conditions.

        Args:
            conditions: single condition or list of conditions to be removed from the index.
            func: function that should accept a single element.
                If the returned value is a Series, it will be used as an additional level
                in the MultiIndex of the returned object.
        """
        return self.groupby_excluding(conditions).apply(func)


class ETLSeriesAccessor(ETLBaseAccessor):
    """Series accessor."""

    def unpool(self, func):
        """Apply the given function to the object elements and add a condition to the index.

        Args:
            func: function that should accept a single element and return a Series object.
                The name of that Series will be used as the name of the new level
                in the MultiIndex of the returned object.
        """
        return self._obj.apply(func).stack()

    # def merge(self, other):
    #     # FIXME: to be removed if redundant
    #     return pd.concat([self._obj, other.reindex_like(self._obj)])
    #
    # def map(self, func):
    #     # FIXME: to be removed if redundant
    #     return self._obj.map(func)

    # def remodel(self, func):
    #     """Apply func and return a new Series.
    #
    #     Args:
    #         func: generator function accepting the Series as argument, and yielding tuples
    #             (value, conditions) that will be concatenated to build a new Series.
    #
    #     Returns:
    #         (pd.Series) result of the concatenation.
    #     """
    #     return concat_tuples(func(self._obj))

    def iter(self):
        """Iterate over the items, yielding a tuple (named_index, value) for each element.

        The returned named_index is a namedtuple representing the value of the index.
        The returned value is the actual value of each element of the series.
        """
        return zip(self._obj.index.etl.iter(), iter(self._obj))

    iter_named_items = iter  # deprecated

    def query_dict(self, query: Dict) -> pd.Series:
        """Given a query dictionary, return a new Series filtered by index."""
        series = self._obj
        if query:
            masks = (
                series.index.get_level_values(k).isin(v if isinstance(v, list) else [v])
                for k, v in query.items()
            )
            series = series[np.all(list(masks), axis=0)]
        return series.copy()

    def q(self, _query: Optional[Dict] = None, /, **params) -> pd.Series:
        """Given a query dictionary or some query parameters, return a new Series filtered by index.

        Filter by index.
        Query and params cannot be specified together.
        If they are both empty or unspecified, return a copy of the original Series.

        Args:
            _query: query dictionary, with:
                    keys: index levels
                    values: value or list of values
                All the keys are combined with AND, while each list of values is combined with OR.
                Examples
                    {"mtype": "SO_BP", "etype": "cNAC"} -> mtype == SO_BP AND etype == cNAC
                    {"mtype": ["SO_BP", "SP_AA"]} -> mtype == SO_BP OR mtype == SP_AA
        """
        if _query and params:
            raise ValueError("Only one of 'query' and 'params' can be specified")
        return self.query_dict(_query or params)


class ETLDataFrameAccessor(ETLBaseAccessor):
    """DataFrame accessor."""

    def iter(self):
        """Iterate over the items, yielding a tuple (named_index, value) for each element.

        The returned ``named_index`` is a namedtuple representing the value of the index.
        The returned ``value`` is a namedtuple as returned by pandas.DataFrame.itertuples.
        """
        return zip(self._obj.index.etl.iter(), self._obj.itertuples(index=False, name="Values"))

    iter_named_items = iter  # deprecated

    def query_dict(self, query: Dict) -> pd.DataFrame:
        """Given a query dictionary, return a new DataFrame filtered by columns and index."""
        df = self._obj
        # split query keys into columns and index
        q = {"columns": {}, "index": {}}
        columns_set = set(df.columns)
        for k, v in query.items():
            # ensure that all the values are lists
            v = [v] if not isinstance(v, list) else v
            q["columns" if k in columns_set else "index"][k] = v
        # filter by columns if needed
        if q["columns"]:
            df = df[df[list(q["columns"])].isin(q["columns"]).all(axis=1)]
        # filter by index if needed
        if q["index"]:
            masks = (df.index.get_level_values(k).isin(v) for k, v in q["index"].items())
            df = df[np.all(list(masks), axis=0)]
        return df.copy()

    def q(self, _query: Optional[Dict] = None, /, **params) -> pd.DataFrame:
        """Given a query dictionary or some query parameters, return the filtered DataFrame.

        Filter by columns and index.
        Query and params cannot be specified together.
        If they are both empty or unspecified, return a copy of the original DataFrame.

        This method is similar to pd.DataFrame.query, but it accepts a dict instead of a string
        and has some limitations on the possible filters to be applied.

        Args:
            _query: query dictionary, with:
                    keys: columns or index levels
                    values: value or list of values
                All the keys are combined with AND, while each list of values is combined with OR.
                Examples
                    {"mtype": "SO_BP", "etype": "cNAC"} -> mtype == SO_BP AND etype == cNAC
                    {"mtype": ["SO_BP", "SP_AA"]} -> mtype == SO_BP OR mtype == SP_AA
        """
        if _query and params:
            raise ValueError("Query and params cannot be specified together")
        return self.query_dict(_query or params)

    query_params = q  # deprecated

    def grouped_by(self, groupby_columns, selected_columns, sort=True, observed=True):
        """Group the dataframe by some columns and yield each record as a tuple (key, df).

        Yields:
            a tuple (key, df), where key is a namedtuple with the grouped columns
        """
        grouped = self._obj.groupby(groupby_columns, sort=sort, observed=observed)
        grouped = grouped[selected_columns]
        RecordKey = collections.namedtuple("RecordKey", groupby_columns)
        for key, df in grouped:
            yield RecordKey(*key), df


class ETLIndexAccessor:
    def __init__(self, pandas_obj):
        """Initialize the accessor."""
        self._obj = pandas_obj

    def iter(self):
        """Iterate over the index, yielding a namedtuple for each element.

        It can be used as an alternative to the pandas iteration over the index
        to yield named tuples instead of standard tuples.

        It works with both Indexes and MultiIndexes.
        """
        names = self._obj.names
        Index = collections.namedtuple("Index", names, rename=True)
        if len(names) > 1:
            yield from (Index(*i) for i in self._obj)
        else:
            yield from (Index(i) for i in self._obj)


def register_accessors():
    """Register the accessors.

    It must be called once, before accessing the etl namespace.
    """
    L.info("Registering etl pandas accessors")
    # alternatively, the accessors could be registered with a decorator,
    # but this call is more explicit and it doesn't need any unused import
    pd.api.extensions.register_series_accessor("etl")(ETLSeriesAccessor)
    pd.api.extensions.register_dataframe_accessor("etl")(ETLDataFrameAccessor)
    pd.api.extensions.register_index_accessor("etl")(ETLIndexAccessor)