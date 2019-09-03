from abc import ABCMeta, abstractmethod

import sqlalchemy


class QueryColumnProvider(metaclass=ABCMeta):
    """
    A QueryColumnProvider is a utility class that can provide a sqlalchemy column
    based on an input table and set of aggregation params.
    """

    @abstractmethod
    def get_query_column(self, sqlalchemy_table, aggregation_params):
        pass

    @abstractmethod
    def is_groupable(self):
        pass


class StandardQueryColumnProvider(QueryColumnProvider, metaclass=ABCMeta):
    """
    A QueryColumnProvider that passes the query through to a column on the table.
    """

    def __init__(self, column_id):
        self.column_id = column_id

    def get_query_column(self, sqlalchemy_table, aggregation_params):
        return sqlalchemy_table.c[self.column_id]

    def is_groupable(self):
        return True


class AggregationParamQueryColumnProvider(QueryColumnProvider, metaclass=ABCMeta):
    """
    A QueryColumnProvider that returns one of the aggregation params
    """

    def __init__(self, param_id):
        self.param_id = param_id

    def get_query_column(self, sqlalchemy_table, aggregation_params):
        return sqlalchemy.bindparam(self.param_id, aggregation_params[self.param_id])

    def is_groupable(self):
        return False
