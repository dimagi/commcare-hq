from __future__ import absolute_import
from __future__ import unicode_literals

import sqlalchemy
from django.utils.translation import ugettext_lazy as _
from abc import ABCMeta, abstractmethod

import six
from jsonobject.base_properties import DefaultProperty

from corehq.apps.userreports.datatypes import DATA_TYPE_INTEGER, DataTypeProperty, DATA_TYPE_STRING, DATA_TYPE_DATE
from corehq.apps.userreports.indicators import Column
from dimagi.ext import jsonobject


class ColumnAdapater(six.with_metaclass(ABCMeta, object)):
    """
    A column adapter represents everything needed to work with an aggregate column,
    including its config as well as its sqlalchemy information (via the ucr column spec)
    """
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
    def to_sqlalchemy_query_column(self, sqlalchemy_table):
        pass


PRIMARY_COLUMN_TYPE_REFERENCE = 'reference'
PRIMARY_COLUMN_TYPE_CONSTANT = 'constant'
PRIMARY_COLUMN_TYPE_SQL = 'sql_statement'
PRIMARY_COLUMN_TYPE_CHOICES = (
    (PRIMARY_COLUMN_TYPE_REFERENCE, _('Reference')),
    (PRIMARY_COLUMN_TYPE_CONSTANT, _('Constant')),
    (PRIMARY_COLUMN_TYPE_SQL, _('SQL Statement')),
)


class RawColumnAdapter(six.with_metaclass(ABCMeta, ColumnAdapater)):

    def __init__(self, column_id, datatype, is_nullable, is_primary_key, create_index):
        # short circuit super class call to avoid refences to db_column
        # todo: find a better way to do this that doesn't break constructor inheritance
        self.column_id = column_id
        self._datatype = datatype
        self._is_nullable = is_nullable
        self._is_primary_key = is_primary_key
        self._create_index = create_index

    def is_nullable(self):
        return self._is_nullable

    def is_primary_key(self):
        return self._is_primary_key

    def create_index(self):
        return self._create_index

    def get_datatype(self):
        return self._datatype

    def to_sqlalchemy_query_column(self, sqlalchemy_table):
        return sqlalchemy_table.c[self.column_id]


def IdColumnAdapter():
    # shortcut/convenience method to instantiate id columns
    return RawColumnAdapter(
        column_id='doc_id',
        datatype=DATA_TYPE_STRING,
        is_nullable=False,
        is_primary_key=True,
        create_index=True,
    )


def MonthColumnAdapter():
    # shortcut/convenience method to instantiate month columns
    return RawColumnAdapter(
        column_id='month',
        datatype=DATA_TYPE_DATE,
        is_nullable=False,
        is_primary_key=True,
        create_index=True,
    )


class PrimaryColumnAdapter(six.with_metaclass(ABCMeta, ColumnAdapater)):

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


class ConstantColumnProperties(jsonobject.JsonObject):
    constant = DefaultProperty(required=True)


class ConstantColumnAdapter(PrimaryColumnAdapter):
    config_spec = ConstantColumnProperties

    def get_datatype(self):
        # todo should be configurable
        return DATA_TYPE_INTEGER

    def to_sqlalchemy_query_column(self, sqlalchemy_table):
        # https://stackoverflow.com/a/7546802/8207
        return sqlalchemy.sql.expression.bindparam(self.column_id, self.properties.constant)


class ReferenceColumnProperties(jsonobject.JsonObject):
    referenced_column = jsonobject.StringProperty(required=True)


class ReferenceColumnAdapter(PrimaryColumnAdapter):
    config_spec = ReferenceColumnProperties

    def get_datatype(self):
        return self._db_column.table_definition.data_source.get_column_by_id(
            self.properties.referenced_column
        ).datatype

    def to_sqlalchemy_query_column(self, sqlalchemy_table):
        return sqlalchemy_table.c[self.properties.referenced_column]


class SqlColumnProperties(jsonobject.JsonObject):
    datatype = DataTypeProperty(required=True)
    statement = jsonobject.StringProperty(required=True)
    statement_params = jsonobject.DictProperty()


class SqlColumnAdapter(PrimaryColumnAdapter):
    config_spec = SqlColumnProperties

    def get_datatype(self):
        return self.properties.datatype

    def to_sqlalchemy_query_column(self, sqlalchemy_table):
        # todo:
        return sqlalchemy.sql.expression.bindparam(self.column_id, 'not working yet')


SECONDARY_COLUMN_TYPE_SUM = 'sum'
SECONDARY_COLUMN_TYPE_CHOICES = (
    (SECONDARY_COLUMN_TYPE_SUM, _('Sum')),
    # todo: add other aggregations, count, min, max, (first? last?)
)


class SecondaryColumnAdapter(ColumnAdapater):

    def is_nullable(self):
        return True

    def is_primary_key(self):
        return False

    def create_index(self):
        return False

    @staticmethod
    def from_db_column(db_column):
        type_to_class_mapping = {
            SECONDARY_COLUMN_TYPE_SUM: SumColumnAdapter,
        }
        return type_to_class_mapping[db_column.aggregation_type](db_column)


class SingleFieldColumnProperties(jsonobject.JsonObject):
    referenced_column = jsonobject.StringProperty(required=True)


class SumColumnAdapter(SecondaryColumnAdapter):
    config_spec = SingleFieldColumnProperties

    def get_datatype(self):
        return DATA_TYPE_INTEGER

    def to_sqlalchemy_query_column(self, sqlalchemy_table):
        raise NotImplementedError('todo')

