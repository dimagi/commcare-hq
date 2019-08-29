
from abc import ABCMeta, abstractmethod, abstractproperty

from django.utils.translation import ugettext_lazy as _

import six
import sqlalchemy
from jsonobject.base_properties import DefaultProperty

from dimagi.ext import jsonobject

from corehq.apps.aggregate_ucrs.aggregations import AGG_WINDOW_START_PARAM
from corehq.apps.aggregate_ucrs.query_column_providers import (
    AggregationParamQueryColumnProvider,
    StandardQueryColumnProvider,
)
from corehq.apps.userreports import const
from corehq.apps.userreports.datatypes import (
    DATA_TYPE_DATE,
    DATA_TYPE_DECIMAL,
    DATA_TYPE_INTEGER,
    DATA_TYPE_SMALL_INTEGER,
    DATA_TYPE_STRING,
    DataTypeProperty,
)
from corehq.apps.userreports.indicators import Column
from corehq.apps.userreports.reports.specs import SQLAGG_COLUMN_MAP


class ColumnAdapater(six.with_metaclass(ABCMeta, object)):
    """
    A column adapter represents everything needed to work with an aggregate column,
    including its config as well as its sqlalchemy information (via the ucr column spec).

    Column adapters handle both the querying side (via the to_sqlalchemy_query_column function)
    as well as the table creation/writing side.
    """
    # most subclasses will/should override this to provide a schema for how they are configured.
    config_spec = jsonobject.JsonObject

    def __init__(self, db_column):
        self._db_column = db_column
        self.column_id = db_column.column_id
        self.properties = self.config_spec.wrap(db_column.config_params)

    @abstractmethod
    def is_nullable(self):
        pass

    @abstractmethod
    def is_primary_key(self):
        pass

    @abstractmethod
    def create_index(self):
        pass

    def to_ucr_column_spec(self):
        """
        :return: a UCR-compatible `Column` object that can be used to be converted to sqlalchemy tables
        """
        return Column(
            id=self.column_id,
            datatype=self.get_datatype(),
            is_nullable=self.is_nullable(),
            is_primary_key=self.is_primary_key(),
            create_index=self.create_index(),
        )

    @abstractmethod
    def get_datatype(self):
        pass

    @abstractmethod
    def to_sqlalchemy_query_column(self, sqlalchemy_table, aggregation_params):
        pass

    @abstractmethod
    def is_groupable(self):
        """
        Whether the column should be included in the group by clause when doing aggregation queries
        """
        pass


PRIMARY_COLUMN_TYPE_REFERENCE = 'reference'
PRIMARY_COLUMN_TYPE_CONSTANT = 'constant'
PRIMARY_COLUMN_TYPE_SQL = 'sql_statement'
PRIMARY_COLUMN_TYPE_CHOICES = (
    (PRIMARY_COLUMN_TYPE_REFERENCE, _('Reference')),
    (PRIMARY_COLUMN_TYPE_CONSTANT, _('Constant')),
    (PRIMARY_COLUMN_TYPE_SQL, _('SQL Statement')),
)


class RawColumnAdapter(ColumnAdapater):
    """
    A ColumnAdapter that is composed of all the possible fields it can have.
    """

    def __init__(self, column_id, datatype, is_nullable, is_primary_key, create_index, query_column_provider):
        # short circuit super class call to avoid refences to db_column
        # todo: find a better way to do this that doesn't break constructor inheritance
        self.column_id = column_id
        self._datatype = datatype
        self._is_nullable = is_nullable
        self._is_primary_key = is_primary_key
        self._create_index = create_index
        self.query_column_provider = query_column_provider

    def is_nullable(self):
        return self._is_nullable

    def is_primary_key(self):
        return self._is_primary_key

    def create_index(self):
        return self._create_index

    def get_datatype(self):
        return self._datatype

    def to_sqlalchemy_query_column(self, sqlalchemy_table, aggregation_params):
        return self.query_column_provider.get_query_column(sqlalchemy_table, aggregation_params)

    def is_groupable(self):
        return self.query_column_provider.is_groupable()


def IdColumnAdapter():
    """shortcut/convenience method to instantiate id columns"""
    return RawColumnAdapter(
        column_id='doc_id',
        datatype=DATA_TYPE_STRING,
        is_nullable=False,
        is_primary_key=True,
        create_index=True,
        query_column_provider=StandardQueryColumnProvider('doc_id'),
    )


def MonthColumnAdapter():
    """shortcut/convenience method to instantiate month columns"""
    return RawColumnAdapter(
        column_id='month',
        datatype=DATA_TYPE_DATE,
        is_nullable=False,
        is_primary_key=True,
        create_index=True,
        query_column_provider=AggregationParamQueryColumnProvider(AGG_WINDOW_START_PARAM)
    )


def WeekColumnAdapter():
    """shortcut/convenience method to instantiate week columns"""
    return RawColumnAdapter(
        column_id='week',
        datatype=DATA_TYPE_DATE,
        is_nullable=False,
        is_primary_key=True,
        create_index=True,
        query_column_provider=AggregationParamQueryColumnProvider(AGG_WINDOW_START_PARAM)
    )


class PrimaryColumnAdapter(six.with_metaclass(ABCMeta, ColumnAdapater)):
    """
    A base ColumnAdapter class for columns associated with the primary table.
    """

    def is_nullable(self):
        return True

    def is_primary_key(self):
        return False

    def create_index(self):
        return False

    @staticmethod
    def from_db_column(db_column):
        type_to_class_mapping = {
            PRIMARY_COLUMN_TYPE_REFERENCE: ReferenceColumnAdapter,
            PRIMARY_COLUMN_TYPE_CONSTANT: ConstantColumnAdapter,
            PRIMARY_COLUMN_TYPE_SQL: SqlColumnAdapter,
        }
        return type_to_class_mapping[db_column.column_type](db_column)

    def is_groupable(self):
        return True


class ConstantColumnProperties(jsonobject.JsonObject):
    constant = DefaultProperty(required=True)


class ConstantColumnAdapter(PrimaryColumnAdapter):
    """
    A PrimaryColumnAdapter class that allows populating a table with constant values.
    """

    config_spec = ConstantColumnProperties

    def get_datatype(self):
        # todo should be configurable
        return DATA_TYPE_INTEGER

    def to_sqlalchemy_query_column(self, sqlalchemy_table, aggregation_params):
        # https://stackoverflow.com/a/7546802/8207
        return sqlalchemy.bindparam(self.column_id, self.properties.constant)

    def is_groupable(self):
        return False


class ReferenceColumnProperties(jsonobject.JsonObject):
    referenced_column = jsonobject.StringProperty(required=True)


class ReferenceColumnAdapter(PrimaryColumnAdapter):
    """
    A PrimaryColumnAdapter class that allows populating a table with the value
    of a column in the primary table.
    """

    config_spec = ReferenceColumnProperties

    def get_datatype(self):
        return _get_datatype_from_referenced_column(self._db_column, self.properties.referenced_column)

    def to_sqlalchemy_query_column(self, sqlalchemy_table, aggregation_params):
        return sqlalchemy_table.c[self.properties.referenced_column]


class SqlColumnProperties(jsonobject.JsonObject):
    datatype = DataTypeProperty(required=True)
    statement = jsonobject.StringProperty(required=True)
    statement_params = jsonobject.DictProperty()


class SqlColumnAdapter(PrimaryColumnAdapter):
    """
    A PrimaryColumnAdapter class that allows populating a table with the value
    of a sql expression run on the primary table.
    """

    config_spec = SqlColumnProperties

    def get_datatype(self):
        return self.properties.datatype

    def to_sqlalchemy_query_column(self, sqlalchemy_table, aggregation_params):
        def _map_params(statement_params):
            mapped_params = {}
            for param_name, param_value in statement_params.items():
                mapped_value = param_value
                # transform anything starting with a ":" to the value passed in from aggregation_params
                if mapped_value.startswith(':'):
                    mapped_value = aggregation_params[mapped_value[1:]]
                mapped_params[param_name] = mapped_value
            return mapped_params

        mapped_params = _map_params(self.properties.statement_params)
        return sqlalchemy.text(self.properties.statement).bindparams(
            **mapped_params
        )


SECONDARY_COLUMN_TYPE_CHOICES = (
    (const.AGGGREGATION_TYPE_SUM, _('Sum')),
    (const.AGGGREGATION_TYPE_MIN, _('Min')),
    (const.AGGGREGATION_TYPE_MAX, _('Max')),
    (const.AGGGREGATION_TYPE_AVG, _('Average')),
    (const.AGGGREGATION_TYPE_COUNT, _('Count')),
    (const.AGGGREGATION_TYPE_COUNT_UNIQUE, _('Count Unique Values')),
    (const.AGGGREGATION_TYPE_NONZERO_SUM, _('Has a nonzero sum (1 if sum is nonzero else 0).')),
)


class SecondaryColumnAdapter(ColumnAdapater):
    """
    A base ColumnAdapter class for columns associated with secondary tables.
    """

    def is_nullable(self):
        return True

    def is_primary_key(self):
        return False

    def create_index(self):
        return False

    @staticmethod
    def from_db_column(db_column):
        assert db_column.aggregation_type in SQLAGG_COLUMN_MAP
        return SqlaggColumnAdapter(db_column)

    def is_groupable(self):
        return False


class SingleFieldColumnProperties(jsonobject.JsonObject):
    referenced_column = jsonobject.StringProperty(required=True)


class SimpleAggregationAdapater(six.with_metaclass(ABCMeta, SecondaryColumnAdapter)):
    """
    Generic SecondaryColumnAdapter class that does a passed-in sqlalchemy aggregation.
    """
    config_spec = SingleFieldColumnProperties

    @abstractproperty
    def sqlalchemy_fn(self):
        pass

    def to_sqlalchemy_query_column(self, sqlalchemy_table, aggregation_params):
        return self.sqlalchemy_fn(sqlalchemy_table.c[self.properties.referenced_column])


class SqlaggColumnAdapter(SimpleAggregationAdapater):

    def _get_sqlagg_column(self):
        return SQLAGG_COLUMN_MAP[self._db_column.aggregation_type](self._db_column.column_id)

    @property
    def sqlalchemy_fn(self):
        return self._get_sqlagg_column().aggregate_fn

    def get_datatype(self):
        # special case some columns to allow to e.g. count unique values from a string column
        if self._db_column.aggregation_type in (
                const.AGGGREGATION_TYPE_COUNT,
                const.AGGGREGATION_TYPE_COUNT_UNIQUE
        ):
            return DATA_TYPE_INTEGER
        elif self._db_column.aggregation_type in (
                const.AGGGREGATION_TYPE_NONZERO_SUM
        ):
            return DATA_TYPE_SMALL_INTEGER
        elif self._db_column.aggregation_type in (
                const.AGGGREGATION_TYPE_AVG
        ):
            return DATA_TYPE_DECIMAL
        else:
            # default to using the same column type as the source
            return _get_datatype_from_referenced_column(self._db_column, self.properties.referenced_column)


def _get_datatype_from_referenced_column(db_column, referenced_column):
    return db_column.table_definition.data_source.get_column_by_id(referenced_column).datatype
